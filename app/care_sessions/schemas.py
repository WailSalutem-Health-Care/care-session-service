from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateCareSessionRequest(BaseModel):
    tag_id: str
    session_id: Optional[str] = None


class CompleteCareSessionRequest(BaseModel):
    caregiver_notes: str


class UpdateCareSessionRequest(BaseModel):
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    caregiver_notes: Optional[str] = None
    status: Optional[str] = None


class CareSessionResponse(BaseModel):
    id: UUID
    session_id: str
    patient_id: UUID
    caregiver_id: UUID
    check_in_time: datetime
    check_out_time: Optional[datetime] = None
    status: str  # in_progress | completed
    caregiver_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class CareSessionListResponse(BaseModel):
    sessions: List[CareSessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int



