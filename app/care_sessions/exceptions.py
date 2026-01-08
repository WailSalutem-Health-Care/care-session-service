"""Custom exceptions for care sessions"""
from fastapi import HTTPException, status


class CareSessionNotFoundException(HTTPException):
    """Raised when a care session is not found"""
    def __init__(self, session_id: str = None):
        detail = "Care session not found"
        if session_id:
            detail = f"Care session {session_id} not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class NFCTagNotFoundException(HTTPException):
    """Raised when an NFC tag is not found or inactive"""
    def __init__(self, tag_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NFC tag '{tag_id}' not found or inactive"
        )


class InvalidStatusException(HTTPException):
    """Raised when an invalid status is provided"""
    def __init__(self, status_value: str, valid_statuses: list):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status_value}'. Must be one of: {', '.join(valid_statuses)}"
        )


class InvalidSessionTimesException(HTTPException):
    """Raised when check_out_time is before or equal to check_in_time"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-out time must be after check-in time"
        )


class SessionNotInProgressException(HTTPException):
    """Raised when attempting to complete a session that is not in progress"""
    def __init__(self, current_status: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete session with status: {current_status}"
        )


class UnauthorizedCaregiverException(HTTPException):
    """Raised when a caregiver tries to complete someone else's session"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only complete your own sessions"
        )


class DuplicateActiveSessionException(HTTPException):
    """Raised when trying to create a session for a patient who already has an active session"""
    def __init__(self, patient_id: str = None):
        detail = "Active session already exists for this patient"
        if patient_id:
            detail = f"Active session already exists for patient {patient_id}"
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
