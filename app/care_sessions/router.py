from uuid import UUID
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.care_sessions.service import CareSessionService
from app.care_sessions.schemas import (
    CreateCareSessionRequest,
    CareSessionResponse,
    CareSessionListResponse,
    CompleteCareSessionRequest,
    UpdateCareSessionRequest,
)
from app.care_sessions.models import CareSession
from app.auth.middleware import JWTPayload, verify_token, check_permission

router = APIRouter(
    prefix="/care-sessions",
    tags=["care-sessions"],
)


def to_response(session: CareSession) -> CareSessionResponse:
    """Convert CareSession model to response schema."""
    return CareSessionResponse(
        session_id=session.session_id,
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


@router.post("/create", response_model=CareSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_care_session(
    request: CreateCareSessionRequest,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Create a new care session by scanning an NFC tag.
    
    Workflow:
    1. Validates NFC tag exists and is active
    2. Checks for duplicate active sessions for patient
    3. Creates session with check_in timestamp
    
    Required permission: care-session:create (CAREGIVER role)
    """
    check_permission(jwt_payload, "care-session:create")
    
    service = CareSessionService(db, jwt_payload.tenant_schema)
    session = await service.create_session(
        tag_id=request.tag_id,
        caregiver_id=jwt_payload.user_id,
        session_id=request.session_id,
    )
    
    return to_response(session)


@router.get("/{session_id}", response_model=CareSessionResponse)
async def get_care_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Get care session details.
    
    Required permission: care-session:read (CAREGIVER, PATIENT roles)
    """
    check_permission(jwt_payload, "care-session:read")
    
    service = CareSessionService(db, jwt_payload.tenant_schema)
    session = await service.get_session(session_id)
    
    return to_response(session)


@router.put("/{session_id}/complete", response_model=CareSessionResponse)
async def complete_care_session(
    session_id: str,
    request: CompleteCareSessionRequest,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Complete a care session (check-out) and add caregiver notes.
    
    Workflow:
    1. Validates session exists and is in progress
    2. Verifies caregiver owns the session
    3. Sets check_out_time, adds notes, marks as completed
    
    Required permission: care-session:update (CAREGIVER role)
    """
    check_permission(jwt_payload, "care-session:update")
    
    service = CareSessionService(db, jwt_payload.tenant_schema)
    session = await service.complete_session(
        session_id=session_id,
        caregiver_notes=request.caregiver_notes,
        caregiver_id=jwt_payload.user_id,
    )
    
    return to_response(session)


@router.get("/", response_model=CareSessionListResponse)
async def list_care_sessions(
    caregiver_id: Optional[UUID] = Query(None),
    patient_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """List care sessions with optional filters and pagination."""
    check_permission(jwt_payload, "care-session:read")
    
    service = CareSessionService(db, jwt_payload.tenant_schema)
    sessions, total = await service.list_sessions(
        caregiver_id=caregiver_id,
        patient_id=patient_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return CareSessionListResponse(
        sessions=[to_response(session) for session in sessions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.patch("/{session_id}", response_model=CareSessionResponse)
async def update_care_session(
    session_id: str,
    request: UpdateCareSessionRequest,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Update a care session (Admins only).
    
    Allows admins to correct or adjust session data:
    - Update check-in time
    - Update check-out time
    - Update caregiver notes
    - Change session status
    
    All fields are optional - only provided fields will be updated.
    
    Required permission: care-session:admin (ORG_ADMIN, SUPER_ADMIN roles)
    """
    check_permission(jwt_payload, "care-session:admin")
    
    service = CareSessionService(db, jwt_payload.tenant_schema)
    session = await service.update_session(
        session_id=session_id,
        check_in_time=request.check_in_time,
        check_out_time=request.check_out_time,
        caregiver_notes=request.caregiver_notes,
        status=request.status,
    )
    
    return to_response(session)
