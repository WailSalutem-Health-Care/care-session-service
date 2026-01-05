from typing import List, Optional, Tuple, Dict
from uuid import UUID
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.care_sessions.repository import CareSessionRepository
from app.reports.schemas import CareSessionReportItem, CaregiverListItem, CaregiverPerformanceItem
from app.care_sessions.exceptions import CareSessionNotFoundException
from app.db.models import Patient, User


def to_report_response(session, patient: Optional[Patient], caregiver: Optional[User]) -> CareSessionReportItem:
    """Convert CareSession model to report response schema."""
    duration_minutes = None
    if session.check_in_time and session.check_out_time:
        duration_minutes = int((session.check_out_time - session.check_in_time).total_seconds() / 60)
    patient_full_name = None
    if patient:
        patient_full_name = " ".join([name for name in [patient.first_name, patient.last_name] if name])
    caregiver_full_name = None
    if caregiver:
        caregiver_full_name = " ".join([name for name in [caregiver.first_name, caregiver.last_name] if name])
    return CareSessionReportItem(
        id=session.id,
        patient_id=session.patient_id,
        patient_full_name=patient_full_name,
        patient_email=patient.email if patient else None,
        careplan_type=patient.careplan_type if patient else None,
        caregiver_id=session.caregiver_id,
        caregiver_full_name=caregiver_full_name,
        caregiver_email=caregiver.email if caregiver else None,
        check_in_time=session.check_in_time,
        check_out_time=session.check_out_time,
        duration_minutes=duration_minutes,
        status=session.status,
        caregiver_notes=session.caregiver_notes,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


class ReportsService:
    """Service for generating care session reports"""

    def __init__(self, repository: CareSessionRepository):
        self.repository = repository

    def _parse_cursor(self, cursor: str) -> Tuple[datetime, UUID]:
        parts = cursor.split("|", 1)
        if len(parts) != 2:
            raise ValueError("Invalid cursor")
        cursor_time = datetime.fromisoformat(parts[0])
        cursor_id = UUID(parts[1])
        return cursor_time, cursor_id

    def _build_cursor(self, cursor_time: datetime, cursor_id: UUID) -> str:
        return f"{cursor_time.isoformat()}|{cursor_id}"

    def _format_full_name(self, first_name: Optional[str], last_name: Optional[str]) -> str:
        return " ".join([name for name in [first_name, last_name] if name])

    async def _load_cache_maps(self, sessions) -> Tuple[Dict[UUID, Patient], Dict[UUID, User]]:
        patient_ids = {session.patient_id for session in sessions}
        caregiver_ids = {session.caregiver_id for session in sessions}
        patients = await self.repository.get_patients_by_ids(list(patient_ids))
        caregivers = await self.repository.get_users_by_ids(list(caregiver_ids))
        return patients, caregivers

    async def get_individual_session_report(self, session_id: UUID) -> CareSessionReportItem:
        """Get report for a single care session"""
        session = await self.repository.get_by_id(session_id)
        if not session:
            raise CareSessionNotFoundException(str(session_id))
        patients, caregivers = await self._load_cache_maps([session])
        return to_report_response(
            session,
            patients.get(session.patient_id),
            caregivers.get(session.caregiver_id),
        )

    async def get_period_session_report(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int | None = 100,
        cursor: Optional[str] = None,
    ) -> Tuple[List[CareSessionReportItem], Optional[str]]:
        """Get reports for care sessions in a specific period"""
        cursor_time = None
        cursor_id = None
        if cursor:
            cursor_time, cursor_id = self._parse_cursor(cursor)
        fetch_limit = limit + 1 if limit is not None else None
        sessions = await self.repository.get_sessions_in_period(
            start_date,
            end_date,
            fetch_limit,
            None,
            cursor_time,
            cursor_id,
        )
        next_cursor = None
        if limit is not None and len(sessions) > limit:
            last = sessions[limit - 1]
            next_cursor = self._build_cursor(last.check_in_time, last.id)
            sessions = sessions[:limit]
        patients, caregivers = await self._load_cache_maps(sessions)
        items = [
            to_report_response(
                session,
                patients.get(session.patient_id),
                caregivers.get(session.caregiver_id),
            )
            for session in sessions
        ]
        return items, next_cursor

    async def get_caregiver_list(self, limit: int = 100, offset: int = 0) -> List[CaregiverListItem]:
        caregivers = await self.repository.get_caregiver_list(limit, offset)
        return [
            CaregiverListItem(
                id=caregiver.id,
                full_name=self._format_full_name(caregiver.first_name, caregiver.last_name),
                email=caregiver.email,
                is_active=caregiver.is_active,
            )
            for caregiver in caregivers
        ]

    async def get_caregiver_performance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        caregiver_id: Optional[UUID] = None,
    ) -> List[CaregiverPerformanceItem]:
        rows = await self.repository.get_caregiver_performance(start_date, end_date, caregiver_id)
        items: List[CaregiverPerformanceItem] = []
        for row in rows:
            full_name = self._format_full_name(row.first_name, row.last_name)
            status = "Active" if row.is_active else "Inactive"
            items.append(
                CaregiverPerformanceItem(
                    caregiver_id=row.id,
                    caregiver_full_name=full_name,
                    caregiver_email=row.email,
                    total_sessions=int(row.total_sessions or 0),
                    completed_sessions=int(row.completed_sessions or 0),
                    avg_rating=None,
                    avg_duration_minutes=float(row.avg_duration_minutes) if row.avg_duration_minutes is not None else None,
                    status=status,
                )
            )
        return items

    def generate_caregiver_csv(self, caregivers: List[CaregiverPerformanceItem]) -> BytesIO:
        """Generate CSV file from caregiver performance data."""
        data = []
        for caregiver in caregivers:
            data.append({
                "Caregiver ID": str(caregiver.caregiver_id),
                "Caregiver Name": caregiver.caregiver_full_name,
                "Caregiver Email": caregiver.caregiver_email or "",
                "Total Sessions": caregiver.total_sessions,
                "Completed Sessions": caregiver.completed_sessions,
                "Avg Rating": caregiver.avg_rating if caregiver.avg_rating is not None else "",
                "Avg Duration (Minutes)": caregiver.avg_duration_minutes if caregiver.avg_duration_minutes is not None else "",
                "Status": caregiver.status,
            })
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)
        return buffer

    def generate_caregiver_pdf(self, caregivers: List[CaregiverPerformanceItem], title: str) -> BytesIO:
        """Generate PDF file from caregiver performance data."""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        line_x1 = 50
        line_x2 = width - 50

        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, title)

        y = height - 80
        c.setFont("Helvetica", 10)

        for caregiver in caregivers:
            if y < 200:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            c.drawString(50, y, f"Caregiver ID: {caregiver.caregiver_id}")
            c.drawString(50, y - 15, f"Name: {caregiver.caregiver_full_name}")
            c.drawString(50, y - 30, f"Email: {caregiver.caregiver_email or ''}")
            c.drawString(50, y - 45, f"Total Sessions: {caregiver.total_sessions}")
            c.drawString(50, y - 60, f"Completed Sessions: {caregiver.completed_sessions}")
            c.drawString(50, y - 75, f"Avg Rating: {caregiver.avg_rating if caregiver.avg_rating is not None else ''}")
            c.drawString(50, y - 90, f"Avg Duration (Minutes): {caregiver.avg_duration_minutes if caregiver.avg_duration_minutes is not None else ''}")
            c.drawString(50, y - 105, f"Status: {caregiver.status}")
            c.setLineWidth(0.5)
            c.line(line_x1, y - 120, line_x2, y - 120)
            y -= 140

        c.save()
        buffer.seek(0)
        return buffer

    async def get_all_time_session_report(
        self,
        limit: int | None = 100,
        cursor: Optional[str] = None,
    ) -> Tuple[List[CareSessionReportItem], Optional[str]]:
        """Get reports for all care sessions"""
        cursor_time = None
        cursor_id = None
        if cursor:
            cursor_time, cursor_id = self._parse_cursor(cursor)
        fetch_limit = limit + 1 if limit is not None else None
        sessions = await self.repository.get_all_sessions(
            fetch_limit,
            None,
            cursor_time,
            cursor_id,
        )
        next_cursor = None
        if limit is not None and len(sessions) > limit:
            last = sessions[limit - 1]
            next_cursor = self._build_cursor(last.created_at, last.id)
            sessions = sessions[:limit]
        patients, caregivers = await self._load_cache_maps(sessions)
        items = [
            to_report_response(
                session,
                patients.get(session.patient_id),
                caregivers.get(session.caregiver_id),
            )
            for session in sessions
        ]
        return items, next_cursor

    def generate_csv(self, sessions: List[CareSessionReportItem]) -> BytesIO:
        """Generate CSV file from session data"""
        data = []
        for session in sessions:
            data.append({
                'ID': str(session.id),
                'Patient ID': str(session.patient_id),
                'Patient Name': session.patient_full_name or '',
                'Patient Email': session.patient_email or '',
                'Careplan Type': session.careplan_type or '',
                'Caregiver ID': str(session.caregiver_id),
                'Caregiver Name': session.caregiver_full_name or '',
                'Caregiver Email': session.caregiver_email or '',
                'Check In Time': session.check_in_time.isoformat() if session.check_in_time else '',
                'Check Out Time': session.check_out_time.isoformat() if session.check_out_time else '',
                'Duration (Minutes)': session.duration_minutes if session.duration_minutes is not None else '',
                'Status': session.status,
                'Caregiver Notes': session.caregiver_notes or '',
                'Created At': session.created_at.isoformat(),
                'Updated At': session.updated_at.isoformat() if session.updated_at else '',
            })
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)
        return buffer

    def generate_pdf(self, sessions: List[CareSessionReportItem], title: str) -> BytesIO:
        """Generate PDF file from session data"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        line_x1 = 50
        line_x2 = width - 50

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, title)

        y = height - 80
        c.setFont("Helvetica", 10)

        for session in sessions:
            if y < 250:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            c.drawString(50, y, f"ID: {session.id}")
            c.drawString(50, y - 15, f"Patient ID: {session.patient_id}")
            c.drawString(50, y - 30, f"Patient Name: {session.patient_full_name or ''}")
            c.drawString(50, y - 45, f"Patient Email: {session.patient_email or ''}")
            c.drawString(50, y - 60, f"Careplan Type: {session.careplan_type or ''}")
            c.drawString(50, y - 75, f"Caregiver ID: {session.caregiver_id}")
            c.drawString(50, y - 90, f"Caregiver Name: {session.caregiver_full_name or ''}")
            c.drawString(50, y - 105, f"Caregiver Email: {session.caregiver_email or ''}")
            c.drawString(50, y - 120, f"Check In: {session.check_in_time}")
            c.drawString(50, y - 135, f"Check Out: {session.check_out_time}")
            c.drawString(50, y - 150, f"Duration (Minutes): {session.duration_minutes if session.duration_minutes is not None else ''}")
            c.drawString(50, y - 165, f"Status: {session.status}")
            c.drawString(50, y - 180, f"Notes: {session.caregiver_notes or ''}")
            c.setLineWidth(0.5)
            c.line(line_x1, y - 195, line_x2, y - 195)
            y -= 215

        c.save()
        buffer.seek(0)
        return buffer
