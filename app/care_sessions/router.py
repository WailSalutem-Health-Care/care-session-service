from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.care_sessions.service import CareSessionService
from app.care_sessions.schemas import (
    CreateCareSessionRequest,
    CareSessionResponse,
    CompleteCareSessionRequest,
)
from app.auth.middleware import JWTPayload, verify_token, check_permission

router = APIRouter(
    prefix="/care-sessions",
    tags=["care-sessions"],
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
    )
    
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


@router.get("/{session_id}", response_model=CareSessionResponse)
async def get_care_session(
    session_id: UUID,
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


@router.put("/{session_id}/complete", response_model=CareSessionResponse)
async def complete_care_session(
    session_id: UUID,
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
