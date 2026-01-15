"""Feedback repository for database operations"""
from uuid import UUID
from typing import Optional, Tuple, List, Dict
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, and_, cast, Date
from app.db.models import Feedback
from app.db.repository import BaseRepository


class FeedbackRepository(BaseRepository):
    """Repository for feedback database operations"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        super().__init__(db, tenant_schema, include_public=True)
    
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
    
    async def get_daily_averages(self, start_date: date, end_date: date) -> List[Dict]:
        """Get daily average ratings for a date range."""
        await self._set_search_path()
        
        date_col = cast(Feedback.created_at, Date)
        stmt = select(
            date_col.label('date'),
            func.avg(Feedback.rating).label('average_rating'),
            func.count(Feedback.id).label('total_feedbacks')
        ).where(
            and_(date_col >= start_date, date_col <= end_date)
        ).group_by(date_col).order_by(date_col)
        
        result = await self.db.execute(stmt)
        return [
            {'date': row.date, 'average_rating': float(row.average_rating), 'total_feedbacks': row.total_feedbacks}
            for row in result.all()
        ]
    
    async def get_caregiver_weekly_feedbacks(
        self, caregiver_id: UUID, week_start: date, week_end: date
    ) -> List[Feedback]:
        """Get all feedbacks for a caregiver within a week (Monday-Sunday)."""
        await self._set_search_path()
        
        date_col = cast(Feedback.created_at, Date)
        stmt = select(Feedback).where(
            and_(
                Feedback.caregiver_id == caregiver_id,
                date_col >= week_start,
                date_col <= week_end
            )
        ).order_by(Feedback.created_at)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_patient_average_rating(self, patient_id: UUID) -> Optional[float]:
        """Get patient's all-time average rating."""
        await self._set_search_path()
        
        stmt = select(func.avg(Feedback.rating)).where(Feedback.patient_id == patient_id)
        result = await self.db.execute(stmt)
        avg_rating = result.scalar()
        
        return float(avg_rating) if avg_rating is not None else None
    
    async def get_top_caregivers_of_week(self, week_start: date, week_end: date, limit: int = 3) -> List[Dict]:
        """Get top caregivers of the week based on average feedback rating."""
        await self._set_search_path()
        
        date_col = cast(Feedback.created_at, Date)
        stmt = select(
            Feedback.caregiver_id,
            func.avg(Feedback.rating).label('average_rating'),
            func.count(Feedback.id).label('total_feedbacks')
        ).where(
            and_(date_col >= week_start, date_col <= week_end)
        ).group_by(Feedback.caregiver_id).order_by(
            func.avg(Feedback.rating).desc()
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        return [
            {
                'caregiver_id': row.caregiver_id,
                'average_rating': float(row.average_rating),
                'total_feedbacks': row.total_feedbacks
            }
            for row in result.all()
        ]
    
    async def get_caregiver_average_rating(
        self,
        caregiver_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Tuple[Optional[float], int]:
        """Get caregiver's average rating for a date range."""
        await self._set_search_path()
        
        date_col = cast(Feedback.created_at, Date)
        stmt = select(
            func.avg(Feedback.rating).label('average_rating'),
            func.count(Feedback.id).label('total_feedbacks')
        ).where(
            and_(
                Feedback.caregiver_id == caregiver_id,
                date_col >= start_date,
                date_col <= end_date
            )
        )
        
        result = await self.db.execute(stmt)
        row = result.one()
        
        avg_rating = float(row.average_rating) if row.average_rating is not None else None
        return avg_rating, int(row.total_feedbacks)
    
    


