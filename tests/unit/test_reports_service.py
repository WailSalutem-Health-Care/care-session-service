import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, date
from io import BytesIO
from app.reports.service import ReportsService
from app.care_sessions.exceptions import CareSessionNotFoundException


@pytest.fixture
def dummy_session():
    """Create a dummy care session for testing"""

    class DummySession:
        def __init__(self):
            self.id = uuid4()
            self.patient_id = uuid4()
            self.caregiver_id = uuid4()
            self.check_in_time = datetime.now()
            self.check_out_time = datetime.now()
            self.status = "completed"
            self.caregiver_notes = "Good session"
            self.created_at = datetime.now()
            self.updated_at = datetime.now()

    return DummySession()


@pytest.fixture
def dummy_patient():
    """Create a dummy patient for testing"""

    class DummyPatient:
        def __init__(self):
            self.id = uuid4()
            self.first_name = "John"
            self.last_name = "Doe"
            self.email = "john.doe@example.com"
            self.careplan_type = "standard"
            self.is_active = True

    return DummyPatient()


@pytest.fixture
def dummy_user():
    """Create a dummy user for testing"""

    class DummyUser:
        def __init__(self):
            self.id = uuid4()
            self.first_name = "Jane"
            self.last_name = "Smith"
            self.email = "jane.smith@example.com"
            self.is_active = True

    return DummyUser()


@pytest.fixture
def dummy_feedback():
    """Create a dummy feedback for testing"""
    return {
        "id": uuid4(),
        "care_session_id": uuid4(),
        "patient_id": uuid4(),
        "caregiver_id": uuid4(),
        "feedback_date": datetime.now(),
        "rating": 3,
        "patient_feedback": "Good service",
    }


@pytest.mark.asyncio
async def test_get_individual_session_report_success(dummy_session, dummy_patient, dummy_user):
    svc = ReportsService(None)

    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=dummy_session)
    svc._load_cache_maps = AsyncMock(
        return_value=({dummy_session.patient_id: dummy_patient}, {dummy_session.caregiver_id: dummy_user})
    )

    result = await svc.get_individual_session_report(dummy_session.id)

    assert result.id == dummy_session.id
    assert result.patient_full_name == "John Doe"
    assert result.caregiver_full_name == "Jane Smith"


@pytest.mark.asyncio
async def test_get_individual_session_report_not_found():
    svc = ReportsService(None)

    session_id = uuid4()
    svc.repository = MagicMock()
    svc.repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(CareSessionNotFoundException):
        await svc.get_individual_session_report(session_id)


@pytest.mark.asyncio
async def test_get_period_session_report(dummy_session, dummy_patient, dummy_user):
    svc = ReportsService(None)

    start_date = datetime.now()
    end_date = datetime.now()

    svc.repository = MagicMock()
    svc.repository.get_sessions_in_period = AsyncMock(return_value=[dummy_session])
    svc._load_cache_maps = AsyncMock(
        return_value=({dummy_session.patient_id: dummy_patient}, {dummy_session.caregiver_id: dummy_user})
    )

    items, next_cursor = await svc.get_period_session_report(start_date, end_date, limit=10)

    assert len(items) == 1
    assert items[0].id == dummy_session.id
    assert next_cursor is None


@pytest.mark.asyncio
async def test_get_period_session_report_with_cursor(dummy_session, dummy_patient, dummy_user):
    svc = ReportsService(None)

    start_date = datetime.now()
    end_date = datetime.now()
    cursor = "2023-01-01T00:00:00|12345678-1234-1234-1234-123456789abc"

    svc.repository = MagicMock()
    # Return more than limit to trigger cursor
    svc.repository.get_sessions_in_period = AsyncMock(return_value=[dummy_session, dummy_session])
    svc._load_cache_maps = AsyncMock(
        return_value=({dummy_session.patient_id: dummy_patient}, {dummy_session.caregiver_id: dummy_user})
    )

    items, next_cursor = await svc.get_period_session_report(start_date, end_date, limit=1, cursor=cursor)

    assert len(items) == 1
    assert next_cursor is not None


@pytest.mark.asyncio
async def test_get_all_time_session_report(dummy_session, dummy_patient, dummy_user):
    svc = ReportsService(None)

    svc.repository = MagicMock()
    svc.repository.get_all_sessions = AsyncMock(return_value=[dummy_session])
    svc._load_cache_maps = AsyncMock(
        return_value=({dummy_session.patient_id: dummy_patient}, {dummy_session.caregiver_id: dummy_user})
    )

    items, next_cursor = await svc.get_all_time_session_report(limit=10)

    assert len(items) == 1
    assert items[0].id == dummy_session.id
    assert next_cursor is None


@pytest.mark.asyncio
async def test_get_caregiver_list(dummy_user):
    svc = ReportsService(None)

    svc.repository = MagicMock()
    svc.repository.get_caregiver_list = AsyncMock(return_value=[dummy_user])

    result = await svc.get_caregiver_list(limit=10, offset=0)

    assert len(result) == 1
    assert result[0].id == dummy_user.id
    assert result[0].full_name == "Jane Smith"


