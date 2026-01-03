from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.reports.service import ReportsService
from app.reports.schemas import CareSessionReportPage
from app.care_sessions.repository import CareSessionRepository
from app.care_sessions.schemas import CareSessionResponse
from app.auth.middleware import JWTPayload, verify_token, check_permission


def get_reports_service(db: AsyncSession = Depends(get_db), jwt_payload: JWTPayload = Depends(verify_token)) -> ReportsService:
    """Dependency to get ReportsService"""
    repository = CareSessionRepository(db, jwt_payload.tenant_schema)
    return ReportsService(repository)


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


@router.get("/sessions/period", response_model=CareSessionReportPage)
async def get_period_session_report(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = Query(None),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Get reports for care sessions in a specific time period"""
    check_permission(jwt_payload, "care-session:report")
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
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    service: ReportsService = Depends(get_reports_service),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """Download reports for care sessions in a specific time period"""
    check_permission(jwt_payload, "care-session:report")
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


@router.get("/sessions/{session_id}", response_model=CareSessionResponse)
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
