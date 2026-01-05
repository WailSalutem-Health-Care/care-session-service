from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class CareSessionReportItem(BaseModel):
    """Care session report item with cached names/emails."""
    id: UUID
    patient_id: UUID
    patient_full_name: Optional[str] = None
    patient_email: Optional[str] = None
    careplan_type: Optional[str] = None
    caregiver_id: UUID
    caregiver_full_name: Optional[str] = None
    caregiver_email: Optional[str] = None
    check_in_time: datetime
    check_out_time: datetime | None = None
    duration_minutes: Optional[int] = None
    status: str
    caregiver_notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class CareSessionReportPage(BaseModel):
    """Cursor-paginated report response."""
    items: List[CareSessionReportItem]
    next_cursor: Optional[str] = None


class CaregiverListItem(BaseModel):
    """Caregiver list item for selectors."""
    id: UUID
    full_name: str
    email: Optional[str] = None
    is_active: bool


class CaregiverPerformanceItem(BaseModel):
    """Aggregated caregiver performance."""
    caregiver_id: UUID
    caregiver_full_name: str
    caregiver_email: Optional[str] = None
    total_sessions: int
    completed_sessions: int
    avg_rating: Optional[float] = None
    avg_duration_minutes: Optional[float] = None
    status: str
