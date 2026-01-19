from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CareSession
from app.messaging.nfc_cache import get_nfc_cache
from app.care_sessions.exceptions import (
    NFCTagNotFoundException,
    InvalidStatusException,
    InvalidSessionTimesException,
    SessionNotInProgressException,
    UnauthorizedCaregiverException,
)


class SessionValidator:
    VALID_STATUSES = ["in_progress", "completed"]

    def __init__(self, db: AsyncSession, repository, tenant_schema: str):
        self.db = db
        self.repository = repository
        self.tenant_schema = tenant_schema
        self.nfc_cache = get_nfc_cache()

    def get_patient_id_from_nfc_event(self, tag_id: str) -> UUID:
        patient_id = self.nfc_cache.get_patient_id(tag_id)
        if not patient_id:
            raise NFCTagNotFoundException(tag_id)
        return patient_id

    def validate_status(self, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise InvalidStatusException(status, self.VALID_STATUSES)

    def validate_session_times(self, session: CareSession) -> None:
        if session.check_out_time and session.check_in_time:
            if session.check_out_time <= session.check_in_time:
                raise InvalidSessionTimesException()

    def validate_session_in_progress(self, session: CareSession) -> None:
        if session.status != "in_progress":
            raise SessionNotInProgressException(session.status)

    def validate_caregiver_ownership(self, session: CareSession, caregiver_id: UUID) -> None:
        if session.caregiver_id != caregiver_id:
            raise UnauthorizedCaregiverException()
