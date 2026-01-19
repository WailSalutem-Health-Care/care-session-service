import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import date
from app.feedback.service import FeedbackService
from app.feedback.exceptions import FeedbackAlreadyExistsException, FeedbackNotFoundException
from app.db.models import Feedback


@pytest.fixture
def dummy_feedback():
    """Create a dummy feedback object for testing"""
    return Feedback(
        id=uuid4(),
        care_session_id=uuid4(),
        patient_id=uuid4(),
        caregiver_id=uuid4(),
        rating=3,
        patient_feedback="Great service!"
    )


@pytest.fixture
def dummy_care_session():
    """Create a dummy care session object for testing"""
    class DummyCareSession:
        def __init__(self):
            self.id = uuid4()
            self.caregiver_id = uuid4()
    return DummyCareSession()


@pytest.mark.asyncio
async def test_create_feedback_success(fake_db, dummy_feedback, dummy_care_session):
    svc = FeedbackService(fake_db, "test_schema")

    # Mock repositories
    svc.repository = MagicMock()
    svc.repository.get_by_session_id = AsyncMock(return_value=None)
    svc.repository.create = AsyncMock(return_value=dummy_feedback)

    svc.care_session_repository = MagicMock()
    svc.care_session_repository.get_by_id = AsyncMock(return_value=dummy_care_session)

    created = await svc.create_feedback(
        care_session_id=dummy_feedback.care_session_id,
        patient_id=dummy_feedback.patient_id,
        rating=dummy_feedback.rating,
        patient_feedback=dummy_feedback.patient_feedback
    )

    assert created is dummy_feedback
    svc.repository.create.assert_awaited()


