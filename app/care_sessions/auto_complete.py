"""Auto-complete sessions older than 2 hours"""
from datetime import datetime, timedelta
from app.db.models import CareSession
from app.utils.timezone import now_cet

AUTO_COMPLETE_HOURS = 2


def auto_complete_if_needed(session: CareSession) -> bool:
    """Auto-complete session if > 2 hours old (using CET timezone)."""
    if session.status != "in_progress":
        return False
    
    cutoff = now_cet() - timedelta(hours=AUTO_COMPLETE_HOURS)
    if session.check_in_time >= cutoff:
        return False
    
    # Auto-complete: mark as completed with CET timestamp
    session.status = "completed"
    session.check_out_time = now_cet()
    session.caregiver_notes = (
        f"{session.caregiver_notes or ''}\n"
        f"[AUTO-COMPLETED] Session exceeded {AUTO_COMPLETE_HOURS} hour timeout"
    ).strip()
    
    return True
