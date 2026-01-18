import pytest
from unittest.mock import AsyncMock, MagicMock
from app.care_sessions.service import CareSessionService
from app.care_sessions.exceptions import DuplicateActiveSessionException


@pytest.mark.asyncio
async def test_create_session_success(fake_db, dummy_care_session):
    svc = CareSessionService(fake_db, "test_schema")

    # Mock validator to return an object with patient_id
    svc.validator = MagicMock()
    svc.validator.validate_and_get_nfc_tag = AsyncMock()
    svc.validator.validate_and_get_nfc_tag.return_value = MagicMock(patient_id=dummy_care_session.patient_id)

    # Mock repository
    svc.repository = MagicMock()
    svc.repository.get_active_by_patient = AsyncMock(return_value=None)
    svc.repository.create = AsyncMock(return_value=dummy_care_session)

    created = await svc.create_session(tag_id="TAG1", caregiver_id=dummy_care_session.caregiver_id)

    assert created is dummy_care_session
    svc.repository.create.assert_awaited()


@pytest.mark.asyncio
async def test_create_session_duplicate_raises(fake_db, dummy_care_session):
    svc = CareSessionService(fake_db, "test_schema")

    svc.validator = MagicMock()
    svc.validator.validate_and_get_nfc_tag = AsyncMock()
    svc.validator.validate_and_get_nfc_tag.return_value = MagicMock(patient_id=dummy_care_session.patient_id)

    svc.repository = MagicMock()
    # Simulate an existing active session
    svc.repository.get_active_by_patient = AsyncMock(return_value=dummy_care_session)

    with pytest.raises(DuplicateActiveSessionException):
        await svc.create_session(tag_id="TAG1", caregiver_id=dummy_care_session.caregiver_id)


@pytest.mark.asyncio
async def test_complete_session_updates_and_returns(fake_db, dummy_care_session):
    svc = CareSessionService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=dummy_care_session)
    # The update should be awaited and return an updated object
    updated = dummy_care_session
    updated.status = "completed"
    svc.repository.update = AsyncMock(return_value=updated)

    svc.validator = MagicMock()
    svc.validator.validate_session_in_progress = MagicMock()
    svc.validator.validate_caregiver_ownership = MagicMock()

    res = await svc.complete_session(
        session_id=dummy_care_session.id,
        caregiver_notes="notes",
        caregiver_id=dummy_care_session.caregiver_id,
    )

    assert res.status == "completed"
    svc.repository.update.assert_awaited()


@pytest.mark.asyncio
async def test_update_session_applies_changes_and_validates(fake_db, dummy_care_session):
    svc = CareSessionService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=dummy_care_session)
    svc.repository.update = AsyncMock(return_value=dummy_care_session)

    svc.validator = MagicMock()
    svc.validator.validate_status = MagicMock()
    svc.validator.validate_session_times = MagicMock()

    res = await svc.update_session(
        session_id=dummy_care_session.id,
        check_in_time=None,
        check_out_time=None,
        caregiver_notes="updated",
        status="completed",
    )

    assert res is dummy_care_session
    svc.repository.update.assert_awaited()


@pytest.mark.asyncio
async def test_get_session_auto_complete_triggers_commit(fake_db, dummy_care_session, monkeypatch):
    svc = CareSessionService(fake_db, "test_schema")
    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=dummy_care_session)

    # Patch the auto_complete_if_needed function to return True so commit is hit
    monkeypatch.setattr("app.care_sessions.service.auto_complete_if_needed", lambda s: True)

    # fake_db.commit is an AsyncMock from fixture and will be awaited
    res = await svc.get_session(dummy_care_session.id)
    # commit should have been called on the db session
    fake_db.commit.assert_awaited()
    assert res is dummy_care_session


@pytest.mark.asyncio
async def test_delete_session_calls_repository(fake_db, dummy_care_session):
    svc = CareSessionService(fake_db, "test_schema")
    svc.repository = MagicMock()
    svc.repository.delete = AsyncMock(return_value=True)

    res = await svc.delete_session(dummy_care_session.id)
    assert res is True
    svc.repository.delete.assert_awaited()