@pytest.mark.asyncio
async def test_get_caregiver_performance():
    svc = ReportsService(None)

    # Mock performance row
    performance_row = MagicMock()
    performance_row.id = uuid4()
    performance_row.first_name = "Jane"
    performance_row.last_name = "Smith"
    performance_row.email = "jane@example.com"
    performance_row.is_active = True
    performance_row.total_sessions = 10
    performance_row.completed_sessions = 8
    performance_row.avg_duration_minutes = 45.5

    svc.repository = MagicMock()
    svc.repository.get_caregiver_performance = AsyncMock(return_value=[performance_row])
    svc.repository.get_caregiver_avg_ratings = AsyncMock(return_value={performance_row.id: 4.2})

    result = await svc.get_caregiver_performance()

    assert len(result) == 1
    assert result[0].caregiver_id == performance_row.id
    assert result[0].total_sessions == 10
    assert result[0].avg_rating == 4.2


@pytest.mark.asyncio
async def test_get_patient_list(dummy_patient):
    svc = ReportsService(None)

    svc.repository = MagicMock()
    svc.repository.get_patient_list = AsyncMock(return_value=[dummy_patient])

    result = await svc.get_patient_list(limit=10, offset=0)

    assert len(result) == 1
    assert result[0].id == dummy_patient.id
    assert result[0].full_name == "John Doe"


@pytest.mark.asyncio
async def test_get_patient_summary():
    svc = ReportsService(None)

    patient_id = uuid4()
    summary_data = {"total_sessions": 5, "avg_rating": 4.0, "distinct_caregivers": 3}

    svc.repository = MagicMock()
    svc.repository.get_patient_summary = AsyncMock(return_value=summary_data)

    result = await svc.get_patient_summary(patient_id)

    assert result.patient_id == patient_id
    assert result.total_sessions == 5
    assert result.avg_rating == 4.0


@pytest.mark.asyncio
async def test_get_patient_sessions():
    svc = ReportsService(None)

    patient_id = uuid4()
    session_row = {
        "id": uuid4(),
        "caregiver_id": uuid4(),
        "check_in_time": datetime.now(),
        "check_out_time": datetime.now(),
        "status": "completed",
        "rating": 5,
        "feedback_comment": "Great!",
    }

    svc.repository = MagicMock()
    svc.repository.get_patient_sessions = AsyncMock(return_value=([session_row], 1))
    svc.repository.get_users_by_ids = AsyncMock(
        return_value={session_row["caregiver_id"]: MagicMock(first_name="Jane", last_name="Smith")}
    )
    svc.repository.get_patients_by_ids = AsyncMock(return_value={patient_id: MagicMock(careplan_type="premium")})

    result = await svc.get_patient_sessions(patient_id)

    assert len(result.items) == 1
    assert result.total == 1
    assert result.items[0].session_id == session_row["id"]


@pytest.mark.asyncio
async def test_get_feedback_report(dummy_feedback):
    svc = ReportsService(None)

    svc.repository = MagicMock()
    svc.repository.get_feedback_list = AsyncMock(return_value=[dummy_feedback])
    svc.repository.get_patients_by_ids = AsyncMock(
        return_value={
            dummy_feedback["patient_id"]: MagicMock(first_name="John", last_name="Doe", careplan_type="standard")
        }
    )
    svc.repository.get_users_by_ids = AsyncMock(
        return_value={dummy_feedback["caregiver_id"]: MagicMock(first_name="Jane", last_name="Smith")}
    )

    result = await svc.get_feedback_report(limit=10)

    assert len(result.items) == 1
    assert result.items[0].id == dummy_feedback["id"]
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_get_feedback_summary():
    svc = ReportsService(None)

    summary_data = {"total_feedback": 10, "avg_rating": 4.2, "positive_feedback": 8}

    svc.repository = MagicMock()
    svc.repository.get_feedback_summary = AsyncMock(return_value=summary_data)

    result = await svc.get_feedback_summary()

    assert result.total_feedback == 10
    assert result.avg_rating == 4.2
    assert result.positive_feedback == 8


@pytest.mark.asyncio
async def test_get_caregiver_feedback():
    svc = ReportsService(None)

    caregiver_id = uuid4()
    feedback_row = {
        "id": uuid4(),
        "patient_id": uuid4(),
        "rating": 4,
        "patient_feedback": "Good",
        "session_date": datetime.now(),
        "feedback_date": datetime.now(),
    }

    svc.repository = MagicMock()
    svc.repository.get_caregiver_feedback = AsyncMock(return_value=([feedback_row], 1))
    svc.repository.get_patients_by_ids = AsyncMock(
        return_value={feedback_row["patient_id"]: MagicMock(first_name="John", last_name="Doe")}
    )
    svc.repository.get_users_by_ids = AsyncMock(
        return_value={caregiver_id: MagicMock(first_name="Jane", last_name="Smith")}
    )

    result = await svc.get_caregiver_feedback(caregiver_id)

    assert len(result.items) == 1
    assert result.total == 1
    assert result.items[0].caregiver_id == caregiver_id


