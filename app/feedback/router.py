"""Feedback REST API endpoints"""
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.feedback.service import FeedbackService
from app.feedback.schemas import CreateFeedbackRequest, FeedbackResponse, FeedbackListResponse
from app.feedback.models import Feedback
from app.auth.middleware import JWTPayload, verify_token, check_permission

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
)


def to_response(feedback: Feedback) -> FeedbackResponse:
    """Convert Feedback model to response schema"""
    return FeedbackResponse(
        id=feedback.id,
        care_session_id=feedback.care_session_id,
        patient_id=feedback.patient_id,
        rating=feedback.rating,
        created_at=feedback.created_at,
    )


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    request: CreateFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Create feedback for a care session.
    
    Business rules:
    - Only patients can create feedback
    - One feedback per session
    - Rating must be 1-5 stars
    
    Required permission: feedback:create (PATIENT role)
    """
    check_permission(jwt_payload, "feedback:create")
    
    service = FeedbackService(db, jwt_payload.tenant_schema)
    feedback = await service.create_feedback(
        care_session_id=request.care_session_id,
        patient_id=jwt_payload.user_id,
        rating=request.rating,
    )
    
    return to_response(feedback)


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback_by_id(
    feedback_id: UUID,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Get patient's own feedback by ID.
    
    Required permission: feedback:read (PATIENT role)
    """
    check_permission(jwt_payload, "feedback:read")
    
    service = FeedbackService(db, jwt_payload.tenant_schema)
    feedback = await service.get_feedback_by_id(feedback_id=feedback_id)
    
    return to_response(feedback)


@router.get("/", response_model=FeedbackListResponse)
async def list_feedbacks(
    patient_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    List all feedbacks (Admins only).
    
    """
    check_permission(jwt_payload, "feedback:read")
    
    service = FeedbackService(db, jwt_payload.tenant_schema)
    feedbacks, total = await service.list_feedbacks(
        patient_id=patient_id,
        page=page,
        page_size=page_size,
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return FeedbackListResponse(
        feedbacks=[to_response(feedback) for feedback in feedbacks],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
