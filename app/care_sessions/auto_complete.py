"""Auto-complete sessions older than 2 hours"""
from datetime import datetime, timedelta
from app.db.models import CareSession

AUTO_COMPLETE_HOURS = 2


def auto_complete_if_needed(session: CareSession) -> bool:
    """Auto-complete session if > 2 hours old."""
    if session.status != "in_progress":
        return False
    
    cutoff = datetime.utcnow() - timedelta(hours=AUTO_COMPLETE_HOURS)
    if session.check_in_time >= cutoff:
        return False
    
    # Auto-complete: mark as completed
    session.status = "completed"
    session.check_out_time = datetime.utcnow()
    session.caregiver_notes = (
        f"{session.caregiver_notes or ''}\n"
        f"[AUTO-COMPLETED] Session exceeded {AUTO_COMPLETE_HOURS} hour timeout"
    ).strip()
    
    return True
