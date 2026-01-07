"""Feedback Pydantic schemas"""
from uuid import UUID
from datetime import datetime
from typing import List, Dict
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
    caregiver_id: UUID
    rating: int
    satisfaction_level: str  # VERY_DISSATISFIED, DISSATISFIED, NEUTRAL, SATISFIED, VERY_SATISFIED
    created_at: datetime


class FeedbackMetrics(BaseModel):
    """Satisfaction metrics"""
    average_rating: float
    satisfaction_index: float  # 0-100 scale
    total_feedbacks: int
    distribution: Dict[str, float]  # Percentage distribution of star ratings
    satisfaction_levels: Dict[str, int]  # Count by satisfaction level


class FeedbackListResponse(BaseModel):
    """Paginated list of feedbacks with metrics"""
    feedbacks: List[FeedbackResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    metrics: FeedbackMetrics


class DailyAverageResponse(BaseModel):
    """Daily average feedback rating"""
    date: str  # YYYY-MM-DD
    average_rating: float
    total_feedbacks: int
    satisfaction_index: float  # 0-100 scale


class DailyAverageListResponse(BaseModel):
    """List of daily average feedback ratings"""
    daily_averages: List[DailyAverageResponse]
    overall_metrics: FeedbackMetrics


class CaregiverWeeklyMetrics(BaseModel):
    """Caregiver's weekly feedback metrics"""
    caregiver_id: UUID
    week_start: str  # YYYY-MM-DD (Monday)
    week_end: str  # YYYY-MM-DD (Sunday)
    average_rating: float
    total_feedbacks: int
    satisfaction_index: float  # 0-100 scale
    distribution: Dict[str, float]  # Percentage distribution of star ratings
    satisfaction_levels: Dict[str, int]  # Count by satisfaction level


class CaregiverFeedbackItem(BaseModel):
    """Feedback item for caregiver reports."""
    id: UUID
    caregiver_id: UUID
    caregiver_full_name: str | None = None
    patient_id: UUID
    patient_full_name: str | None = None
    rating: int
    comment: str | None = None
    session_date: datetime
    feedback_date: datetime


class CaregiverFeedbackPage(BaseModel):
    """Paginated caregiver feedback."""
    items: List[CaregiverFeedbackItem]
    total: int
    limit: int
    offset: int
