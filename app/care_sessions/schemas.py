from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class CreateCareSessionRequest(BaseModel):
    """Request to create a new care session"""
    tag_id: str 


class CompleteCareSessionRequest(BaseModel):
    """Request to complete/check-out a care session"""
    caregiver_notes: str


class CareSessionResponse(BaseModel):
    """Care session response"""
    id: UUID
    patient_id: UUID
    caregiver_id: UUID
    check_in_time: datetime
    check_out_time: datetime | None = None
    status: str  # in_progress | completed | cancelled
    caregiver_notes: str | None = None
    created_at: datetime
    updated_at: datetime


