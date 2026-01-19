"""Small, test-friendly shim for publishing care-session events.

Default implementation is a no-op so imports succeed in tests. Replace
with a real broker implementation in production.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def publish_care_session_event(event_type: str, session_data: dict, tenant_schema: Optional[str] = None) -> None:
    """Publish a care session event to the message broker (no-op default)."""
    logger.debug("publish_care_session_event called: %s %s", event_type, session_data)
    # Intentionally a no-op here.
    return None
