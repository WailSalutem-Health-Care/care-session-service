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
def multi_user_client(tmp_path, monkeypatch):
    """Setup E2E test environment with multiple users and permissions"""
    sqlite3.register_adapter(UUID, str)

    db_path = tmp_path / "multi_user_test.db"
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

    # Create multiple patients, caregivers, and tags
    patient1_id = str(uuid4())
    patient2_id = str(uuid4())
    patient3_id = str(uuid4())
    caregiver1_id = str(uuid4())
    caregiver2_id = str(uuid4())
    admin_id = str(uuid4())
    readonly_user_id = str(uuid4())

    async def insert_seed():
        async with AsyncSessionLocal() as session:
            # Insert patients
            await session.execute(text("INSERT INTO patients (id) VALUES (:id)"), {"id": patient1_id})
            await session.execute(text("INSERT INTO patients (id) VALUES (:id)"), {"id": patient2_id})
            await session.execute(text("INSERT INTO patients (id) VALUES (:id)"), {"id": patient3_id})

            # Insert NFC tags
            await session.execute(
                text("INSERT INTO nfc_tags (id, tag_id, patient_id, status) VALUES (:id, :tag, :pid, :st)"),
                {"id": str(uuid4()), "tag": "tag-patient1", "pid": patient1_id, "st": "active"},
            )
            await session.execute(
                text("INSERT INTO nfc_tags (id, tag_id, patient_id, status) VALUES (:id, :tag, :pid, :st)"),
                {"id": str(uuid4()), "tag": "tag-patient2", "pid": patient2_id, "st": "active"},
            )
            await session.execute(
                text("INSERT INTO nfc_tags (id, tag_id, patient_id, status) VALUES (:id, :tag, :pid, :st)"),
                {"id": str(uuid4()), "tag": "tag-patient3", "pid": patient3_id, "st": "active"},
            )

            # Insert caregivers and admin
            await session.execute(
                text("INSERT INTO users (id, first_name, last_name, email, is_active) VALUES (:id, :fn, :ln, :em, :act)"),
                {"id": caregiver1_id, "fn": "John", "ln": "Caregiver", "em": "john@care.com", "act": 1},
            )
            await session.execute(
                text("INSERT INTO users (id, first_name, last_name, email, is_active) VALUES (:id, :fn, :ln, :em, :act)"),
                {"id": caregiver2_id, "fn": "Jane", "ln": "Nurse", "em": "jane@care.com", "act": 1},
            )
            await session.execute(
                text("INSERT INTO users (id, first_name, last_name, email, is_active) VALUES (:id, :fn, :ln, :em, :act)"),
                {"id": admin_id, "fn": "Admin", "ln": "User", "em": "admin@care.com", "act": 1},
            )
            await session.execute(
                text("INSERT INTO users (id, first_name, last_name, email, is_active) VALUES (:id, :fn, :ln, :em, :act)"),
                {"id": readonly_user_id, "fn": "ReadOnly", "ln": "User", "em": "readonly@care.com", "act": 1},
            )
            await session.commit()

    asyncio.get_event_loop().run_until_complete(insert_seed())

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

    # Store user contexts
    users = {
        "caregiver1": {
            "id": caregiver1_id,
            "permissions": ["care-session:create", "care-session:read", "care-session:update", "feedback:create", "feedback:read"]
        },
        "caregiver2": {
            "id": caregiver2_id,
            "permissions": ["care-session:create", "care-session:read", "care-session:update", "feedback:create", "feedback:read"]
        },
        "admin": {
            "id": admin_id,
            "permissions": ["care-session:create", "care-session:read", "care-session:update", "care-session:delete", 
                          "care-session:admin", "feedback:create", "feedback:read", "feedback:delete"]
        },
        "readonly": {
            "id": readonly_user_id,
            "permissions": ["care-session:read", "feedback:read"]
        }
    }

    with TestClient(app) as client:
        yield client, published, users, {
            "patient1": patient1_id,
            "patient2": patient2_id,
            "patient3": patient3_id
        }

    app.dependency_overrides.clear()


def set_user_context(user_info):
    """Helper to set user context for permissions testing"""
    class UserPayload:
        def __init__(self):
            self.internal_user_id = UUID(user_info["id"])
            self.tenant_schema = None
            self.permissions = user_info["permissions"]

    app.dependency_overrides[verify_token] = lambda: UserPayload()


