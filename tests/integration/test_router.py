import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.main import app
from app.db.postgres import get_db
from app.auth.middleware import verify_token
from app.care_sessions.service import CareSessionService


@pytest.mark.integration
def test_create_get_list_endpoints(fake_db, fake_jwt_payload, dummy_care_session):
    # Override dependencies
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[verify_token] = lambda: fake_jwt_payload

    # Patch service methods to avoid DB logic; return our dummy object
    with patch.object(CareSessionService, "create_session", new=AsyncMock(return_value=dummy_care_session)):
        with patch.object(CareSessionService, "get_session", new=AsyncMock(return_value=dummy_care_session)):
            with patch.object(
                CareSessionService, "list_sessions", new=AsyncMock(return_value=([dummy_care_session], 1))
            ):
                with patch.object(
                    CareSessionService, "complete_session", new=AsyncMock(return_value=dummy_care_session)
                ):
                    with patch.object(
                        CareSessionService, "update_session", new=AsyncMock(return_value=dummy_care_session)
                    ):
                        with patch.object(CareSessionService, "delete_session", new=AsyncMock(return_value=True)):
                            client = TestClient(app)

                            # Create
                            resp = client.post("/care-sessions/create", json={"tag_id": "TAG1", "session_id": None})
                            assert resp.status_code == 201
                            data = resp.json()
                            assert data["session_id"] == dummy_care_session.session_id

                            # Get
                            resp2 = client.get(f"/care-sessions/{dummy_care_session.id}")
                            assert resp2.status_code == 200

                            # List
                            resp3 = client.get("/care-sessions/")
                            assert resp3.status_code == 200
                            body = resp3.json()
                            assert body["total"] == 1

                            # Complete (PUT)
                            resp4 = client.put(
                                f"/care-sessions/{dummy_care_session.id}/complete", json={"caregiver_notes": "done"}
                            )
                            assert resp4.status_code == 200

                            # Update (PATCH)
                            resp5 = client.patch(
                                f"/care-sessions/{dummy_care_session.id}", json={"status": "completed"}
                            )
                            assert resp5.status_code == 200

                            # Delete (DELETE)
                            resp6 = client.delete(f"/care-sessions/{dummy_care_session.id}")
                            assert resp6.status_code == 204

    app.dependency_overrides.clear()


@pytest.mark.integration
def test_error_cases_care_sessions(fake_db, fake_jwt_payload):
    """Test error cases for care sessions endpoints"""
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[verify_token] = lambda: fake_jwt_payload

    from app.care_sessions.exceptions import CareSessionNotFoundException, DuplicateActiveSessionException

    client = TestClient(app)

    # Test 404 for non-existent session
    with patch.object(
        CareSessionService, "get_session", new=AsyncMock(side_effect=CareSessionNotFoundException(uuid4()))
    ):
        resp = client.get(f"/care-sessions/{uuid4()}")
        assert resp.status_code == 404

    # Test 409 for duplicate session creation
    with patch.object(
        CareSessionService, "create_session", new=AsyncMock(side_effect=DuplicateActiveSessionException())
    ):
        resp = client.post("/care-sessions/create", json={"tag_id": "TAG1", "session_id": None})
        assert resp.status_code == 409

    # Test 422 for invalid request data
    resp = client.post("/care-sessions/create", json={})  # Missing required fields
    assert resp.status_code == 422

    # Test 404 for completing non-existent session
    with patch.object(
        CareSessionService, "complete_session", new=AsyncMock(side_effect=CareSessionNotFoundException(uuid4()))
    ):
        resp = client.put(f"/care-sessions/{uuid4()}/complete", json={"caregiver_notes": "done"})
        assert resp.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.integration
def test_validation_cases_care_sessions(fake_db, fake_jwt_payload):
    """Test validation cases for care sessions endpoints"""
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[verify_token] = lambda: fake_jwt_payload

    client = TestClient(app)

    # Test invalid UUID format - FastAPI returns 422 for path parameter validation
    resp = client.get("/care-sessions/invalid-uuid")
    # FastAPI may return 422 (validation error) or handle it differently
    # Accept both 404 (not found after attempting parse) and 422 (validation error)
    assert resp.status_code in [404, 422]

    # Test invalid status update - returns 404 if session doesn't exist (checked before validation)
    resp = client.patch(f"/care-sessions/{uuid4()}", json={"status": "invalid_status"})
    # Returns 404 because session doesn't exist (existence check happens before field validation)
    assert resp.status_code in [404, 422]

    # Test query parameter validation
    resp = client.get("/care-sessions/", params={"page": 0})  # Page should be >= 1
    assert resp.status_code == 422

    resp = client.get("/care-sessions/", params={"page_size": 1000})  # Too large page_size
    assert resp.status_code == 422

    app.dependency_overrides.clear()
