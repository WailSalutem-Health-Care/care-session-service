"""Timezone utilities for converting UTC to European timezone"""
from datetime import datetime
import pytz

# European timezone (handles CET/CEST automatically)
EUROPE_TZ = pytz.timezone('Europe/Paris')


def convert_to_cet(dt: datetime | None) -> datetime | None:
    """
    Convert UTC naive datetime to CET (Europe/Paris) for API display.
    
    Args:
        dt: Naive datetime assumed to be in UTC, or None
        
    Returns:
        Naive datetime in CET timezone, or None if input is None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume it's UTC and convert to Europe/Paris
        utc_dt = pytz.utc.localize(dt)
        cet_dt = utc_dt.astimezone(EUROPE_TZ)
        # Return as naive CET datetime
        return cet_dt.replace(tzinfo=None)
    return dt
