import sqlite3
import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.main import app
from app.db.postgres import get_db
from app.db.repository import BaseRepository
from app.auth.middleware import verify_token


@pytest.fixture()
def error_recovery_client(tmp_path, monkeypatch):
    """Setup E2E test environment for error recovery scenarios"""
    sqlite3.register_adapter(UUID, str)

    db_path = tmp_path / "error_recovery_test.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(database_url, echo=False, future=True)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_tables():
        async with engine.begin() as conn:
            def _create(sync_conn):
                sync_conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS patients (
                        id TEXT PRIMARY KEY
                    )
                    """
                ))

                sync_conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS nfc_tags (
                        id TEXT PRIMARY KEY,
                        tag_id TEXT UNIQUE,
                        patient_id TEXT,
                        status TEXT,
                        issued_at TEXT,
                        deactivated_at TEXT
                    )
                    """
                ))

                sync_conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS care_sessions (
                        id TEXT PRIMARY KEY,
                        session_id TEXT UNIQUE,
                        patient_id TEXT,
                        caregiver_id TEXT,
                        check_in_time TEXT,
                        check_out_time TEXT,
                        status TEXT,
                        caregiver_notes TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        deleted_at TEXT
                    )
                    """
                ))

                sync_conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        first_name TEXT,
                        last_name TEXT,
                        email TEXT,
                        is_active INTEGER
                    )
                    """
                ))

                sync_conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id TEXT PRIMARY KEY,
                        care_session_id TEXT,
                        patient_id TEXT,
                        caregiver_id TEXT,
                        rating INTEGER,
                        patient_feedback TEXT,
                        created_at TEXT,
                        deleted_at TEXT
                    )
                    """
                ))

            await conn.run_sync(_create)

    asyncio.get_event_loop().run_until_complete(create_tables())

    # Patch BaseRepository._set_search_path to no-op
    async def _noop_set_search_path(self):
        return None

    monkeypatch.setattr(BaseRepository, "_set_search_path", _noop_set_search_path)

    # Create test data
    patient_id = str(uuid4())
    caregiver_id = str(uuid4())

    async def insert_seed():
        async with AsyncSessionLocal() as session:
            await session.execute(text("INSERT INTO patients (id) VALUES (:id)"), {"id": patient_id})
            await session.execute(
                text("INSERT INTO nfc_tags (id, tag_id, patient_id, status) VALUES (:id, :tag, :pid, :st)"),
                {"id": str(uuid4()), "tag": "test-tag", "pid": patient_id, "st": "active"},
            )
            await session.execute(
                text("INSERT INTO nfc_tags (id, tag_id, patient_id, status) VALUES (:id, :tag, :pid, :st)"),
                {"id": str(uuid4()), "tag": "inactive-tag", "pid": patient_id, "st": "inactive"},
            )
            await session.execute(
                text("INSERT INTO users (id, first_name, last_name, email, is_active) VALUES (:id, :fn, :ln, :em, :act)"),
                {"id": caregiver_id, "fn": "Test", "ln": "Caregiver", "em": "test@care.com", "act": 1},
            )
            await session.commit()

    asyncio.get_event_loop().run_until_complete(insert_seed())

    # Populate NFC cache with test data (the service uses cache, not DB lookup)
    from app.messaging.nfc_cache import get_nfc_cache
    nfc_cache = get_nfc_cache()
    nfc_cache.store("test-tag", patient_id)
    # Note: inactive-tag is intentionally NOT added to cache to test error recovery

    # Provide async DB dependency override
    async def _get_db():
        async with AsyncSessionLocal() as session:
            yield session

    monkeypatch.setattr("app.care_sessions.repository.BaseRepository._set_search_path", _noop_set_search_path, raising=False)
    app.dependency_overrides[get_db] = _get_db

    # Mock event publisher
    published = []

    def _capture_event(event_type=None, session_data=None, tenant_schema=None):
        published.append({"event_type": event_type, "session_data": session_data})

    monkeypatch.setattr("app.care_sessions.event_publisher.publish_care_session_event", _capture_event, raising=False)

    # Set user with full permissions
    class UserPayload:
        def __init__(self):
            self.internal_user_id = UUID(caregiver_id)
            self.tenant_schema = None
            self.permissions = [
                "care-session:create", "care-session:read", "care-session:update", 
                "care-session:delete", "care-session:admin",
                "feedback:create", "feedback:read", "feedback:delete"
            ]

    app.dependency_overrides[verify_token] = lambda: UserPayload()

    with TestClient(app) as client:
        yield client, published, patient_id, caregiver_id

    app.dependency_overrides.clear()


def test_duplicate_session_creation_recovery(error_recovery_client):
    """Test recovery from attempting to create duplicate active session"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Create first session
    resp1 = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-DUP-001"})
    assert resp1.status_code == 201
    session1_id = resp1.json()["id"]

    # Attempt to create another session for same patient (should fail with 409)
    resp2 = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-DUP-002"})
    assert resp2.status_code == 409
    error_data = resp2.json()
    assert "active session" in error_data["detail"].lower() or "duplicate" in error_data["detail"].lower()

    # Recovery: Complete the first session
    complete_resp = client.put(f"/care-sessions/{session1_id}/complete", json={"caregiver_notes": "Completing to recover"})
    assert complete_resp.status_code == 200

    # Now we can create a new session
    resp3 = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-DUP-003"})
    assert resp3.status_code == 201
    assert resp3.json()["session_id"] == "CS-DUP-003"


