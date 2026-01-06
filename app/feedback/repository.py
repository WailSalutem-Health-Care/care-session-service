"""Feedback repository for database operations"""
from uuid import UUID
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from app.feedback.models import Feedback


class FeedbackRepository:
    """Repository for feedback database operations"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.tenant_schema = tenant_schema
    
    async def _set_search_path(self):
        """Set PostgreSQL search path to tenant schema"""
        await self.db.execute(text(f'SET search_path TO "{self.tenant_schema}", public'))
    
    async def create(self, feedback: Feedback) -> Feedback:
        """Create new feedback"""
        await self._set_search_path()
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback
    
    async def get_by_id(self, feedback_id: UUID) -> Optional[Feedback]:
        """Get feedback by ID"""
        await self._set_search_path()
        stmt = select(Feedback).where(Feedback.id == feedback_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_session_id(self, care_session_id: UUID) -> Optional[Feedback]:
        """Get feedback by care session ID"""
        await self._set_search_path()
        stmt = select(Feedback).where(Feedback.care_session_id == care_session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_feedbacks(
        self,
        patient_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Feedback], int]:
        """
        List feedbacks with pagination and optional filters.
        
        Args:
            patient_id: Filter by patient (optional)
            page: Page number (1-indexed)
            page_size: Number of results per page
            
        Returns:
            Tuple of (feedbacks, total_count)
        """
        await self._set_search_path()
        
        # Build base query
        stmt = select(Feedback)
        count_stmt = select(func.count()).select_from(Feedback)
        
        # Apply filters
        if patient_id:
            stmt = stmt.where(Feedback.patient_id == patient_id)
            count_stmt = count_stmt.where(Feedback.patient_id == patient_id)
        
        # Get total count
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar()
        
        # Apply pagination and ordering
        stmt = stmt.order_by(Feedback.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        
        # Execute query
        result = await self.db.execute(stmt)
        feedbacks = list(result.scalars().all())
        
        return feedbacks, total
    
    async def delete(self, feedback: Feedback) -> None:
        """Delete feedback"""
        await self._set_search_path()
        await self.db.delete(feedback)
        await self.db.commit()
