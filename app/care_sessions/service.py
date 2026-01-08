from uuid import UUID
from datetime import datetime
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.care_sessions.models import CareSession
from app.care_sessions.repository import CareSessionRepository
from app.care_sessions.validators import SessionValidator
from app.care_sessions.event_publisher import SessionEventPublisher
from app.care_sessions.exceptions import (
    CareSessionNotFoundException,
    DuplicateActiveSessionException,
)
from app.db.models import Patient


class CareSessionService:
    """Service layer for care session business logic"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.repository = CareSessionRepository(db, tenant_schema)
        self.validator = SessionValidator(db, self.repository)
        self.event_publisher = SessionEventPublisher(tenant_schema)
    
    async def _get_session_or_404(self, session_id: UUID | str) -> CareSession:
        """Get session by primary ID (UUID) or by public session_id (string) or raise 404"""
        session = None
        # Try by primary UUID id first
        try:
            if isinstance(session_id, str):
                # attempt to fetch by public session_id string
                session = await self.repository.get_by_session_id(session_id)
            else:
                session = await self.repository.get_by_id(session_id)
        except Exception:
            # fallback: if session_id is UUID-like string, repository.get_by_id expects UUID
            session = await self.repository.get_by_session_id(str(session_id))

        if not session:
            raise CareSessionNotFoundException(session_id)
        return session
    
    async def create_session(
        self,
        tag_id: str,
        caregiver_id: UUID,
        session_id: str | None = None,
    ) -> CareSession:
        """
        Create a new care session by scanning an NFC tag.
        
        Steps:
        1. Validate NFC tag exists and is active
        2. Check for duplicate active sessions
        3. Create session record
        """
        # Validate NFC tag
        nfc_tag = await self.validator.validate_and_get_nfc_tag(tag_id)
        
        # Check for duplicate active sessions
        existing_session = await self.repository.get_active_by_patient(nfc_tag.patient_id)
        if existing_session:
            raise DuplicateActiveSessionException(nfc_tag.patient_id)
        
        # Create session
        new_session = CareSession(
            patient_id=nfc_tag.patient_id,
            caregiver_id=caregiver_id,
            status="in_progress",
        )
        # Only set public session_id if provided; otherwise let the model/DB default generate it
        if session_id:
            new_session.session_id = session_id
        
        created_session = await self.repository.create(new_session)
        self.event_publisher.publish_session_created(created_session)
        
        return created_session
    
    async def get_session(self, session_id: UUID | str) -> CareSession:
        """Get a care session by primary ID or public session_id"""
        return await self._get_session_or_404(session_id)
    
    async def get_patient_with_session(self, session_id: UUID | str) -> dict:
        """Get patient details for a care session"""
        session = await self._get_session_or_404(session_id)
        
        # Get patient
        await self.repository._set_search_path()
        stmt = select(Patient).where(Patient.id == session.patient_id)
        result = await self.db.execute(stmt)
        patient = result.scalar_one_or_none()
        
        return {"session": session, "patient": patient}

    async def complete_session(
        self,
        session_id: UUID | str,
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
        session = await self._get_session_or_404(session_id)
        
        # Validate business rules
        self.validator.validate_session_in_progress(session)
        self.validator.validate_caregiver_ownership(session, caregiver_id)
        
        # Update session
        session.check_out_time = datetime.utcnow()
        session.caregiver_notes = caregiver_notes
        session.status = "completed"
        
        updated_session = await self.repository.update(session)
        self.event_publisher.publish_session_completed(updated_session)
        
        return updated_session


    async def update_session(
        self,
        session_id: UUID | str,
        check_in_time: datetime | None = None,
        check_out_time: datetime | None = None,
        caregiver_notes: str | None = None,
        status: str | None = None,
    ) -> CareSession:
        """
        Update a care session (Admins only - for corrections/adjustments).
        
        Steps:
        1. Validate session exists
        2. Apply partial updates
        3. Validate business rules
        """
        session = await self._get_session_or_404(session_id)
        
        # Apply updates
        if check_in_time is not None:
            session.check_in_time = check_in_time
        
        if check_out_time is not None:
            session.check_out_time = check_out_time
        
        if caregiver_notes is not None:
            session.caregiver_notes = caregiver_notes
        
        if status is not None:
            self.validator.validate_status(status)
            session.status = status
        
        # Validate session times
        self.validator.validate_session_times(session)
        
        return await self.repository.update(session)
    
    async def list_sessions(
        self,
        caregiver_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CareSession], int]:
        """
        List care sessions with filters and pagination.
        
        Args:
            caregiver_id: Filter by caregiver
            patient_id: Filter by patient
            status: Filter by status (in_progress, completed)
            start_date: Filter sessions from this date (check_in_time)
            end_date: Filter sessions until this date (check_in_time)
            page: Page number (1-indexed)
            page_size: Number of results per page
        
        Returns:
            Tuple of (sessions, total_count)
        """
        # Validate status if provided
        if status:
            self.validator.validate_status(status)
        
        return await self.repository.list_sessions(
            caregiver_id=caregiver_id,
            patient_id=patient_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
