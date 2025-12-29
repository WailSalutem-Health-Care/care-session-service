from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.care_sessions.models import CareSession
from app.care_sessions.repository import CareSessionRepository
from app.db.models import NFCTag, Patient
from fastapi import HTTPException, status


class CareSessionService:
    """Service layer for care session business logic"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.repository = CareSessionRepository(db, tenant_schema)
    
    async def create_session(
        self,
        tag_id: str,
        caregiver_id: UUID,
    ) -> CareSession:
        """
        Create a new care session by scanning an NFC tag.
        
        Steps:
        1. Validate NFC tag exists and is active
        2. Check for duplicate active sessions
        3. Create session record
        """
        # Validate NFC tag
        await self.repository._set_search_path()
        stmt = select(NFCTag).where(NFCTag.tag_id == tag_id, NFCTag.status == "active")
        result = await self.db.execute(stmt)
        nfc_tag = result.scalar_one_or_none()
        
        if not nfc_tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NFC tag '{tag_id}' not found or inactive"
            )
        
        # Check for duplicate active sessions
        existing_session = await self.repository.get_active_by_patient(nfc_tag.patient_id)
        
        if existing_session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Active session already exists for this patient"
            )
        
        # Create session (no notes on check-in)
        new_session = CareSession(
            patient_id=nfc_tag.patient_id,
            caregiver_id=caregiver_id,
            status="in_progress",
        )
        
        return await self.repository.create(new_session)
    
    async def get_session(self, session_id: UUID) -> CareSession:
        """Get a care session by ID"""
        session = await self.repository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care session not found"
            )
        
        return session
    
    async def get_patient_with_session(self, session_id: UUID) -> dict:
        """Get patient details for a care session"""
        session = await self.repository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care session not found"
            )
        
        # Get patient
        await self.repository._set_search_path()
        stmt = select(Patient).where(Patient.id == session.patient_id)
        result = await self.db.execute(stmt)
        patient = result.scalar_one_or_none()
        
        return {"session": session, "patient": patient}

    async def complete_session(
        self,
        session_id: UUID,
        caregiver_notes: str,
        caregiver_id: UUID,
    ) -> CareSession:
        """
        Complete a care session (check-out).
        
        Steps:
        1. Validate session exists and is in progress
        2. Verify caregiver owns the session
        3. Update with check_out_time, notes, and status
        """
        session = await self.repository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care session not found"
            )
        
        if session.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete session with status: {session.status}"
            )
        
        if session.caregiver_id != caregiver_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only complete your own sessions"
            )
        
        # Update session
        session.check_out_time = datetime.utcnow()
        session.caregiver_notes = caregiver_notes
        session.status = "completed"
        
        return await self.repository.update(session)