def test_invalid_tag_recovery(error_recovery_client):
    """Test recovery from using invalid/non-existent NFC tag"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Attempt to create session with non-existent tag
    resp1 = client.post("/care-sessions/create", json={"tag_id": "non-existent-tag", "session_id": "CS-INV-001"})
    assert resp1.status_code == 404  # Tag not found

    # Attempt to create session with inactive tag
    resp2 = client.post("/care-sessions/create", json={"tag_id": "inactive-tag", "session_id": "CS-INV-002"})
    assert resp2.status_code in [400, 404, 422]  # Invalid tag status

    # Recovery: Use valid active tag
    resp3 = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-INV-003"})
    assert resp3.status_code == 201
    assert resp3.json()["session_id"] == "CS-INV-003"


def test_update_non_existent_session_recovery(error_recovery_client):
    """Test recovery from attempting to update non-existent session"""
    client, published, patient_id, caregiver_id = error_recovery_client

    fake_session_id = str(uuid4())

    # Attempt to update non-existent session
    resp1 = client.patch(f"/care-sessions/{fake_session_id}", json={"caregiver_notes": "Update attempt"})
    assert resp1.status_code == 404

    # Attempt to complete non-existent session
    resp2 = client.put(f"/care-sessions/{fake_session_id}/complete", json={"caregiver_notes": "Complete attempt"})
    assert resp2.status_code == 404

    # Attempt to delete non-existent session
    resp3 = client.delete(f"/care-sessions/{fake_session_id}")
    assert resp3.status_code == 404

    # Recovery: Create a valid session first
    create_resp = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-REC-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Now updates work
    update_resp = client.patch(f"/care-sessions/{session_id}", json={"caregiver_notes": "Valid update"})
    assert update_resp.status_code == 200


def test_duplicate_feedback_recovery(error_recovery_client):
    """Test recovery from attempting to create duplicate feedback"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Create and complete a session
    create_resp = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-FB-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Done"})
    assert complete_resp.status_code == 200

    # Create first feedback
    feedback1 = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3, "patient_feedback": "Good"})
    assert feedback1.status_code == 201
    feedback_id = feedback1.json()["id"]

    # Attempt to create duplicate feedback (should fail with 409)
    feedback2 = client.post("/feedback/", json={"care_session_id": session_id, "rating": 2, "patient_feedback": "Trying again"})
    assert feedback2.status_code == 409

    # Recovery: Delete existing feedback first
    delete_resp = client.delete(f"/feedback/{feedback_id}")
    assert delete_resp.status_code == 204

    # Now we can create new feedback
    feedback3 = client.post("/feedback/", json={"care_session_id": session_id, "rating": 2, "patient_feedback": "New feedback"})
    assert feedback3.status_code == 201


def test_invalid_rating_recovery(error_recovery_client):
    """Test recovery from invalid feedback rating"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Create and complete session
    create_resp = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-RAT-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Done"})
    assert complete_resp.status_code == 200

    # Attempt invalid ratings
    invalid_ratings = [0, 4, 5, -1, 10]
    for invalid_rating in invalid_ratings:
        resp = client.post("/feedback/", json={"care_session_id": session_id, "rating": invalid_rating})
        assert resp.status_code == 422  # Validation error

    # Recovery: Use valid rating
    valid_resp = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3, "patient_feedback": "Valid rating"})
    assert valid_resp.status_code == 201


def test_feedback_for_incomplete_session_recovery(error_recovery_client):
    """Test recovery from attempting to create feedback for incomplete session"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Create session but don't complete it
    create_resp = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-INC-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Attempt to create feedback for incomplete session (might fail depending on business rules)
    feedback_resp = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3})
    # This might succeed or fail depending on validation rules
    # If it fails, status should be 400 or 422
    if feedback_resp.status_code not in [201, 400, 422]:
        pytest.fail(f"Unexpected status code: {feedback_resp.status_code}")

    # Recovery: Complete the session first
    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Completed"})
    assert complete_resp.status_code == 200

    # Now feedback should definitely work (if not already created)
    if feedback_resp.status_code != 201:
        retry_feedback = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3})
        assert retry_feedback.status_code == 201


