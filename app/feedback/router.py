"""Feedback REST API endpoints"""
from uuid import UUID
from typing import Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.feedback.service import FeedbackService
from fastapi import Response
from app.feedback.schemas import (
    CreateFeedbackRequest, 
    FeedbackResponse, 
    FeedbackListResponse, 
    FeedbackMetrics,
    DailyAverageResponse,
    DailyAverageListResponse,
    CaregiverWeeklyMetrics,
    PatientAverageRatingResponse,
    TopCaregiversResponse,
    TopCaregiverItem,
)
from app.feedback.models import Feedback
from app.feedback.satisfaction import get_satisfaction_level, compute_metrics
from app.auth.middleware import JWTPayload, verify_token, check_permission

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
)


def to_response(feedback: Feedback) -> FeedbackResponse:
    """Convert Feedback model to response schema"""
    satisfaction_level = get_satisfaction_level(feedback.rating)
    return FeedbackResponse(
        id=feedback.id,
        care_session_id=feedback.care_session_id,
        patient_id=feedback.patient_id,
        caregiver_id=feedback.caregiver_id,
        rating=feedback.rating,
        patient_feedback=feedback.patient_feedback,
        satisfaction_level=satisfaction_level.value,
        created_at=feedback.created_at,
    )


def calculate_satisfaction_index(average_rating: float) -> float:
    """Calculate satisfaction index (0-100 scale) from average rating"""
    return round((average_rating / 3.0) * 100, 2)


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
    - Rating: 1=Dissatisfied, 2=Neutral, 3=Satisfied
    
    Required permission: feedback:create (PATIENT role)
    """
    check_permission(jwt_payload, "feedback:create")
    
    service = FeedbackService(db, jwt_payload.tenant_schema)
    feedback = await service.create_feedback(
        care_session_id=request.care_session_id,
        patient_id=jwt_payload.user_id,
        rating=request.rating,
        patient_feedback=request.patient_feedback,
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
    
    # Compute satisfaction metrics
    metrics_data = compute_metrics(feedbacks)
    metrics = FeedbackMetrics(**metrics_data)
    
    total_pages = (total + page_size - 1) // page_size
    
    return FeedbackListResponse(
        feedbacks=[to_response(feedback) for feedback in feedbacks],
        count=len(feedbacks),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        metrics=metrics,
    )


@router.get("/analytics/daily", response_model=DailyAverageListResponse)
async def get_daily_averages(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Get daily average feedback ratings for a date range.
    
    Returns daily averages and overall metrics for the period.
    Required permission: feedback:read (Admin roles)
    """
    check_permission(jwt_payload, "feedback:read")
    
    service = FeedbackService(db, jwt_payload.tenant_schema)
    daily_averages, all_feedbacks = await service.get_daily_averages(start_date, end_date)
    
    # Build daily responses
    daily_responses = [
        DailyAverageResponse(
            date=day['date'].isoformat(),
            average_rating=round(day['average_rating'], 2),
            total_feedbacks=day['total_feedbacks'],
            satisfaction_index=calculate_satisfaction_index(day['average_rating']),
        )
        for day in daily_averages
    ]
    
    # Compute overall metrics
    overall_metrics = FeedbackMetrics(**compute_metrics(all_feedbacks))
    
    return DailyAverageListResponse(
        daily_averages=daily_responses,
        count=len(daily_responses),
        overall_metrics=overall_metrics,
    )


@router.get("/analytics/caregiver/{caregiver_id}/weekly", response_model=CaregiverWeeklyMetrics)
async def get_caregiver_weekly_metrics(
    caregiver_id: UUID,
    week_start: date = Query(..., description="Start of week - Monday (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Get caregiver's average feedback for a specific week.
    
    Week runs Monday-Sunday. Returns metrics for the 7-day period.
    Required permission: feedback:read (Admin roles)
    """
    check_permission(jwt_payload, "feedback:read")
    
    week_end = week_start + timedelta(days=6)
    service = FeedbackService(db, jwt_payload.tenant_schema)
    feedbacks = await service.get_caregiver_weekly_metrics(caregiver_id, week_start, week_end)
    
    # Compute metrics (returns empty metrics if no feedbacks)
    metrics_data = compute_metrics(feedbacks)
    
    return CaregiverWeeklyMetrics(
        caregiver_id=caregiver_id,
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        **metrics_data,
    )


@router.get("/analytics/patient/{patient_id}/average", response_model=PatientAverageRatingResponse)
async def get_patient_average_rating(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Get patient's all-time average rating across all their feedback.

    """
    check_permission(jwt_payload, "feedback:read")
    
    service = FeedbackService(db, jwt_payload.tenant_schema)
    
    # Get average rating
    avg_rating = await service.get_patient_average_rating(patient_id)
    
    # Get total count
    _, total_feedbacks = await service.list_feedbacks(patient_id=patient_id, page=1, page_size=1)
    
    # Calculate satisfaction index
    satisfaction_index = None
    if avg_rating is not None:
        satisfaction_index = calculate_satisfaction_index(avg_rating)
    
    return PatientAverageRatingResponse(
        patient_id=patient_id,
        average_rating=round(avg_rating, 2) if avg_rating is not None else None,
        satisfaction_index=satisfaction_index,
        total_feedbacks=total_feedbacks,
    )


@router.get("/analytics/top-caregivers/weekly", response_model=TopCaregiversResponse)
async def get_top_caregivers_of_week(
    week_start: date = Query(..., description="Start of week - Monday (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Get top 3 caregivers of the week based on average feedback rating.
    
    """
    check_permission(jwt_payload, "feedback:read")
    
    week_end = week_start + timedelta(days=6)
    service = FeedbackService(db, jwt_payload.tenant_schema)
    
    top_caregivers_data = await service.get_top_caregivers_of_week(week_start, week_end)
    
    # Build response with rankings
    top_caregivers = [
        TopCaregiverItem(
            caregiver_id=caregiver['caregiver_id'],
            average_rating=round(caregiver['average_rating'], 2),
            satisfaction_index=calculate_satisfaction_index(caregiver['average_rating']),
            total_feedbacks=caregiver['total_feedbacks'],
            rank=idx + 1,
        )
        for idx, caregiver in enumerate(top_caregivers_data)
    ]
    
    return TopCaregiversResponse(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        top_caregivers=top_caregivers,
    )

@router.delete("/delete/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(
    feedback_id: UUID,
    db: AsyncSession = Depends(get_db),
    jwt_payload: JWTPayload = Depends(verify_token),
):
    """
    Delete a feedback. 
    """
    check_permission(jwt_payload, "feedback:delete")

    service = FeedbackService(db, jwt_payload.tenant_schema)
    
    await service.delete_feedback(feedback_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
