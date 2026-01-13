"""Care Session Repository Layer"""
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.care_sessions.models import CareSession
from app.db.repository import BaseRepository


class CareSessionRepository(BaseRepository):
    """Repository for care session database operations"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        super().__init__(db, tenant_schema, include_public=False)
    
    async def create(self, session: CareSession) -> CareSession:
        """Create a new care session"""
        await self._set_search_path()
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session
    
    async def get_by_id(self, session_id: UUID) -> Optional[CareSession]:
        """Get care session by ID"""
        await self._set_search_path()
        stmt = select(CareSession).where(CareSession.id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_active_by_patient(self, patient_id: UUID) -> Optional[CareSession]:
        """Get active care session for a patient"""
        await self._set_search_path()
        stmt = select(CareSession).where(
            and_(
                CareSession.patient_id == patient_id,
                CareSession.status == "in_progress"
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_caregiver(self, caregiver_id: UUID, limit: int = 100) -> List[CareSession]:
        """Get care sessions by caregiver"""
        await self._set_search_path()
        stmt = select(CareSession).where(
            CareSession.caregiver_id == caregiver_id
        ).order_by(CareSession.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_by_patient(self, patient_id: UUID, limit: int = 100) -> List[CareSession]:
        """Get care sessions by patient"""
        await self._set_search_path()
        stmt = select(CareSession).where(
            CareSession.patient_id == patient_id
        ).order_by(CareSession.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update(self, session: CareSession) -> CareSession:
        """Update care session"""
        await self._set_search_path()
        session.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(session)
        return session
    
    async def delete(self, session_id: UUID) -> bool:
        """Soft delete care session"""
        await self._set_search_path()
        session = await self.get_by_id(session_id)
        if session:
            session.deleted_at = datetime.utcnow()
            await self.db.commit()
            return True
        return False
    
    async def list_sessions(
        self,
        caregiver_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CareSession], int]:
        """List care sessions with filters and pagination."""
        await self._set_search_path()
        
        conditions = []
        if caregiver_id:
            conditions.append(CareSession.caregiver_id == caregiver_id)
        if patient_id:
            conditions.append(CareSession.patient_id == patient_id)
        if status:
            conditions.append(CareSession.status == status)
        if start_date:
            conditions.append(CareSession.check_in_time >= start_date)
        if end_date:
            conditions.append(CareSession.check_in_time <= end_date)
        
        base_query = select(CareSession)
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar()
        
        offset = (page - 1) * page_size
        stmt = base_query.order_by(CareSession.check_in_time.desc()).offset(offset).limit(page_size)
        
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        
        return sessions, total
