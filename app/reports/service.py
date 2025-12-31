from typing import List
from uuid import UUID
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.care_sessions.repository import CareSessionRepository
from app.care_sessions.schemas import CareSessionResponse
from app.care_sessions.exceptions import CareSessionNotFoundException


def to_response(session) -> CareSessionResponse:
    """Convert CareSession model to response schema."""
    return CareSessionResponse(
        id=session.id,
        patient_id=session.patient_id,
        caregiver_id=session.caregiver_id,
        check_in_time=session.check_in_time,
        check_out_time=session.check_out_time,
        status=session.status,
        caregiver_notes=session.caregiver_notes,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


class ReportsService:
    """Service for generating care session reports"""

    def __init__(self, repository: CareSessionRepository):
        self.repository = repository

    async def get_individual_session_report(self, session_id: UUID) -> CareSessionResponse:
        """Get report for a single care session"""
        session = await self.repository.get_by_id(session_id)
        if not session:
            raise CareSessionNotFoundException(str(session_id))
        return to_response(session)

    async def get_period_session_report(self, start_date: datetime, end_date: datetime, limit: int = 100, offset: int = 0) -> List[CareSessionResponse]:
        """Get reports for care sessions in a specific period"""
        sessions = await self.repository.get_sessions_in_period(start_date, end_date, limit, offset)
        return [to_response(s) for s in sessions]

    async def get_all_time_session_report(self, limit: int = 100, offset: int = 0) -> List[CareSessionResponse]:
        """Get reports for all care sessions"""
        sessions = await self.repository.get_all_sessions(limit, offset)
        return [to_response(s) for s in sessions]

    def generate_csv(self, sessions: List[CareSessionResponse]) -> BytesIO:
        """Generate CSV file from session data"""
        data = []
        for session in sessions:
            data.append({
                'ID': str(session.id),
                'Patient ID': str(session.patient_id),
                'Caregiver ID': str(session.caregiver_id),
                'Check In Time': session.check_in_time.isoformat() if session.check_in_time else '',
                'Check Out Time': session.check_out_time.isoformat() if session.check_out_time else '',
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

    def generate_pdf(self, sessions: List[CareSessionResponse], title: str) -> BytesIO:
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
            if y < 120:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            c.drawString(50, y, f"ID: {session.id}")
            c.drawString(50, y - 15, f"Patient ID: {session.patient_id}")
            c.drawString(50, y - 30, f"Caregiver ID: {session.caregiver_id}")
            c.drawString(50, y - 45, f"Check In: {session.check_in_time}")
            c.drawString(50, y - 60, f"Check Out: {session.check_out_time}")
            c.drawString(50, y - 75, f"Status: {session.status}")
            c.drawString(50, y - 90, f"Notes: {session.caregiver_notes or ''}")
            c.setLineWidth(0.5)
            c.line(line_x1, y - 100, line_x2, y - 100)
            y -= 120

        c.save()
        buffer.seek(0)
        return buffer
