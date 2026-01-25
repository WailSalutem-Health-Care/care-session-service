from uuid import UUID
import asyncio
import logging
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

logger = logging.getLogger(__name__)


class SessionValidator:
    VALID_STATUSES = ["in_progress", "completed"]

    def __init__(self, db: AsyncSession, repository, tenant_schema: str):
        self.db = db
        self.repository = repository
        self.tenant_schema = tenant_schema
        self.nfc_cache = get_nfc_cache()

    async def get_patient_id_from_nfc_event(self, tag_id: str) -> UUID:
        """
        Get patient_id from NFC cache with retry logic.

        The NFC resolve API publishes an event to RabbitMQ asynchronously.
        We retry with exponential backoff to wait for the consumer to process it.

        Retry strategy:
        - Attempts: 5 (0ms, 100ms, 200ms, 400ms, 800ms = ~1.5s total)
        - This handles typical message processing latency
        """
        max_retries = 5
        retry_delay = 0.1  # Start with 100ms

        for attempt in range(max_retries):
            patient_id = self.nfc_cache.get_patient_id(tag_id)
            if patient_id:
                if attempt > 0:
                    logger.info(f"NFC tag {tag_id} resolved after {attempt + 1} attempts")
                return patient_id

            if attempt < max_retries - 1:
                logger.debug(
                    f"NFC tag {tag_id} not in cache, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

        # After all retries failed
        logger.error(f"NFC tag {tag_id} not found in cache after {max_retries} attempts")
        raise NFCTagNotFoundException(tag_id)

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
