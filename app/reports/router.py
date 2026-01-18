from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.reports.service import ReportsService
from app.reports.schemas import (
    CareSessionReportPage,
    CareSessionReportItem,
    CaregiverListItem,
    CaregiverPerformanceItem,
    PatientListItem,
    PatientSummary,
    PatientSessionPage,
    FeedbackReportPage,
    FeedbackReportSummary,
    CaregiverFeedbackPage,
)
from app.reports.repository import ReportsRepository
from app.auth.middleware import JWTPayload, verify_token, check_permission
from app.utils.timezone import convert_to_cet


def get_reports_service(db: AsyncSession = Depends(get_db), jwt_payload: JWTPayload = Depends(verify_token)) -> ReportsService:
    """Dependency to get ReportsService"""
    repository = ReportsRepository(db, jwt_payload.tenant_schema)
    return ReportsService(repository)


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


def _resolve_period_range(period: str) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    if period == "day":
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        return start, end
    if period == "week":
        start = datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return start, end
    if period == "month":
        start = datetime(now.year, now.month, 1)
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1) - timedelta(microseconds=1)
        else:
            end = datetime(start.year, start.month + 1, 1) - timedelta(microseconds=1)
        return start, end
    raise ValueError("Invalid period")


@router.get("/sessions/period", response_model=CareSessionReportPage)
async def get_period_session_report(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    period: str | None = Query(None, enum=["day", "week", "month"]),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Get reports for care sessions in a specific time period"""
    check_permission(jwt_payload, "care-session:report")
    if period:
        try:
            start_date, end_date = _resolve_period_range(period)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period")
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="start_date and end_date are required when period is not provided")
    try:
        items, next_cursor = await service.get_period_session_report(start_date, end_date, limit, cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return CareSessionReportPage(items=items, next_cursor=next_cursor)


@router.get("/sessions/all", response_model=CareSessionReportPage)
async def get_all_time_session_report(
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Get reports for all care sessions"""
    check_permission(jwt_payload, "care-session:report")
    try:
        items, next_cursor = await service.get_all_time_session_report(limit, cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return CareSessionReportPage(items=items, next_cursor=next_cursor)


@router.get("/sessions/period/download")
async def download_period_session_report(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    period: str | None = Query(None, enum=["day", "week", "month"]),
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download reports for care sessions in a specific time period"""
    check_permission(jwt_payload, "care-session:report")
    if period:
        try:
            start_date, end_date = _resolve_period_range(period)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period")
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="start_date and end_date are required when period is not provided")
    sessions, _ = await service.get_period_session_report(start_date, end_date, None, None)

    if format == "csv":
        csv_buffer = service.generate_csv(sessions)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=sessions_{start_date.date()}_to_{end_date.date()}.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_pdf(sessions, f"Care Sessions Report - {start_date.date()} to {end_date.date()}")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=sessions_{start_date.date()}_to_{end_date.date()}.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/sessions/all/download")
async def download_all_time_session_report(
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download reports for all care sessions"""
    check_permission(jwt_payload, "care-session:report")
    sessions, _ = await service.get_all_time_session_report(None, None)

    if format == "csv":
        csv_buffer = service.generate_csv(sessions)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=all_sessions.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_pdf(sessions, "All Care Sessions Report")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=all_sessions.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/sessions/{session_id}", response_model=CareSessionReportItem)
async def get_individual_session_report(
    session_id: UUID,
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Get report for an individual care session"""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_individual_session_report(session_id)


@router.get("/sessions/{session_id}/download")
async def download_individual_session_report(
    session_id: UUID,
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download report for an individual care session"""
    check_permission(jwt_payload, "care-session:report")
    session = await service.get_individual_session_report(session_id)
    sessions = [session]

    if format == "csv":
        csv_buffer = service.generate_csv(sessions)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_pdf(sessions, f"Care Session Report - {session_id}")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=session_{session_id}.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/caregivers", response_model=list[CaregiverListItem])
async def list_caregivers(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """List caregivers for selector dropdowns."""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_caregiver_list(limit, offset)


@router.get("/caregivers/performance", response_model=list[CaregiverPerformanceItem])
async def caregiver_performance(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Aggregate caregiver performance metrics."""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_caregiver_performance(start_date, end_date)


@router.get("/caregivers/download")
async def download_caregiver_performance(
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download caregiver performance report."""
    check_permission(jwt_payload, "care-session:report")
    caregivers = await service.get_caregiver_performance(start_date, end_date)

    if format == "csv":
        csv_buffer = service.generate_caregiver_csv(caregivers)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=caregiver_performance.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_caregiver_pdf(caregivers, "Caregiver Performance Report")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=caregiver_performance.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/caregivers/{caregiver_id}/download")
async def download_caregiver_report(
    caregiver_id: UUID,
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download report for a single caregiver."""
    check_permission(jwt_payload, "care-session:report")
    caregivers = await service.get_caregiver_performance(start_date, end_date, caregiver_id)

    if format == "csv":
        csv_buffer = service.generate_caregiver_csv(caregivers)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=caregiver_{caregiver_id}.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_caregiver_pdf(caregivers, f"Caregiver Report - {caregiver_id}")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=caregiver_{caregiver_id}.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/patients", response_model=list[PatientListItem])
async def list_patients(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """List patients for selector dropdowns."""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_patient_list(limit, offset)


@router.get("/patients/{patient_id}/summary", response_model=PatientSummary)
async def get_patient_summary(
    patient_id: UUID,
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Get patient summary metrics."""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_patient_summary(patient_id)


@router.get("/patients/{patient_id}/sessions", response_model=PatientSessionPage)
async def list_patient_sessions(
    patient_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """List patient session history."""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_patient_sessions(patient_id, limit, offset, start_date, end_date)


@router.get("/patients/{patient_id}/download")
async def download_patient_report(
    patient_id: UUID,
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download patient session history report."""
    check_permission(jwt_payload, "care-session:report")
    page = await service.get_patient_sessions(patient_id, limit=10000, offset=0, start_date=start_date, end_date=end_date)

    if format == "csv":
        csv_buffer = service.generate_patient_sessions_csv(page.items)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=patient_{patient_id}.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_patient_sessions_pdf(page.items, f"Patient Report - {patient_id}")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=patient_{patient_id}.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/feedback", response_model=FeedbackReportPage)
async def list_feedback_reports(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    period: str | None = Query(None, enum=["day", "week", "month"]),
    caregiver_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    session_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """List feedback reports with filters."""
    check_permission(jwt_payload, "care-session:report")
    if period:
        try:
            start_date, end_date = _resolve_period_range(period)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period")
    try:
        return await service.get_feedback_report(
            limit=limit,
            cursor=cursor,
            start_date=start_date,
            end_date=end_date,
            caregiver_id=caregiver_id,
            patient_id=patient_id,
            session_id=session_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@router.get("/feedback/summary", response_model=FeedbackReportSummary)
async def feedback_summary(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    period: str | None = Query(None, enum=["day", "week", "month"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Feedback summary metrics."""
    check_permission(jwt_payload, "care-session:report")
    if period:
        try:
            start_date, end_date = _resolve_period_range(period)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period")
    return await service.get_feedback_summary(start_date, end_date)


@router.get("/feedback/download")
async def download_feedback_report(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    period: str | None = Query(None, enum=["day", "week", "month"]),
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download feedback report."""
    check_permission(jwt_payload, "care-session:report")
    if period:
        try:
            start_date, end_date = _resolve_period_range(period)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period")
    page = await service.get_feedback_report(
        limit=10000,
        cursor=None,
        start_date=start_date,
        end_date=end_date,
        caregiver_id=None,
        patient_id=None,
        session_id=None,
    )

    if format == "csv":
        csv_buffer = service.generate_feedback_csv(page.items)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=feedback_report.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_feedback_pdf(page.items, "Feedback Report")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=feedback_report.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")


@router.get("/caregivers/{caregiver_id}/feedback", response_model=CaregiverFeedbackPage)
async def list_caregiver_feedback(
    caregiver_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """List caregiver feedback for reports."""
    check_permission(jwt_payload, "care-session:report")
    return await service.get_caregiver_feedback(caregiver_id, limit, offset)


@router.get("/caregivers/{caregiver_id}/feedback/download")
async def download_caregiver_feedback(
    caregiver_id: UUID,
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download caregiver feedback report."""
    check_permission(jwt_payload, "care-session:report")
    page = await service.get_caregiver_feedback(caregiver_id, limit=10000, offset=0)

    if format == "csv":
        csv_buffer = service.generate_caregiver_feedback_csv(page.items)
        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=caregiver_{caregiver_id}_feedback.csv"})
    elif format == "pdf":
        pdf_buffer = service.generate_caregiver_feedback_pdf(page.items, f"Caregiver Feedback - {caregiver_id}")
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=caregiver_{caregiver_id}_feedback.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")
