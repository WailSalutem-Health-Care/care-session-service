"""Feedback service layer for business logic"""
from uuid import UUID
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.feedback.models import Feedback
from app.feedback.repository import FeedbackRepository
from app.feedback.exceptions import (
    FeedbackAlreadyExistsException,
    FeedbackNotFoundException,
)


class FeedbackService:
    """Service layer for feedback business logic"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.repository = FeedbackRepository(db, tenant_schema)
    
    async def create_feedback(
        self,
        care_session_id: UUID,
        patient_id: UUID,
        rating: int,
    ) -> Feedback:
        """
        Create feedback for a care session.
        
        Business rules:
        - Patient can only create one feedback per session
        - Rating must be between 1-5
        """
        # Check if feedback already exists for this session
        existing_feedback = await self.repository.get_by_session_id(care_session_id)
        if existing_feedback:
            raise FeedbackAlreadyExistsException(care_session_id)
        
        # Create feedback
        feedback = Feedback(
            care_session_id=care_session_id,
            patient_id=patient_id,
            rating=rating,
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
