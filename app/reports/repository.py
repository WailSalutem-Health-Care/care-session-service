"""Reports repository for read-only reporting queries."""
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text, func, case

from app.care_sessions.models import CareSession
from app.db.models import Patient, User


class ReportsRepository:
    """Repository for report-specific database operations."""

    def __init__(self, db: AsyncSession, tenant_schema: str):
        self.db = db
        self.tenant_schema = tenant_schema

    async def _set_search_path(self):
        """Set PostgreSQL search_path to tenant schema"""
        await self.db.execute(text(f'SET search_path TO "{self.tenant_schema}"'))

    async def get_by_id(self, session_id: UUID) -> Optional[CareSession]:
        """Get care session by ID"""
        await self._set_search_path()
        stmt = select(CareSession).where(CareSession.id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

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

    async def get_caregiver_avg_ratings(
        self,
        caregiver_ids: List[UUID],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[UUID, float]:
        """Fetch average ratings per caregiver from feedback table."""
        if not caregiver_ids:
            return {}
        await self._set_search_path()

        clauses = ["cs.caregiver_id = ANY(:caregiver_ids)"]
        params: Dict[str, object] = {"caregiver_ids": caregiver_ids}
        if start_date:
            clauses.append("f.created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("f.created_at <= :end_date")
            params["end_date"] = end_date

        stmt = text(
            f"""
            SELECT cs.caregiver_id, AVG(f.rating)::float AS avg_rating
            FROM feedback f
            JOIN care_sessions cs ON cs.id = f.care_session_id
            WHERE {' AND '.join(clauses)}
            GROUP BY cs.caregiver_id
            """
        )
        result = await self.db.execute(stmt, params)
        return {row.caregiver_id: float(row.avg_rating) for row in result.all()}

    async def get_patient_list(self, limit: int = 100, offset: int = 0) -> List[Patient]:
        """List patients for selector dropdowns."""
        await self._set_search_path()
        stmt = (
            select(Patient)
            .where(Patient.deleted_at.is_(None))
            .order_by(Patient.last_name.asc(), Patient.first_name.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_patient_summary(self, patient_id: UUID) -> Dict[str, object]:
        """Aggregate patient summary metrics."""
        await self._set_search_path()
        summary_stmt = text(
            """
            SELECT
                COUNT(cs.id) AS total_sessions,
                COUNT(DISTINCT cs.caregiver_id) AS distinct_caregivers
            FROM care_sessions cs
            WHERE cs.patient_id = :patient_id
              AND cs.deleted_at IS NULL
            """
        )
        summary_result = await self.db.execute(summary_stmt, {"patient_id": patient_id})
        summary = summary_result.mappings().first() or {}

        rating_stmt = text(
            """
            SELECT AVG(f.rating)::float AS avg_rating
            FROM feedback f
            WHERE f.patient_id = :patient_id
              AND f.deleted_at IS NULL
            """
        )
        rating_result = await self.db.execute(rating_stmt, {"patient_id": patient_id})
        avg_rating = rating_result.scalar()

        return {
            "total_sessions": int(summary.get("total_sessions") or 0),
            "distinct_caregivers": int(summary.get("distinct_caregivers") or 0),
            "avg_rating": float(avg_rating) if avg_rating is not None else None,
        }

    async def get_patient_sessions(
        self,
        patient_id: UUID,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, object]], int]:
        """List patient sessions with feedback ratings."""
        await self._set_search_path()
        where_clauses = ["cs.patient_id = :patient_id", "cs.deleted_at IS NULL"]
        params: Dict[str, object] = {"patient_id": patient_id, "limit": limit, "offset": offset}
        if start_date:
            where_clauses.append("cs.check_in_time >= :start_date")
            params["start_date"] = start_date
        if end_date:
            where_clauses.append("cs.check_in_time <= :end_date")
            params["end_date"] = end_date

        count_stmt = text(
            f"""
            SELECT COUNT(*) AS total
            FROM care_sessions cs
            WHERE {' AND '.join(where_clauses)}
            """
        )
        total_result = await self.db.execute(count_stmt, params)
        total = int(total_result.scalar() or 0)

        data_stmt = text(
            f"""
            SELECT
                cs.id,
                cs.caregiver_id,
                cs.check_in_time,
                cs.check_out_time,
                cs.status,
                cs.caregiver_notes,
                f.rating AS rating,
                f.patient_feedback AS feedback_comment,
                f.created_at AS feedback_date
            FROM care_sessions cs
            LEFT JOIN feedback f ON f.care_session_id = cs.id AND f.deleted_at IS NULL
            WHERE {' AND '.join(where_clauses)}
            ORDER BY cs.check_in_time DESC, cs.id DESC
            LIMIT :limit OFFSET :offset
            """
        )
        result = await self.db.execute(data_stmt, params)
        rows = [dict(row._mapping) for row in result]
        return rows, total
