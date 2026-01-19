import io
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

import app.reports.router as reports_router
from app.auth.middleware import verify_token
from app.main import app


@pytest.fixture
def client_and_service(monkeypatch, fake_jwt_payload):
    service = AsyncMock()
    monkeypatch.setattr(reports_router, "ReportsService", lambda *_: service)
    app.dependency_overrides[verify_token] = lambda: fake_jwt_payload

    with TestClient(app) as client:
        yield client, service

    app.dependency_overrides.clear()


def test_get_period_and_all_time_session_reports(client_and_service):
    client, service = client_and_service

    # Period session report expects items and next_cursor
    service.get_period_session_report.return_value = ([], None)
    resp = client.get(
        "/reports/sessions/period", params={"start_date": "2025-01-01T00:00:00", "end_date": "2025-01-02T00:00:00"}
    )
    assert resp.status_code == 200

    # All time report
    service.get_all_time_session_report.return_value = ([], None)
    resp2 = client.get("/reports/sessions/all")
    assert resp2.status_code == 200


def test_download_period_and_all_time_csv_and_pdf(client_and_service):
    client, service = client_and_service

    # Make service return a list of sessions
    service.get_period_session_report.return_value = ([], None)
    # generate_csv/pdf should return a file-like object
    # generate_csv/pdf are synchronous helpers that return file-like objects
    service.generate_csv = lambda sessions: io.BytesIO(b"a,b,c\n1,2,3")
    service.generate_pdf = lambda sessions, title=None: io.BytesIO(b"%PDF-1.4")

    # CSV format
    resp = client.get(
        "/reports/sessions/period/download",
        params={"start_date": "2025-01-01T00:00:00", "end_date": "2025-01-02T00:00:00", "format": "csv"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/csv")

    # PDF format
    resp2 = client.get(
        "/reports/sessions/period/download",
        params={"start_date": "2025-01-01T00:00:00", "end_date": "2025-01-02T00:00:00", "format": "pdf"},
    )
    assert resp2.status_code == 200
    assert resp2.headers.get("content-type", "").startswith("application/pdf")


def test_error_cases_reports(client_and_service):
    """Test error cases for reports endpoints"""
    client, service = client_and_service

    from app.care_sessions.exceptions import CareSessionNotFoundException

    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    # Test 404 for non-existent session report
    service.get_individual_session_report.side_effect = CareSessionNotFoundException(session_id)
    resp = client.get(f"/reports/sessions/{session_id}")
    assert resp.status_code == 404


def test_validation_cases_reports(client_and_service):
    """Test validation cases for reports endpoints"""
    client, service = client_and_service

    # Setup mock return values for service methods that might be called
    service.get_period_session_report.return_value = ([], None)

    # Test invalid UUID format
    resp = client.get("/reports/sessions/invalid-uuid")
    assert resp.status_code == 422

    # Test invalid date format
    resp = client.get(
        "/reports/sessions/period", params={"start_date": "invalid-date", "end_date": "2025-01-02T00:00:00"}
    )
    assert resp.status_code == 422

    # Test invalid format parameter - FastAPI enum validation returns 400 when constraint fails
    resp = client.get(
        "/reports/sessions/period/download",
        params={"start_date": "2025-01-01T00:00:00", "end_date": "2025-01-02T00:00:00", "format": "invalid"},
    )
    assert resp.status_code in [400, 422]  # Accept both 400 (bad request) and 422 (validation error)

    # Test missing required parameters - missing dates returns 400 (bad request) not 422 (validation error)
    resp = client.get("/reports/sessions/period/download", params={"format": "csv"})  # Missing dates
    assert resp.status_code in [400, 422]  # Accept both since missing params can be either


def test_additional_reports_endpoints(client_and_service):
    """Test additional reports endpoints"""
    client, service = client_and_service

    from uuid import UUID
    from app.reports.schemas import PatientSummary

    # Mock return values
    service.get_caregiver_list.return_value = []
    service.get_caregiver_performance.return_value = []
    service.get_patient_list.return_value = []

    # Create proper PatientSummary object with valid UUID
    patient_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    service.get_patient_summary.return_value = PatientSummary(
        patient_id=patient_id, total_sessions=0, avg_rating=None, distinct_caregivers=0
    )
    service.get_patient_sessions.return_value = MagicMock(items=[], total=0, limit=10, offset=0)
    service.get_feedback_report.return_value = MagicMock(items=[], next_cursor=None)
    service.get_feedback_summary.return_value = MagicMock(total_feedbacks=0, average_rating=0, rating_distribution={})
    service.get_caregiver_feedback.return_value = MagicMock(items=[], total=0, limit=10, offset=0)

    # Test caregiver list
    resp = client.get("/reports/caregivers/")
    assert resp.status_code == 200

    # Test caregiver performance
    resp = client.get("/reports/caregivers/performance")
    assert resp.status_code == 200

    # Test patient list
    resp = client.get("/reports/patients/")
    assert resp.status_code == 200

    # Test patient summary
    resp = client.get(f"/reports/patients/{patient_id}/summary")
    assert resp.status_code == 200

    # Test patient sessions
    resp = client.get(f"/reports/patients/{patient_id}/sessions")
    assert resp.status_code == 200

    # Test feedback report
    resp = client.get("/reports/feedback/")
    assert resp.status_code == 200

    # Test feedback summary
    resp = client.get("/reports/feedback/summary")
    assert resp.status_code == 200

    # Test caregiver feedback
    caregiver_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    resp = client.get(f"/reports/caregivers/{caregiver_id}/feedback")
    assert resp.status_code == 200


def test_reports_download_formats(client_and_service):
    """Test various download formats for reports"""
    client, service = client_and_service

    # Mock service methods
    service.get_caregiver_performance.return_value = []
    service.get_patient_sessions.return_value = MagicMock(items=[], total=0, limit=10, offset=0)
    service.get_feedback_report.return_value = MagicMock(items=[], next_cursor=None)
    service.get_caregiver_feedback.return_value = MagicMock(items=[], total=0, limit=10, offset=0)

    # CSV/PDF generation functions
    service.generate_caregiver_csv = lambda data: io.BytesIO(b"header\n")
    service.generate_caregiver_pdf = lambda data, title: io.BytesIO(b"%PDF-1.4")
    service.generate_patient_sessions_csv = lambda data: io.BytesIO(b"header\n")
    service.generate_patient_sessions_pdf = lambda data, title: io.BytesIO(b"%PDF-1.4")
    service.generate_feedback_csv = lambda data: io.BytesIO(b"header\n")
    service.generate_feedback_pdf = lambda data, title: io.BytesIO(b"%PDF-1.4")
    service.generate_caregiver_feedback_csv = lambda data: io.BytesIO(b"header\n")
    service.generate_caregiver_feedback_pdf = lambda data, title: io.BytesIO(b"%PDF-1.4")

    # Test caregiver performance downloads
    resp = client.get("/reports/caregivers/download", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/csv")

    resp = client.get("/reports/caregivers/download", params={"format": "pdf"})
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/pdf")

    # Test patient sessions downloads
    patient_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    resp = client.get(f"/reports/patients/{patient_id}/download", params={"format": "csv"})
    assert resp.status_code == 200

    # Test feedback downloads
    resp = client.get("/reports/feedback/download", params={"format": "pdf"})
    assert resp.status_code == 200

    # Test caregiver feedback downloads
    caregiver_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    resp = client.get(f"/reports/caregivers/{caregiver_id}/feedback/download", params={"format": "csv"})
    assert resp.status_code == 200
