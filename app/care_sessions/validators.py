"""Validation logic for care sessions"""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import CareSession
from app.care_sessions.exceptions import (
    NFCTagNotFoundException,
    InvalidStatusException,
    InvalidSessionTimesException,
    SessionNotInProgressException,
    UnauthorizedCaregiverException,
)
from app.db.models import NFCTag


class SessionValidator:
    """Validates care session business rules"""
    
    VALID_STATUSES = ["in_progress", "completed"]
    
    def __init__(self, db: AsyncSession, repository):
        self.db = db
        self.repository = repository
    
    async def validate_and_get_nfc_tag(self, tag_id: str) -> NFCTag:
        """Find active NFC tag or raise 404"""
        await self.repository._set_search_path()
        stmt = select(NFCTag).where(NFCTag.tag_id == tag_id, NFCTag.status == "active")
        result = await self.db.execute(stmt)
        nfc_tag = result.scalar_one_or_none()
        
        if not nfc_tag:
            raise NFCTagNotFoundException(tag_id)
        return nfc_tag
    
    def validate_status(self, status: str) -> None:
        """Validate status value"""
        if status not in self.VALID_STATUSES:
            raise InvalidStatusException(status, self.VALID_STATUSES)
    
    def validate_session_times(self, session: CareSession) -> None:
        """Validate check_out_time > check_in_time"""
        if session.check_out_time and session.check_in_time:
            if session.check_out_time <= session.check_in_time:
                raise InvalidSessionTimesException()
    
    def validate_session_in_progress(self, session: CareSession) -> None:
        """Validate session is in progress"""
        if session.status != "in_progress":
            raise SessionNotInProgressException(session.status)
    
    def validate_caregiver_ownership(self, session: CareSession, caregiver_id: UUID) -> None:
        """Validate caregiver owns the session"""
        if session.caregiver_id != caregiver_id:
            raise UnauthorizedCaregiverException()