@pytest.mark.asyncio
async def test_create_feedback_already_exists_raises(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.get_by_session_id = AsyncMock(return_value=dummy_feedback)

    with pytest.raises(FeedbackAlreadyExistsException):
        await svc.create_feedback(
            care_session_id=dummy_feedback.care_session_id,
            patient_id=dummy_feedback.patient_id,
            rating=dummy_feedback.rating
        )


@pytest.mark.asyncio
async def test_create_feedback_care_session_not_found_raises(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.get_by_session_id = AsyncMock(return_value=None)

    svc.care_session_repository = MagicMock()
    svc.care_session_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match=f"Care session {dummy_feedback.care_session_id} not found"):
        await svc.create_feedback(
            care_session_id=dummy_feedback.care_session_id,
            patient_id=dummy_feedback.patient_id,
            rating=dummy_feedback.rating
        )


@pytest.mark.asyncio
async def test_get_feedback_by_id_success(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=dummy_feedback)

    result = await svc.get_feedback_by_id(dummy_feedback.id)

    assert result is dummy_feedback


@pytest.mark.asyncio
async def test_get_feedback_by_id_not_found_raises(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    feedback_id = uuid4()
    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(FeedbackNotFoundException):
        await svc.get_feedback_by_id(feedback_id)


@pytest.mark.asyncio
async def test_list_feedbacks_without_filters(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.list_feedbacks = AsyncMock(return_value=([dummy_feedback], 1))

    feedbacks, total = await svc.list_feedbacks()

    assert feedbacks == [dummy_feedback]
    assert total == 1
    svc.repository.list_feedbacks.assert_awaited_with(
        patient_id=None, page=1, page_size=20
    )


@pytest.mark.asyncio
async def test_list_feedbacks_with_patient_filter(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    patient_id = uuid4()
    svc.repository = MagicMock()
    svc.repository.list_feedbacks = AsyncMock(return_value=([dummy_feedback], 1))

    feedbacks, total = await svc.list_feedbacks(patient_id=patient_id, page=2, page_size=10)

    assert feedbacks == [dummy_feedback]
    assert total == 1
    svc.repository.list_feedbacks.assert_awaited_with(
        patient_id=patient_id, page=2, page_size=10
    )


@pytest.mark.asyncio
async def test_get_daily_averages(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    start_date = date.today()
    end_date = date.today()
    daily_averages = [{'date': start_date, 'average_rating': 3.0, 'total_feedbacks': 1}]

    svc.repository = MagicMock()
    svc.repository.get_daily_averages = AsyncMock(return_value=daily_averages)
    svc.repository.list_feedbacks = AsyncMock(return_value=([dummy_feedback], 1))

    result_averages, result_feedbacks = await svc.get_daily_averages(start_date, end_date)

    assert result_averages == daily_averages
    assert result_feedbacks == [dummy_feedback]


@pytest.mark.asyncio
async def test_get_caregiver_weekly_metrics(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    caregiver_id = uuid4()
    week_start = date.today()
    week_end = date.today()

    svc.repository = MagicMock()
    svc.repository.get_caregiver_weekly_feedbacks = AsyncMock(return_value=[dummy_feedback])

    result = await svc.get_caregiver_weekly_metrics(caregiver_id, week_start, week_end)

    assert result == [dummy_feedback]
    svc.repository.get_caregiver_weekly_feedbacks.assert_awaited_with(
        caregiver_id=caregiver_id, week_start=week_start, week_end=week_end
    )


@pytest.mark.asyncio
async def test_get_patient_average_rating_with_feedback(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    patient_id = uuid4()
    avg_rating = 2.5

    svc.repository = MagicMock()
    svc.repository.get_patient_average_rating = AsyncMock(return_value=avg_rating)

    result = await svc.get_patient_average_rating(patient_id)

    assert result == avg_rating


@pytest.mark.asyncio
async def test_get_patient_average_rating_no_feedback(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    patient_id = uuid4()

    svc.repository = MagicMock()
    svc.repository.get_patient_average_rating = AsyncMock(return_value=None)

    result = await svc.get_patient_average_rating(patient_id)

    assert result is None


@pytest.mark.asyncio
async def test_get_top_caregivers_of_week(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    week_start = date.today()
    week_end = date.today()
    top_caregivers = [
        {'caregiver_id': uuid4(), 'average_rating': 3.0, 'total_feedbacks': 5}
    ]

    svc.repository = MagicMock()
    svc.repository.get_top_caregivers_of_week = AsyncMock(return_value=top_caregivers)

    result = await svc.get_top_caregivers_of_week(week_start, week_end)

    assert result == top_caregivers
    svc.repository.get_top_caregivers_of_week.assert_awaited_with(week_start, week_end, limit=3)


@pytest.mark.asyncio
async def test_delete_feedback_success(fake_db, dummy_feedback):
    svc = FeedbackService(fake_db, "test_schema")

    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=dummy_feedback)
    svc.repository.delete = AsyncMock()

    await svc.delete_feedback(dummy_feedback.id)

    svc.repository.delete.assert_awaited_with(dummy_feedback)


@pytest.mark.asyncio
async def test_delete_feedback_not_found_raises(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    feedback_id = uuid4()
    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(FeedbackNotFoundException):
        await svc.delete_feedback(feedback_id)


@pytest.mark.asyncio
async def test_get_caregiver_average_rating_with_feedback(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    caregiver_id = uuid4()
    start_date = date.today()
    end_date = date.today()
    avg_rating = 2.8
    total_feedbacks = 4

    svc.repository = MagicMock()
    svc.repository.get_caregiver_average_rating = AsyncMock(return_value=(avg_rating, total_feedbacks))

    result_avg, result_total = await svc.get_caregiver_average_rating(caregiver_id, start_date, end_date)

    assert result_avg == avg_rating
    assert result_total == total_feedbacks


@pytest.mark.asyncio
async def test_get_caregiver_average_rating_no_feedback(fake_db):
    svc = FeedbackService(fake_db, "test_schema")

    caregiver_id = uuid4()
    start_date = date.today()
    end_date = date.today()

    svc.repository = MagicMock()
    svc.repository.get_caregiver_average_rating = AsyncMock(return_value=(None, 0))

    result_avg, result_total = await svc.get_caregiver_average_rating(caregiver_id, start_date, end_date)

    assert result_avg is None
    assert result_total == 0