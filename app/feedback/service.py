"""Feedback service layer for business logic"""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.feedback.models import Feedback
from app.feedback.repository import FeedbackRepository
from app.feedback.exceptions import (
    FeedbackAlreadyExistsException,
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

