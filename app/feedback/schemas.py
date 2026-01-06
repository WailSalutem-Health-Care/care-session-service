"""Feedback Pydantic schemas"""
from uuid import UUID
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    """Request to create feedback for a care session"""
    care_session_id: UUID
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")


class FeedbackResponse(BaseModel):
    """Feedback response"""
    id: UUID
    care_session_id: UUID
    patient_id: UUID
    rating: int
    created_at: datetime


class FeedbackListResponse(BaseModel):
    """Paginated list of feedbacks"""
    feedbacks: List[FeedbackResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