def test_multi_caregiver_different_patients(multi_user_client):
    """Test multiple caregivers working with different patients simultaneously"""
    client, published, users, patients = multi_user_client

    # Caregiver 1 creates session for patient 1
    set_user_context(users["caregiver1"])
    resp1 = client.post("/care-sessions/create", json={"tag_id": "tag-patient1", "session_id": "CS-001"})
    assert resp1.status_code == 201
    session1_id = resp1.json()["id"]

    # Caregiver 2 creates session for patient 2
    set_user_context(users["caregiver2"])
    resp2 = client.post("/care-sessions/create", json={"tag_id": "tag-patient2", "session_id": "CS-002"})
    assert resp2.status_code == 201
    session2_id = resp2.json()["id"]

    # Caregiver 1 creates another session for patient 3
    set_user_context(users["caregiver1"])
    resp3 = client.post("/care-sessions/create", json={"tag_id": "tag-patient3", "session_id": "CS-003"})
    assert resp3.status_code == 201
    session3_id = resp3.json()["id"]

    # Admin can see all sessions
    set_user_context(users["admin"])
    list_resp = client.get("/care-sessions/")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 3

    # Complete sessions and add feedback
    set_user_context(users["caregiver1"])
    complete1 = client.put(f"/care-sessions/{session1_id}/complete", json={"caregiver_notes": "Good session"})
    assert complete1.status_code == 200

    set_user_context(users["caregiver2"])
    complete2 = client.put(f"/care-sessions/{session2_id}/complete", json={"caregiver_notes": "Great work"})
    assert complete2.status_code == 200

    # Add feedback for completed sessions
    set_user_context(users["caregiver1"])
    feedback1 = client.post("/feedback/", json={"care_session_id": session1_id, "rating": 3, "patient_feedback": "Excellent"})
    assert feedback1.status_code == 201

    set_user_context(users["caregiver2"])
    feedback2 = client.post("/feedback/", json={"care_session_id": session2_id, "rating": 2, "patient_feedback": "Good"})
    assert feedback2.status_code == 201

    # Admin can view all feedback
    set_user_context(users["admin"])
    feedback_list = client.get("/feedback/")
    assert feedback_list.status_code == 200
    assert feedback_list.json()["total"] >= 2


def test_readonly_user_permissions(multi_user_client):
    """Test that readonly users can only read, not create/update/delete"""
    client, published, users, patients = multi_user_client

    # Create a session as admin first
    set_user_context(users["admin"])
    resp = client.post("/care-sessions/create", json={"tag_id": "tag-patient1", "session_id": "CS-RO-001"})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    # Switch to readonly user
    set_user_context(users["readonly"])

    # Can read sessions
    read_resp = client.get(f"/care-sessions/{session_id}")
    assert read_resp.status_code == 200

    # Can list sessions
    list_resp = client.get("/care-sessions/")
    assert list_resp.status_code == 200

    # Cannot create session (403 Forbidden)
    create_resp = client.post("/care-sessions/create", json={"tag_id": "tag-patient2", "session_id": "CS-RO-002"})
    assert create_resp.status_code == 403

    # Cannot update session (403 Forbidden)
    update_resp = client.patch(f"/care-sessions/{session_id}", json={"status": "completed"})
    assert update_resp.status_code == 403

    # Cannot delete session (403 Forbidden)
    delete_resp = client.delete(f"/care-sessions/{session_id}")
    assert delete_resp.status_code == 403

    # Complete session as admin and add feedback
    set_user_context(users["admin"])
    client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Done"})
    feedback_resp = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3})
    assert feedback_resp.status_code == 201
    feedback_id = feedback_resp.json()["id"]

    # Switch back to readonly
    set_user_context(users["readonly"])

    # Can read feedback
    read_feedback = client.get(f"/feedback/{feedback_id}")
    assert read_feedback.status_code == 200

    # Cannot create feedback (403 Forbidden)
    create_feedback = client.post("/feedback/", json={"care_session_id": session_id, "rating": 2})
    assert create_feedback.status_code == 403

    # Cannot delete feedback (403 Forbidden)
    delete_feedback = client.delete(f"/feedback/{feedback_id}")
    assert delete_feedback.status_code == 403


def test_admin_full_permissions(multi_user_client):
    """Test that admin has full CRUD permissions"""
    client, published, users, patients = multi_user_client
    set_user_context(users["admin"])

    # Create session
    create_resp = client.post("/care-sessions/create", json={"tag_id": "tag-patient1", "session_id": "CS-ADM-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Read session
    read_resp = client.get(f"/care-sessions/{session_id}")
    assert read_resp.status_code == 200

    # Update session
    update_resp = client.patch(f"/care-sessions/{session_id}", json={"caregiver_notes": "Updated by admin"})
    assert update_resp.status_code == 200

    # Complete session
    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Completed"})
    assert complete_resp.status_code == 200

    # Create feedback
    feedback_resp = client.post("/feedback/", json={"care_session_id": session_id, "rating": 3, "patient_feedback": "Great"})
    assert feedback_resp.status_code == 201
    feedback_id = feedback_resp.json()["id"]

    # Read feedback
    read_feedback = client.get(f"/feedback/{feedback_id}")
    assert read_feedback.status_code == 200

    # Delete feedback
    delete_feedback = client.delete(f"/feedback/{feedback_id}")
    assert delete_feedback.status_code == 204

    # Delete session
    delete_resp = client.delete(f"/care-sessions/{session_id}")
    assert delete_resp.status_code == 204


def test_caregiver_cannot_delete(multi_user_client):
    """Test that regular caregivers cannot delete sessions"""
    client, published, users, patients = multi_user_client

    # Caregiver creates session
    set_user_context(users["caregiver1"])
    create_resp = client.post("/care-sessions/create", json={"tag_id": "tag-patient1", "session_id": "CS-CG-001"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Caregiver can complete session
    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={"caregiver_notes": "Done"})
    assert complete_resp.status_code == 200

    # Caregiver cannot delete session (403 Forbidden)
    delete_resp = client.delete(f"/care-sessions/{session_id}")
    assert delete_resp.status_code == 403

    # Admin can delete
    set_user_context(users["admin"])
    delete_resp = client.delete(f"/care-sessions/{session_id}")
    assert delete_resp.status_code == 204
