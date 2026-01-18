import pytest
from unittest.mock import AsyncMock, MagicMock
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


@pytest.fixture
def dummy_nfc_tag():
    """Create a dummy NFC tag for testing"""
    return NFCTag(
        id=uuid4(),
        tag_id="TAG123",
        patient_id=uuid4(),
        status="active"
    )


@pytest.fixture
def dummy_care_session():
    """Create a dummy care session for testing"""
    return CareSession(
        id=uuid4(),
        patient_id=uuid4(),
        caregiver_id=uuid4(),
        check_in_time=datetime.now(),
        check_out_time=datetime.now(),
        status="in_progress"
    )


@pytest.mark.asyncio
async def test_validate_and_get_nfc_tag_success(fake_db, dummy_nfc_tag):
    validator = SessionValidator(fake_db, MagicMock())

    # Mock the repository's _set_search_path method
    validator.repository._set_search_path = AsyncMock()

    # Mock the db execute to return the tag
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = dummy_nfc_tag
    fake_db.execute = AsyncMock(return_value=result_mock)

    result = await validator.validate_and_get_nfc_tag("TAG123")

    assert result is dummy_nfc_tag
    fake_db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_validate_and_get_nfc_tag_not_found(fake_db):
    validator = SessionValidator(fake_db, MagicMock())

    # Mock the repository's _set_search_path method
    validator.repository._set_search_path = AsyncMock()

    # Mock the db execute to return None
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    fake_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(NFCTagNotFoundException):
        await validator.validate_and_get_nfc_tag("INVALID_TAG")


def test_validate_status_valid():
    validator = SessionValidator(None, None)

    # Should not raise for valid statuses
    validator.validate_status("in_progress")
    validator.validate_status("completed")


def test_validate_status_invalid():
    validator = SessionValidator(None, None)

    with pytest.raises(InvalidStatusException):
        validator.validate_status("invalid_status")


def test_validate_session_times_valid(dummy_care_session):
    validator = SessionValidator(None, None)

    # Valid: check_out after check_in
    dummy_care_session.check_in_time = datetime(2023, 1, 1, 10, 0)
    dummy_care_session.check_out_time = datetime(2023, 1, 1, 11, 0)

    # Should not raise
    validator.validate_session_times(dummy_care_session)


def test_validate_session_times_invalid(dummy_care_session):
    validator = SessionValidator(None, None)

    # Invalid: check_out before check_in
    dummy_care_session.check_in_time = datetime(2023, 1, 1, 11, 0)
    dummy_care_session.check_out_time = datetime(2023, 1, 1, 10, 0)

    with pytest.raises(InvalidSessionTimesException):
        validator.validate_session_times(dummy_care_session)


def test_validate_session_times_same_time(dummy_care_session):
    validator = SessionValidator(None, None)

    # Invalid: check_out same as check_in
    same_time = datetime(2023, 1, 1, 10, 0)
    dummy_care_session.check_in_time = same_time
    dummy_care_session.check_out_time = same_time

    with pytest.raises(InvalidSessionTimesException):
        validator.validate_session_times(dummy_care_session)


def test_validate_session_times_no_check_out(dummy_care_session):
    validator = SessionValidator(None, None)

    # Valid: no check_out_time yet
    dummy_care_session.check_out_time = None

    # Should not raise
    validator.validate_session_times(dummy_care_session)


def test_validate_session_in_progress_valid(dummy_care_session):
    validator = SessionValidator(None, None)

    dummy_care_session.status = "in_progress"

    # Should not raise
    validator.validate_session_in_progress(dummy_care_session)


def test_validate_session_in_progress_invalid(dummy_care_session):
    validator = SessionValidator(None, None)

    dummy_care_session.status = "completed"

    with pytest.raises(SessionNotInProgressException):
        validator.validate_session_in_progress(dummy_care_session)


def test_validate_caregiver_ownership_valid(dummy_care_session):
    validator = SessionValidator(None, None)

    caregiver_id = dummy_care_session.caregiver_id

    # Should not raise
    validator.validate_caregiver_ownership(dummy_care_session, caregiver_id)


def test_validate_caregiver_ownership_invalid(dummy_care_session):
    validator = SessionValidator(None, None)

    different_caregiver_id = uuid4()

    with pytest.raises(UnauthorizedCaregiverException):
        validator.validate_caregiver_ownership(dummy_care_session, different_caregiver_id)