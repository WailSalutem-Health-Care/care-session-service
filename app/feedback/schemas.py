"""Feedback Pydantic schemas"""
from uuid import UUID
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    """Request to create feedback for a care session"""
    care_session_id: UUID
    rating: int = Field(..., ge=1, le=3, description="Rating: 1=Dissatisfied, 2=Neutral, 3=Satisfied")
    patient_feedback: Optional[str] = Field(None, description="Optional text feedback from patient")


class FeedbackResponse(BaseModel):
    """Feedback response"""
    id: UUID
    care_session_id: UUID
    patient_id: UUID
    caregiver_id: UUID
    rating: int
    patient_feedback: Optional[str]
    satisfaction_level: str  # DISSATISFIED, NEUTRAL, SATISFIED
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
    count: int  # Number of items in current response
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
    count: int  # Number of daily average items
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


class PatientAverageRatingResponse(BaseModel):
    """Patient's all-time average rating"""
    patient_id: UUID
    average_rating: Optional[float]
    satisfaction_index: Optional[float]  # 0-100 scale
    total_feedbacks: int


class TopCaregiverItem(BaseModel):
    """Top caregiver of the week"""
    caregiver_id: UUID
    average_rating: float
    satisfaction_index: float  # 0-100 scale
    total_feedbacks: int
    rank: int


class TopCaregiversResponse(BaseModel):
    """Top 3 caregivers of the week"""
    week_start: str  # YYYY-MM-DD (Monday)
    week_end: str  # YYYY-MM-DD (Sunday)
    top_caregivers: List[TopCaregiverItem]


class CaregiverAverageRatingResponse(BaseModel):
    """Caregiver's average rating for a period"""
    caregiver_id: UUID
    period: str  # 'daily', 'weekly', 'monthly'
    start_date: str
    end_date: str
    average_rating: Optional[float]
    total_feedbacks: int

