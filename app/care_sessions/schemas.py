from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateCareSessionRequest(BaseModel):
    """Request to create a new care session"""
    tag_id: str
    session_id: Optional[str] = None


class CompleteCareSessionRequest(BaseModel):
    """Request to complete/check-out a care session"""
    caregiver_notes: str


class UpdateCareSessionRequest(BaseModel):
    """Request to update a care session (Admin only)"""
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    caregiver_notes: str | None = None
    status: str | None = None  # in_progress | completed


class CareSessionResponse(BaseModel):
    """Care session response"""
    id: UUID
    session_id: str
    patient_id: UUID
    caregiver_id: UUID
    check_in_time: datetime
    check_out_time: datetime | None = None
    status: str  # in_progress | completed
    caregiver_notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class CareSessionListResponse(BaseModel):
    """Paginated list of care sessions"""
    sessions: List[CareSessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int



