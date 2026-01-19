from uuid import UUID
from datetime import datetime
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CareSession
from app.care_sessions.repository import CareSessionRepository
from app.care_sessions.validators import SessionValidator
from app.care_sessions.auto_complete import auto_complete_if_needed
from app.care_sessions.exceptions import (
    CareSessionNotFoundException,
    DuplicateActiveSessionException,
)
from app.utils.timezone import now_cet
from app.observability.metrics import track_care_session_operation


class CareSessionService:
    """Service layer for care session business logic"""

    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.tenant_schema = tenant_schema
        self.repository = CareSessionRepository(db, tenant_schema)
        self.validator = SessionValidator(db, self.repository, tenant_schema)

    async def _get_session_or_404(self, id: UUID) -> CareSession:
        """Get session by UUID or raise 404"""
        session = await self.repository.get_by_id(id)
        if not session:
            raise CareSessionNotFoundException(id)
        return session

    async def create_session(
        self,
        tag_id: str,
        caregiver_id: UUID,
        session_id: Optional[str] = None,
    ) -> CareSession:
        """
        Create a new care session by scanning an NFC tag.

        Flow:
        1. Caregiver logs in via Keycloak → gets JWT with caregiver_id
        2. Caregiver scans NFC tag → mobile app sends tag_id to this endpoint
        3. This service gets patient_id from NFC event cache (via RabbitMQ)
        4. Creates session with caregiver_id (from JWT) + patient_id (from NFC event)
        """
        with track_care_session_operation("create", tenant_id=self.tenant_schema):
            # Get patient_id from NFC event cache (populated by RabbitMQ consumer)
            patient_id = self.validator.get_patient_id_from_nfc_event(tag_id)

            # Check for duplicate active sessions
            existing_session = await self.repository.get_active_by_patient(patient_id)
            if existing_session:
                raise DuplicateActiveSessionException(patient_id)

            # Create session with CET timestamp
            new_session = CareSession(
                patient_id=patient_id,
                caregiver_id=caregiver_id,
                status="in_progress",
                check_in_time=now_cet(),  # Explicitly set check_in_time in CET
            )
            # Only set public session_id if provided; otherwise let the model/DB default generate it
            if session_id:
                new_session.session_id = session_id

            created_session = await self.repository.create(new_session)
            return created_session

    async def get_session(self, session_id: UUID) -> CareSession:
        """Get a care session by UUID. Auto-completes if > 2 hours old."""
        session = await self._get_session_or_404(session_id)

        # Auto-complete if expired
        if auto_complete_if_needed(session):
            await self.db.commit()

        return session

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
        with track_care_session_operation("complete", tenant_id=self.tenant_schema):
            session = await self._get_session_or_404(session_id)

            # Validate business rules
            self.validator.validate_session_in_progress(session)
            self.validator.validate_caregiver_ownership(session, caregiver_id)

            # Update session with CET timestamp
            session.check_out_time = now_cet()
            session.caregiver_notes = caregiver_notes
            session.status = "completed"

            updated_session = await self.repository.update(session)
            return updated_session

    async def update_session(
        self,
        session_id: UUID,
        check_in_time: Optional[datetime] = None,
        check_out_time: Optional[datetime] = None,
        caregiver_notes: Optional[str] = None,
        status: Optional[str] = None,
    ) -> CareSession:
        """
        Update a care session (Admins only - for corrections/adjustments).

        Steps:
        1. Validate session exists
        2. Apply partial updates
        3. Validate business rules
        """
        with track_care_session_operation("update", tenant_id=self.tenant_schema):
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

        sessions, total = await self.repository.list_sessions(
            caregiver_id=caregiver_id,
            patient_id=patient_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )

        # Auto-complete expired sessions
        if any(auto_complete_if_needed(s) for s in sessions):
            await self.db.commit()

        return sessions, total

    async def delete_session(self, session_id: UUID) -> bool:
        """
        Delete a care session (soft delete - for developers/testing only).

        Args:
            session_id: Session UUID to delete

        Returns:
            True if deletion successful, False if session not found
        """
        with track_care_session_operation("delete", tenant_id=self.tenant_schema):
            return await self.repository.delete(session_id)