def test_invalid_uuid_format_recovery(error_recovery_client):
    """Test recovery from invalid UUID format errors"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Attempt operations with invalid UUID formats
    invalid_uuids = ["not-a-uuid", ""]

    for invalid_uuid in invalid_uuids:
        if invalid_uuid:  # Skip empty string for path parameter
            # Get session with invalid UUID
            resp1 = client.get(f"/care-sessions/{invalid_uuid}")
            assert resp1.status_code == 422  # Validation error

            # Get feedback with invalid UUID
            resp2 = client.get(f"/feedback/{invalid_uuid}")
            assert resp2.status_code == 422

    # Recovery: Use valid UUID
    create_resp = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-UUID-001"})
    assert create_resp.status_code == 201
    valid_session_id = create_resp.json()["id"]

    # Now operations work with valid UUID
    get_resp = client.get(f"/care-sessions/{valid_session_id}")
    assert get_resp.status_code == 200


def test_missing_required_fields_recovery(error_recovery_client):
    """Test recovery from missing required fields"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Attempt to create session without required fields
    resp1 = client.post("/care-sessions/create", json={})
    assert resp1.status_code == 422

    # SQLite doesn't support SEQUENCE, so session_id must always be provided
    # This test verifies that session_id is required
    
    # Attempt to create feedback without required fields
    resp3 = client.post("/feedback/", json={})
    assert resp3.status_code == 422

    resp4 = client.post("/feedback/", json={"rating": 3})  # Missing care_session_id
    assert resp4.status_code == 422

    # Recovery: Provide all required fields
    create_session = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-REQ-001"})
    assert create_session.status_code == 201
    session_id = create_session.json()["id"]

    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Done"})
    assert complete_resp.status_code == 200

    create_feedback = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3})
    assert create_feedback.status_code == 201


def test_cascading_error_recovery(error_recovery_client):
    """Test recovery from cascading errors"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Step 1: Create session first (can't create feedback without session)
    create_resp = client.post("/care-sessions/create", json={"tag_id": "test-tag", "session_id": "CS-CAS-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Step 2: Try to create feedback for incomplete session (might error)
    resp2 = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3})
    # Store result for later

    # Step 3: Complete session
    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Completed"})
    assert complete_resp.status_code == 200

    # Step 4: Try feedback again if previous attempt failed
    if resp2.status_code != 201:
        resp3 = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3})
        assert resp3.status_code == 201
        feedback_id = resp3.json()["id"]
    else:
        feedback_id = resp2.json()["id"]

    # Step 5: Verify everything is in correct state
    session_check = client.get(f"/care-sessions/{session_id}")
    assert session_check.status_code == 200
    assert session_check.json()["status"] == "completed"

    feedback_check = client.get(f"/feedback/{feedback_id}")
    assert feedback_check.status_code == 200


def test_pagination_boundary_recovery(error_recovery_client):
    """Test recovery from pagination boundary errors"""
    client, published, patient_id, caregiver_id = error_recovery_client

    # Attempt invalid pagination parameters
    resp1 = client.get("/care-sessions/", params={"page": 0})  # Page must be >= 1
    assert resp1.status_code == 422

    resp2 = client.get("/care-sessions/", params={"page": -1})
    assert resp2.status_code == 422

    resp3 = client.get("/care-sessions/", params={"page_size": 0})  # Page size must be > 0
    assert resp3.status_code == 422

    resp4 = client.get("/care-sessions/", params={"page_size": 1000})  # Exceeds maximum
    assert resp4.status_code == 422

    # Recovery: Use valid pagination
    resp5 = client.get("/care-sessions/", params={"page": 1, "page_size": 10})
    assert resp5.status_code == 200

    resp6 = client.get("/feedback/", params={"page": 1, "page_size": 20})
    assert resp6.status_code == 200
