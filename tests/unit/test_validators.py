import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from app.care_sessions.validators import SessionValidator
from app.care_sessions.exceptions import (
    NFCTagNotFoundException,
    InvalidStatusException,
    InvalidSessionTimesException,
    SessionNotInProgressException,
    UnauthorizedCaregiverException,
)
from app.db.models import NFCTag, CareSession

# Test constant for tenant schema
TEST_TENANT_SCHEMA = "test_schema"


@pytest.fixture
def dummy_nfc_tag():
    """Create a dummy NFC tag for testing"""
    return NFCTag(id=uuid4(), tag_id="TAG123", patient_id=uuid4(), status="active")


@pytest.fixture
def dummy_care_session():
    """Create a dummy care session for testing"""
    return CareSession(
        id=uuid4(),
        patient_id=uuid4(),
        caregiver_id=uuid4(),
        check_in_time=datetime.now(),
        check_out_time=datetime.now(),
        status="in_progress",
    )


@pytest.mark.asyncio
async def test_get_patient_id_from_nfc_event_success(mock_db_session):
    """Test that patient_id is retrieved from NFC cache"""
    patient_id = uuid4()

    with patch("app.care_sessions.validators.get_nfc_cache") as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache.get_patient_id.return_value = patient_id
        mock_get_cache.return_value = mock_cache

        validator = SessionValidator(mock_db_session, MagicMock(), TEST_TENANT_SCHEMA)
        result = validator.get_patient_id_from_nfc_event("TAG123")

        assert result == patient_id
        mock_cache.get_patient_id.assert_called_once_with("TAG123")


@pytest.mark.asyncio
async def test_get_patient_id_from_nfc_event_not_found(mock_db_session):
    """Test that NFCTagNotFoundException is raised when tag not in cache"""
    with patch("app.care_sessions.validators.get_nfc_cache") as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache.get_patient_id.return_value = None
        mock_get_cache.return_value = mock_cache

        validator = SessionValidator(mock_db_session, MagicMock(), TEST_TENANT_SCHEMA)

        with pytest.raises(NFCTagNotFoundException):
            validator.get_patient_id_from_nfc_event("INVALID_TAG")


def test_validate_status_valid():
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    # Should not raise for valid statuses
    validator.validate_status("in_progress")
    validator.validate_status("completed")


def test_validate_status_invalid():
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    with pytest.raises(InvalidStatusException):
        validator.validate_status("invalid_status")


def test_validate_session_times_valid(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    # Valid: check_out after check_in
    dummy_care_session.check_in_time = datetime(2023, 1, 1, 10, 0)
    dummy_care_session.check_out_time = datetime(2023, 1, 1, 11, 0)

    # Should not raise
    validator.validate_session_times(dummy_care_session)


def test_validate_session_times_invalid(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    # Invalid: check_out before check_in
    dummy_care_session.check_in_time = datetime(2023, 1, 1, 11, 0)
    dummy_care_session.check_out_time = datetime(2023, 1, 1, 10, 0)

    with pytest.raises(InvalidSessionTimesException):
        validator.validate_session_times(dummy_care_session)


def test_validate_session_times_same_time(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    # Invalid: check_out same as check_in
    same_time = datetime(2023, 1, 1, 10, 0)
    dummy_care_session.check_in_time = same_time
    dummy_care_session.check_out_time = same_time

    with pytest.raises(InvalidSessionTimesException):
        validator.validate_session_times(dummy_care_session)


def test_validate_session_times_no_check_out(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    # Valid: no check_out_time yet
    dummy_care_session.check_out_time = None

    # Should not raise
    validator.validate_session_times(dummy_care_session)


def test_validate_session_in_progress_valid(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    dummy_care_session.status = "in_progress"

    # Should not raise
    validator.validate_session_in_progress(dummy_care_session)


def test_validate_session_in_progress_invalid(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    dummy_care_session.status = "completed"

    with pytest.raises(SessionNotInProgressException):
        validator.validate_session_in_progress(dummy_care_session)


def test_validate_caregiver_ownership_valid(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    caregiver_id = dummy_care_session.caregiver_id

    # Should not raise
    validator.validate_caregiver_ownership(dummy_care_session, caregiver_id)


def test_validate_caregiver_ownership_invalid(dummy_care_session):
    validator = SessionValidator(None, None, TEST_TENANT_SCHEMA)

    different_caregiver_id = uuid4()

    with pytest.raises(UnauthorizedCaregiverException):
        validator.validate_caregiver_ownership(dummy_care_session, different_caregiver_id)
