"""E2E tests for care session flow.

These tests use mocked DB since SQLite doesn't support PostgreSQL schemas.
They test the full API flow with mocked service responses.
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.auth.middleware import verify_token
from app.messaging.nfc_cache import get_nfc_cache


def create_mock_session(session_id, patient_id, status="in_progress", caregiver_notes=None, check_out_time=None):
    """Create a mock CareSession object."""
    now = datetime.now(timezone.utc)
    session = MagicMock()
    session.id = session_id
    session.session_id = f"SES-{str(session_id)[:8]}"
    session.patient_id = patient_id
    session.caregiver_id = uuid4()
    session.status = status
    session.check_in_time = now
    session.check_out_time = check_out_time or (now if status == "completed" else None)
    session.caregiver_notes = caregiver_notes
    session.created_at = now
    session.updated_at = now
    session.deleted_at = None
    return session


@pytest.mark.asyncio
async def test_full_care_session_flow(client: AsyncClient, mock_jwt_payload):
    """Test complete care session flow: create → get → complete."""
    cache = get_nfc_cache()
    patient_id = uuid4()
    session_id = uuid4()
    tag_id = "TEST_TAG_E2E_FLOW"
    cache.store(tag_id, str(patient_id))
    
    mock_session = create_mock_session(session_id, patient_id)
    completed_session = create_mock_session(
        session_id, patient_id,
        status="completed",
        caregiver_notes="Patient visited successfully"
    )
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    try:
        # Mock service methods
        with patch("app.care_sessions.router.CareSessionService") as MockService:
            mock_svc = AsyncMock()
            MockService.return_value = mock_svc
            mock_svc.create_session.return_value = mock_session
            mock_svc.get_session.return_value = mock_session
            mock_svc.complete_session.return_value = completed_session
            
            # 1. Create session
            create_response = await client.post(
                "/care-sessions/create",
                json={"tag_id": tag_id},
                headers={"Authorization": "Bearer mock_token"}
            )
            assert create_response.status_code == 201
            session_data = create_response.json()
            assert session_data["patient_id"] == str(patient_id)
            assert session_data["status"] == "in_progress"
            
            # 2. Get session
            get_response = await client.get(
                f"/care-sessions/{session_id}",
                headers={"Authorization": "Bearer mock_token"}
            )
            assert get_response.status_code == 200
            assert get_response.json()["id"] == str(session_id)
            
            # 3. Complete session
            complete_response = await client.put(
                f"/care-sessions/{session_id}/complete",
                json={"caregiver_notes": "Patient visited successfully"},
                headers={"Authorization": "Bearer mock_token"}
            )
            assert complete_response.status_code == 200
            completed_data = complete_response.json()
            assert completed_data["status"] == "completed"
            assert completed_data["caregiver_notes"] == "Patient visited successfully"
            assert completed_data["check_out_time"] is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_sessions_empty(client: AsyncClient, mock_jwt_payload):
    """Test listing sessions when none exist."""
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    try:
        response = await client.get(
            "/care-sessions/",
            headers={"Authorization": "Bearer mock_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sessions"] == []
        assert data["total"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session_duplicate_blocked(client: AsyncClient, mock_jwt_payload):
    """Test that duplicate active sessions are blocked."""
    from app.care_sessions.exceptions import DuplicateActiveSessionException
    
    cache = get_nfc_cache()
    patient_id = uuid4()
    tag_id = "TEST_TAG_DUP"
    cache.store(tag_id, str(patient_id))
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    try:
        # Mock service to raise duplicate exception
        with patch("app.care_sessions.router.CareSessionService") as MockService:
            mock_svc = AsyncMock()
            MockService.return_value = mock_svc
            mock_svc.create_session.side_effect = DuplicateActiveSessionException(patient_id)
            
            # Should fail with 409 Conflict (duplicate session)
            response = await client.post(
                "/care-sessions/create",
                json={"tag_id": tag_id},
                headers={"Authorization": "Bearer mock_token"}
            )
            assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()
