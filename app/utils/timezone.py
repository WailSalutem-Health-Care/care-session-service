"""Timezone utilities for CET (Central European Time) operations"""

from datetime import datetime
from typing import Optional

import pytz

# European timezone (handles CET/CEST automatically)
EUROPE_TZ = pytz.timezone("Europe/Paris")


def now_cet() -> datetime:
    """
    Get current time in CET (Central European Time).
    Handles CET/CEST (daylight saving time) automatically.

    Returns:
        Naive datetime in CET timezone
    """
    return datetime.now(EUROPE_TZ).replace(tzinfo=None)


def convert_to_cet(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert UTC naive datetime to CET (Europe/Paris) for API display.

    Args:
        dt: Naive datetime assumed to be in UTC, or timezone-aware datetime

    Returns:
        Naive datetime in CET timezone, or None if input is None
    """
    import logging

    logger = logging.getLogger(__name__)

    if dt is None:
        return None

    try:
        # If already timezone-aware, convert to CET
        if dt.tzinfo is not None:
            logger.debug(f"Converting timezone-aware datetime to CET: {dt} (tzinfo={dt.tzinfo})")
            cet_dt = dt.astimezone(EUROPE_TZ)
            return cet_dt.replace(tzinfo=None)

        # If naive, assume it's UTC and convert to CET
        logger.debug(f"Converting naive datetime (assumed UTC) to CET: {dt}")
        utc_dt = pytz.utc.localize(dt)
        cet_dt = utc_dt.astimezone(EUROPE_TZ)
        return cet_dt.replace(tzinfo=None)
    except Exception as e:
        logger.error(
            f"Error converting datetime to CET: {e}, dt={dt}, dt.tzinfo={getattr(dt, 'tzinfo', 'N/A')}", exc_info=True
        )
        raise
