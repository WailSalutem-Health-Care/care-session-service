from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.care_sessions.service import CareSessionService
from app.care_sessions.schemas import (
    CreateCareSessionRequest,
    CareSessionResponse,
)
from app.auth.middleware import JWTPayload, verify_token

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
    # Check permission
    if "care-session:create" not in jwt_payload.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create care session"
        )
    
    # Create service and execute
    service = CareSessionService(db, jwt_payload.tenant_schema)
    
    session = await service.create_session(
        tag_id=request.tag_id,
        caregiver_id=jwt_payload.user_id,
        caregiver_notes=request.caregiver_notes,
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
    # Check permission
    if "care-session:read" not in jwt_payload.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view care session"
        )
    
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

