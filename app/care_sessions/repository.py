"""Care Session Repository Layer"""
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text, func, case
from app.care_sessions.models import CareSession
from app.db.models import Patient, User


class CareSessionRepository:
    """Repository for care session database operations"""
    
    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.tenant_schema = tenant_schema
    
    async def _set_search_path(self):
        """Set PostgreSQL search_path to tenant schema"""
        await self.db.execute(text(f'SET search_path TO "{self.tenant_schema}"'))
    
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
    
    async def get_sessions_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int | None = 100,
        offset: int | None = 0,
        cursor_time: datetime | None = None,
        cursor_id: UUID | None = None,
    ) -> List[CareSession]:
        """Get care sessions within a date range"""
        await self._set_search_path()
        stmt = select(CareSession).where(
            and_(
                CareSession.check_in_time >= start_date,
                CareSession.check_in_time <= end_date,
                CareSession.deleted_at.is_(None)
            )
        )
        if cursor_time is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    CareSession.check_in_time < cursor_time,
                    and_(
                        CareSession.check_in_time == cursor_time,
                        CareSession.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(CareSession.check_in_time.desc(), CareSession.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_all_sessions(
        self,
        limit: int | None = 100,
        offset: int | None = 0,
        cursor_time: datetime | None = None,
        cursor_id: UUID | None = None,
    ) -> List[CareSession]:
        """Get all care sessions"""
        await self._set_search_path()
        stmt = select(CareSession).where(
            CareSession.deleted_at.is_(None)
        )
        if cursor_time is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    CareSession.created_at < cursor_time,
                    and_(
                        CareSession.created_at == cursor_time,
                        CareSession.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(CareSession.created_at.desc(), CareSession.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_patients_by_ids(self, patient_ids: List[UUID]) -> Dict[UUID, Patient]:
        """Fetch patients by IDs from the tenant cache."""
        if not patient_ids:
            return {}
        await self._set_search_path()
        stmt = select(Patient).where(Patient.id.in_(patient_ids))
        result = await self.db.execute(stmt)
        patients = result.scalars().all()
        return {patient.id: patient for patient in patients}

    async def get_users_by_ids(self, user_ids: List[UUID]) -> Dict[UUID, User]:
        """Fetch users by IDs from the tenant cache."""
        if not user_ids:
            return {}
        await self._set_search_path()
        stmt = select(User).where(User.id.in_(user_ids))
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        return {user.id: user for user in users}

    async def get_caregiver_list(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List caregivers for selection."""
        await self._set_search_path()
        stmt = (
            select(User)
            .where(
                and_(
                    func.lower(User.role) == "caregiver",
                    User.deleted_at.is_(None),
                )
            )
            .order_by(User.last_name.asc(), User.first_name.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_caregiver_performance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        caregiver_id: Optional[UUID] = None,
    ):
        """Aggregate caregiver performance from care sessions."""
        await self._set_search_path()
        join_conditions = [
            CareSession.caregiver_id == User.id,
            CareSession.deleted_at.is_(None),
        ]
        if start_date:
            join_conditions.append(CareSession.check_in_time >= start_date)
        if end_date:
            join_conditions.append(CareSession.check_in_time <= end_date)

        duration_minutes = func.extract("epoch", CareSession.check_out_time - CareSession.check_in_time) / 60.0
        avg_duration = func.avg(
            case(
                (CareSession.check_out_time.is_not(None), duration_minutes),
                else_=None,
            )
        )
        completed_count = func.sum(
            case(
                (CareSession.status == "completed", 1),
                else_=0,
            )
        )

        stmt = (
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.email,
                User.is_active,
                func.count(CareSession.id).label("total_sessions"),
                completed_count.label("completed_sessions"),
                avg_duration.label("avg_duration_minutes"),
            )
            .select_from(User)
            .outerjoin(CareSession, and_(*join_conditions))
            .where(
                and_(
                    func.lower(User.role) == "caregiver",
                    User.deleted_at.is_(None),
                )
            )
            .group_by(User.id, User.first_name, User.last_name, User.email, User.is_active)
            .order_by(User.last_name.asc(), User.first_name.asc())
        )
        if caregiver_id:
            stmt = stmt.where(User.id == caregiver_id)

        result = await self.db.execute(stmt)
        return result.all()
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
