from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from app.db.models import CareSession, NFCTag, Patient
from fastapi import HTTPException, status


class CareSessionService:
    """Service layer for care session operations"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.tenant_schema = tenant_schema
    
    async def _set_search_path(self):
        """Set PostgreSQL search_path to tenant schema"""
        await self.db.execute(text(f"SET search_path TO {self.tenant_schema}"))
    
    async def create_session(
        self,
        tag_id: str,
        caregiver_id: UUID,
        caregiver_notes: str = None,
    ) -> dict:
        """
        Create a new care session by scanning an NFC tag.
        
        Steps:
        1. Validate NFC tag exists and is active
        2. Check for duplicate active sessions on same tag
        3. Get patient_id from NFC tag
        4. Create session record with check_in timestamp
        """
        await self._set_search_path()
        
        # Step 1: Validate NFC tag
        stmt = select(NFCTag).where(
            and_(
                NFCTag.tag_id == tag_id,
                NFCTag.status == "active",
            )
        )
        result = await self.db.execute(stmt)
        nfc_tag = result.scalar_one_or_none()
        
        if not nfc_tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NFC tag '{tag_id}' not found or inactive"
            )
        
        # Step 2: Check for duplicate active sessions
        stmt = select(CareSession).where(
            and_(
                CareSession.patient_id == nfc_tag.patient_id,
                CareSession.status == "in_progress",
                CareSession.deleted_at == None,
            )
        )
        result = await self.db.execute(stmt)
        existing_session = result.scalar_one_or_none()
        
        if existing_session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Active session already exists for this patient"
            )
        
        # Step 3 & 4: Create session
        new_session = CareSession(
            patient_id=nfc_tag.patient_id,
            caregiver_id=caregiver_id,
            status="in_progress",
            caregiver_notes=caregiver_notes,
        )
        
        self.db.add(new_session)
        await self.db.commit()
        await self.db.refresh(new_session)
        
        return new_session
    
    async def get_session(self, session_id: UUID) -> CareSession:
        """Get a care session by ID"""
        await self._set_search_path()
        
        stmt = select(CareSession).where(
            and_(
                CareSession.id == session_id,
                CareSession.deleted_at == None,
            )
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care session not found"
            )
        
        return session
    
    async def get_patient_with_session(self, session_id: UUID) -> dict:
        """Get patient details for a care session"""
        await self._set_search_path()
        
        # Get session first
        stmt = select(CareSession).where(CareSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care session not found"
            )
        
        # Get patient
        stmt = select(Patient).where(Patient.id == session.patient_id)
        result = await self.db.execute(stmt)
        patient = result.scalar_one_or_none()
        
        return {"session": session, "patient": patient}
