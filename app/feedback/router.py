"""Feedback REST API endpoints"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.feedback.service import FeedbackService
from app.feedback.schemas import CreateFeedbackRequest, FeedbackResponse
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

