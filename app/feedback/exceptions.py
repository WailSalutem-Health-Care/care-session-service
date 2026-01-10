"""Feedback custom exceptions"""
from uuid import UUID
from fastapi import HTTPException, status


class FeedbackNotFoundException(HTTPException):
    """Raised when feedback is not found"""
    def __init__(self, feedback_id: UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback with id {feedback_id} not found"
        )


class FeedbackAlreadyExistsException(HTTPException):
    """Raised when feedback already exists for a session"""
    def __init__(self, session_id: UUID):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feedback already exists for session {session_id}"
        )


class UnauthorizedFeedbackAccessException(HTTPException):
    """Raised when user tries to access feedback they don't own"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this feedback"
        )
