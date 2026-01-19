import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

import app.feedback.router as feedback_router
from app.auth.middleware import verify_token
from app.main import app


@pytest.fixture
def client_and_service(monkeypatch, fake_jwt_payload):
    # Provide a fake service whose async methods we can control
    service = AsyncMock()

    # Patch FeedbackService factory in router to return our mock
    monkeypatch.setattr(feedback_router, "FeedbackService", lambda *_: service)

    # Override token verification to return our fake payload
    app.dependency_overrides[verify_token] = lambda: fake_jwt_payload

    with TestClient(app) as client:
        yield client, service

    app.dependency_overrides.clear()


def test_create_feedback_endpoint(client_and_service):
    client, service = client_and_service

    # Create a feedback-like object with proper UUID string fields and rating
    from types import SimpleNamespace
    from datetime import datetime

    feedback_obj = SimpleNamespace(
        id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        care_session_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        patient_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        caregiver_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        rating=3,
        patient_feedback="good",
        created_at=datetime.utcnow(),
    )

    service.create_feedback.return_value = feedback_obj

    payload = {
        "care_session_id": feedback_obj.care_session_id,
        "rating": 3,
        "patient_feedback": "good",
    }

    resp = client.post("/feedback/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == 3
    service.create_feedback.assert_awaited()


def test_get_feedback_and_list_and_delete(client_and_service):
    client, service = client_and_service

    from types import SimpleNamespace
    from datetime import datetime

    feedback_obj = SimpleNamespace(
        id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        care_session_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        patient_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        caregiver_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        rating=2,
        patient_feedback="ok",
        created_at=datetime.utcnow(),
    )

    # get_feedback
    service.get_feedback_by_id.return_value = feedback_obj
    resp = client.get(f"/feedback/{feedback_obj.id}")
    assert resp.status_code == 200

    # list_feedbacks
    service.list_feedbacks.return_value = ([feedback_obj], 1)
    resp2 = client.get("/feedback/")
    assert resp2.status_code == 200
    assert resp2.json().get("total") == 1

    # delete_feedback
    service.delete_feedback.return_value = AsyncMock()
    resp3 = client.delete(f"/feedback/{feedback_obj.id}")
    assert resp3.status_code == 204


def test_metrics_endpoints(client_and_service):
    client, service = client_and_service

    from types import SimpleNamespace
    from datetime import datetime

    feedback_obj = SimpleNamespace(
        id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        care_session_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        patient_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        caregiver_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        rating=3,
        patient_feedback="nice",
        created_at=datetime.utcnow(),
    )

    # daily metrics
    service.get_daily_averages.return_value = (
        [{"date": datetime.utcnow().date(), "average_rating": 3.0, "total_feedbacks": 1}],
        [feedback_obj],
    )
    resp = client.get("/feedback/metrics/daily", params={"start_date": "2025-01-01", "end_date": "2025-01-02"})
    assert resp.status_code == 200

    # caregiver weekly
    service.get_caregiver_weekly_metrics.return_value = [feedback_obj]
    resp2 = client.get(
        f"/feedback/metrics/caregivers/{feedback_obj.caregiver_id}/weekly", params={"week_start": "2025-01-06"}
    )
    assert resp2.status_code == 200

    # patient metrics
    service.get_patient_average_rating.return_value = 2.5
    service.list_feedbacks.return_value = ([feedback_obj], 1)
    resp3 = client.get(f"/feedback/metrics/patients/{feedback_obj.patient_id}")
    assert resp3.status_code == 200

    # top caregivers weekly
    service.get_top_caregivers_of_week.return_value = [
        {"caregiver_id": feedback_obj.caregiver_id, "average_rating": 3.0, "total_feedbacks": 1}
    ]
    resp4 = client.get("/feedback/metrics/top-caregivers/weekly", params={"week_start": "2025-01-06"})
    assert resp4.status_code == 200

    # caregiver metrics period
    service.get_caregiver_average_rating.return_value = (3.0, 2)
    resp5 = client.get(f"/feedback/metrics/caregivers/{feedback_obj.caregiver_id}/period", params={"period": "weekly"})
    assert resp5.status_code == 200


def test_error_cases_feedback(client_and_service):
    """Test error cases for feedback endpoints"""
    client, service = client_and_service

    from app.feedback.exceptions import FeedbackNotFoundException, FeedbackAlreadyExistsException

    feedback_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    session_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    # Test 404 for non-existent feedback
    service.get_feedback_by_id.side_effect = FeedbackNotFoundException(feedback_id)
    resp = client.get(f"/feedback/{feedback_id}")
    assert resp.status_code == 404

    # Test 400 for duplicate feedback creation
    service.create_feedback.side_effect = FeedbackAlreadyExistsException(session_id)
    payload = {
        "care_session_id": session_id,
        "rating": 3,
        "patient_feedback": "good",
    }
    resp = client.post("/feedback/", json=payload)
    assert resp.status_code == 409

    # Test 404 for deleting non-existent feedback
    service.delete_feedback.side_effect = FeedbackNotFoundException(feedback_id)
    resp = client.delete(f"/feedback/{feedback_id}")
    assert resp.status_code == 404


def test_validation_cases_feedback(client_and_service):
    """Test validation cases for feedback endpoints"""
    client, service = client_and_service

    # Test invalid UUID format
    resp = client.get("/feedback/invalid-uuid")
    assert resp.status_code == 422

    # Test invalid rating (out of range)
    payload = {
        "care_session_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "rating": 6,  # Invalid rating
        "patient_feedback": "good",
    }
    resp = client.post("/feedback/", json=payload)
    assert resp.status_code == 422

    # Test missing required fields
    resp = client.post("/feedback/", json={"rating": 3})  # Missing care_session_id
    assert resp.status_code == 422

    # Test invalid date format in metrics
    resp = client.get("/feedback/metrics/daily", params={"start_date": "invalid-date", "end_date": "2025-01-02"})
    assert resp.status_code == 422
