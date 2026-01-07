"""Feedback service layer for business logic"""
from uuid import UUID
from typing import Tuple, List, Optional, Dict
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.feedback.models import Feedback
from app.feedback.repository import FeedbackRepository
from app.care_sessions.repository import CareSessionRepository
from app.feedback.exceptions import (
    FeedbackAlreadyExistsException,
    FeedbackNotFoundException,
)


class FeedbackService:
    """Service layer for feedback business logic"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.repository = FeedbackRepository(db, tenant_schema)
        self.care_session_repository = CareSessionRepository(db, tenant_schema)
    
    async def create_feedback(
        self,
        care_session_id: UUID,
        patient_id: UUID,
        rating: int,
        patient_feedback: Optional[str] = None,
    ) -> Feedback:
        """
        Create feedback for a care session.
        
        Business rules:
        - Patient can only create one feedback per session
        - Rating must be between 1-3 (1=Dissatisfied, 2=Neutral, 3=Satisfied)
        - Caregiver ID is looked up from the care session
        """
        # Check if feedback already exists for this session
        existing_feedback = await self.repository.get_by_session_id(care_session_id)
        if existing_feedback:
            raise FeedbackAlreadyExistsException(care_session_id)
        
        # Look up the care session to get caregiver_id
        care_session = await self.care_session_repository.get_by_id(care_session_id)
        if not care_session:
            raise ValueError(f"Care session {care_session_id} not found")
        
        # Create feedback
        feedback = Feedback(
            care_session_id=care_session_id,
            patient_id=patient_id,
            caregiver_id=care_session.caregiver_id,
            rating=rating,
            patient_feedback=patient_feedback,
        )
        
        return await self.repository.create(feedback)
    
    async def get_feedback_by_id(self, feedback_id: UUID) -> Feedback:
        """
        Get feedback by ID.
        """
        feedback = await self.repository.get_by_id(feedback_id)
        if not feedback:
            raise FeedbackNotFoundException(feedback_id)
        
        return feedback
    
    async def list_feedbacks(
        self,
        patient_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Feedback], int]:
        """
        List feedbacks with pagination and filters.
        
        Args:
            patient_id: Filter by patient (optional)
            page: Page number (1-indexed)
            page_size: Number of results per page
            
        Returns:
            Tuple of (feedbacks, total_count)
        """
        return await self.repository.list_feedbacks(
            patient_id=patient_id,
            page=page,
            page_size=page_size,
        )
    
    async def get_daily_averages(
        self,
        start_date: date,
        end_date: date,
    ) -> Tuple[List[Dict], List[Feedback]]:
        """
        Get daily average ratings for a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            Tuple of (daily_averages, all_feedbacks_in_range)
        """
        daily_averages = await self.repository.get_daily_averages(start_date, end_date)
        
        # Get all feedbacks in range for overall metrics
        all_feedbacks, _ = await self.repository.list_feedbacks(
            page=1,
            page_size=10000,  # Get all feedbacks in range
        )
        
        return daily_averages, all_feedbacks
    
    async def get_caregiver_weekly_metrics(
        self,
        caregiver_id: UUID,
        week_start: date,
        week_end: date,
    ) -> List[Feedback]:
        """
        Get caregiver's feedbacks for a specific week.
        
        Args:
            caregiver_id: Caregiver UUID
            week_start: Start of week (Monday)
            week_end: End of week (Sunday)
            
        Returns:
            List of Feedback objects
        """
        return await self.repository.get_caregiver_weekly_feedbacks(
            caregiver_id=caregiver_id,
            week_start=week_start,
            week_end=week_end,
        )
