"""Care Session Repository Layer"""
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from app.care_sessions.models import CareSession


class CareSessionRepository:
    """Repository for care session database operations"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.tenant_schema = tenant_schema
    
    async def _set_search_path(self):
        """Set PostgreSQL search_path to tenant schema"""
        await self.db.execute(text(f"SET search_path TO {self.tenant_schema}"))
    
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