def test_generate_csv():
    svc = ReportsService(None)

    # Mock session data
    session = MagicMock()
    session.id = uuid4()
    session.patient_id = uuid4()
    session.patient_full_name = "John Doe"
    session.patient_email = "john@example.com"
    session.careplan_type = "standard"
    session.caregiver_id = uuid4()
    session.caregiver_full_name = "Jane Smith"
    session.caregiver_email = "jane@example.com"
    session.check_in_time = datetime.now()
    session.check_out_time = datetime.now()
    session.duration_minutes = 60
    session.status = "completed"
    session.caregiver_notes = "Good session"
    session.created_at = datetime.now()
    session.updated_at = datetime.now()

    buffer = svc.generate_csv([session])

    assert isinstance(buffer, BytesIO)
    # Check that buffer contains CSV data
    buffer.seek(0)
    content = buffer.read().decode("utf-8")
    assert "ID" in content
    assert "Patient Name" in content


def test_generate_pdf():
    svc = ReportsService(None)

    # Mock session data
    session = MagicMock()
    session.id = uuid4()
    session.patient_id = uuid4()
    session.patient_full_name = "John Doe"
    session.patient_email = "john@example.com"
    session.careplan_type = "standard"
    session.caregiver_id = uuid4()
    session.caregiver_full_name = "Jane Smith"
    session.caregiver_email = "jane@example.com"
    session.check_in_time = datetime.now()
    session.check_out_time = datetime.now()
    session.duration_minutes = 60
    session.status = "completed"
    session.caregiver_notes = "Good session"

    buffer = svc.generate_pdf([session], "Test Report")

    assert isinstance(buffer, BytesIO)


def test_generate_caregiver_csv():
    svc = ReportsService(None)

    # Mock caregiver performance data
    caregiver = MagicMock()
    caregiver.caregiver_id = uuid4()
    caregiver.caregiver_full_name = "Jane Smith"
    caregiver.caregiver_email = "jane@example.com"
    caregiver.total_sessions = 10
    caregiver.completed_sessions = 8
    caregiver.avg_rating = 4.2
    caregiver.avg_duration_minutes = 45.5
    caregiver.status = "Active"

    buffer = svc.generate_caregiver_csv([caregiver])

    assert isinstance(buffer, BytesIO)
    buffer.seek(0)
    content = buffer.read().decode("utf-8")
    assert "Caregiver Name" in content


def test_generate_feedback_csv(dummy_feedback):
    svc = ReportsService(None)

    # Mock feedback item
    feedback = MagicMock()
    feedback.id = dummy_feedback["id"]
    feedback.session_id = dummy_feedback["care_session_id"]
    feedback.patient_full_name = "John Doe"
    feedback.caregiver_full_name = "Jane Smith"
    feedback.careplan_type = "standard"
    feedback.feedback_date = dummy_feedback["feedback_date"]
    feedback.rating = dummy_feedback["rating"]
    feedback.comment = dummy_feedback["patient_feedback"]

    buffer = svc.generate_feedback_csv([feedback])

    assert isinstance(buffer, BytesIO)
    buffer.seek(0)
    content = buffer.read().decode("utf-8")
    assert "Patient" in content


def test_generate_patient_sessions_csv():
    svc = ReportsService(None)

    # Mock patient session item
    session = MagicMock()
    session.session_id = uuid4()
    session.caregiver_id = uuid4()
    session.caregiver_full_name = "Jane Smith"
    session.careplan_type = "standard"
    session.check_in_time = datetime.now()
    session.check_out_time = datetime.now()
    session.duration_minutes = 60
    session.status = "completed"
    session.rating = 5
    session.feedback_comment = "Great!"

    buffer = svc.generate_patient_sessions_csv([session])

    assert isinstance(buffer, BytesIO)
    buffer.seek(0)
    content = buffer.read().decode("utf-8")
    assert "Session ID" in content


def test_generate_caregiver_feedback_csv():
    svc = ReportsService(None)

    # Mock caregiver feedback item
    feedback = MagicMock()
    feedback.caregiver_id = uuid4()
    feedback.caregiver_full_name = "Jane Smith"
    feedback.patient_id = uuid4()
    feedback.patient_full_name = "John Doe"
    feedback.session_date = datetime.now()
    feedback.rating = 4
    feedback.comment = "Good service"
    feedback.feedback_date = datetime.now()

    buffer = svc.generate_caregiver_feedback_csv([feedback])

    assert isinstance(buffer, BytesIO)
    buffer.seek(0)
    content = buffer.read().decode("utf-8")
    assert "Caregiver Name" in content
