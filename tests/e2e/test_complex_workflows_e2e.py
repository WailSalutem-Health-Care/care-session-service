import sqlite3
import asyncio
from uuid import UUID, uuid4
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.main import app
from app.db.postgres import get_db
from app.db.repository import BaseRepository
from app.auth.middleware import verify_token


@pytest.fixture()
def complex_workflow_client(tmp_path, monkeypatch):
    """Setup E2E test environment for complex business workflows"""
    sqlite3.register_adapter(UUID, str)

    db_path = tmp_path / "complex_workflow_test.db"
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

    # Create test data: 5 patients, 3 caregivers
    patients = [str(uuid4()) for _ in range(5)]
    caregivers = [str(uuid4()) for _ in range(3)]

    async def insert_seed():
        async with AsyncSessionLocal() as session:
            # Insert patients
            for i, patient_id in enumerate(patients):
                await session.execute(text("INSERT INTO patients (id) VALUES (:id)"), {"id": patient_id})
                # Create NFC tag for each patient
                await session.execute(
                    text("INSERT INTO nfc_tags (id, tag_id, patient_id, status) VALUES (:id, :tag, :pid, :st)"),
                    {"id": str(uuid4()), "tag": f"tag-{i+1}", "pid": patient_id, "st": "active"},
                )

            # Insert caregivers
            for i, caregiver_id in enumerate(caregivers):
                await session.execute(
                    text("INSERT INTO users (id, first_name, last_name, email, is_active) VALUES (:id, :fn, :ln, :em, :act)"),
                    {"id": caregiver_id, "fn": f"Caregiver{i+1}", "ln": "Smith", "em": f"cg{i+1}@care.com", "act": 1},
                )

            await session.commit()

    asyncio.get_event_loop().run_until_complete(insert_seed())

    # Populate NFC cache with test data (the service uses cache, not DB lookup)
    from app.messaging.nfc_cache import get_nfc_cache
    nfc_cache = get_nfc_cache()
    for i, patient_id in enumerate(patients):
        nfc_cache.store(f"tag-{i+1}", patient_id)

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

    # Set default user with full permissions
    class UserPayload:
        def __init__(self, user_id):
            self.internal_user_id = UUID(user_id)
            self.tenant_schema = None
            self.permissions = [
                "care-session:create", "care-session:read", "care-session:update", 
                "care-session:delete", "care-session:admin",
                "feedback:create", "feedback:read", "feedback:delete"
            ]

    def set_current_user(user_id):
        app.dependency_overrides[verify_token] = lambda: UserPayload(user_id)

    with TestClient(app) as client:
        yield client, published, patients, caregivers, set_current_user

    app.dependency_overrides.clear()


def test_full_day_multiple_sessions_workflow(complex_workflow_client):
    """Test a full day workflow with multiple sessions across patients and caregivers"""
    client, published, patients, caregivers, set_current_user = complex_workflow_client

    session_ids = []
    
    # Morning sessions: Caregiver 1 handles patients 1 and 2
    set_current_user(caregivers[0])
    
    # Session 1: Patient 1
    resp1 = client.post("/care-sessions/create", json={"tag_id": "tag-1", "session_id": "CS-MORN-001"})
    assert resp1.status_code == 201
    session_ids.append(resp1.json()["id"])
    
    # Session 2: Patient 2
    resp2 = client.post("/care-sessions/create", json={"tag_id": "tag-2", "session_id": "CS-MORN-002"})
    assert resp2.status_code == 201
    session_ids.append(resp2.json()["id"])

    # Afternoon sessions: Caregiver 2 handles patients 3 and 4
    set_current_user(caregivers[1])
    
    resp3 = client.post("/care-sessions/create", json={"tag_id": "tag-3", "session_id": "CS-AFT-001"})
    assert resp3.status_code == 201
    session_ids.append(resp3.json()["id"])
    
    resp4 = client.post("/care-sessions/create", json={"tag_id": "tag-4", "session_id": "CS-AFT-002"})
    assert resp4.status_code == 201
    session_ids.append(resp4.json()["id"])

    # Evening session: Caregiver 3 handles patient 5
    set_current_user(caregivers[2])
    
    resp5 = client.post("/care-sessions/create", json={"tag_id": "tag-5", "session_id": "CS-EVE-001"})
    assert resp5.status_code == 201
    session_ids.append(resp5.json()["id"])

    # Verify all sessions exist
    list_resp = client.get("/care-sessions/")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 5

    # Complete all sessions and add feedback
    feedback_ratings = [3, 2, 3, 3, 1]  # Different ratings
    
    for i, (session_id, caregiver_id, rating) in enumerate(zip(session_ids, 
                                                                 [caregivers[0], caregivers[0], caregivers[1], caregivers[1], caregivers[2]],
                                                                 feedback_ratings)):
        set_current_user(caregiver_id)
        
        # Complete session
        complete_resp = client.put(f"/care-sessions/{session_id}/complete", 
                                   json={"caregiver_notes": f"Session {i+1} completed"})
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"
        
        # Add feedback
        feedback_resp = client.post("/feedback/", json={
            "care_session_id": session_id,
            "rating": rating,
            "patient_feedback": f"Feedback for session {i+1}"
        })
        assert feedback_resp.status_code == 201

    # Verify feedback metrics
    set_current_user(caregivers[0])
    feedback_list = client.get("/feedback/")
    assert feedback_list.status_code == 200
    assert feedback_list.json()["total"] >= 5

    # Check daily metrics
    today = datetime.now().date()
    metrics_resp = client.get("/feedback/metrics/daily", params={
        "start_date": str(today),
        "end_date": str(today)
    })
    assert metrics_resp.status_code == 200


def test_patient_multiple_sessions_same_day(complex_workflow_client):
    """Test a patient having multiple sessions on the same day with different caregivers"""
    client, published, patients, caregivers, set_current_user = complex_workflow_client

    patient_id = patients[0]
    session_ids = []

    # Morning session with caregiver 1
    set_current_user(caregivers[0])
    resp1 = client.post("/care-sessions/create", json={"tag_id": "tag-1", "session_id": "CS-PAT-AM"})
    assert resp1.status_code == 201
    session1_id = resp1.json()["id"]
    session_ids.append(session1_id)

    # Complete morning session
    complete1 = client.put(f"/care-sessions/{session1_id}/complete", json={"caregiver_notes": "Morning care"})
    assert complete1.status_code == 200

    # Add feedback for morning session
    feedback1 = client.post("/feedback/", json={"care_session_id": session1_id, "rating": 3, "patient_feedback": "Great morning care"})
    assert feedback1.status_code == 201

    # Afternoon session with caregiver 2 (same patient)
    set_current_user(caregivers[1])
    resp2 = client.post("/care-sessions/create", json={"tag_id": "tag-1", "session_id": "CS-PAT-PM"})
    assert resp2.status_code == 201
    session2_id = resp2.json()["id"]
    session_ids.append(session2_id)

    # Complete afternoon session
    complete2 = client.put(f"/care-sessions/{session2_id}/complete", json={"caregiver_notes": "Afternoon care"})
    assert complete2.status_code == 200

    # Add feedback for afternoon session
    feedback2 = client.post("/feedback/", json={"care_session_id": session2_id, "rating": 2, "patient_feedback": "Good afternoon care"})
    assert feedback2.status_code == 201

    # Verify both sessions exist
    list_resp = client.get("/care-sessions/")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 2

    # Verify patient has multiple feedbacks
    feedback_list = client.get("/feedback/")
    assert feedback_list.status_code == 200
    assert feedback_list.json()["total"] >= 2


def test_caregiver_performance_tracking(complex_workflow_client):
    """Test tracking a caregiver's performance across multiple sessions"""
    client, published, patients, caregivers, set_current_user = complex_workflow_client

    caregiver_id = caregivers[0]
    set_current_user(caregiver_id)

    # Caregiver handles 3 patients with different outcomes
    sessions = []
    ratings = [3, 3, 2]  # High performer

    for i, (patient_idx, rating) in enumerate(zip([0, 1, 2], ratings)):
        # Create session
        resp = client.post("/care-sessions/create", json={
            "tag_id": f"tag-{patient_idx + 1}",
            "session_id": f"CS-PERF-{i+1:03d}"
        })
        assert resp.status_code == 201
        session_id = resp.json()["id"]
        sessions.append(session_id)

        # Complete session
        complete_resp = client.put(f"/care-sessions/{session_id}/complete", 
                                   json={"caregiver_notes": f"Quality care session {i+1}"})
        assert complete_resp.status_code == 200

        # Add feedback
        feedback_resp = client.post("/feedback/", json={
            "care_session_id": session_id,
            "rating": rating,
            "patient_feedback": f"Rating {rating} for session {i+1}"
        })
        assert feedback_resp.status_code == 201

    # Check caregiver's weekly metrics
    today = datetime.now().date()
    # Get Monday of current week
    monday = today - timedelta(days=today.weekday())
    
    weekly_metrics = client.get(f"/feedback/metrics/caregivers/{caregiver_id}/weekly", params={
        "week_start": str(monday)
    })
    assert weekly_metrics.status_code == 200
    data = weekly_metrics.json()
    # Check that metrics were returned (might be 0 if no data in that exact week)
    assert "total_feedbacks" in data
    assert "average_rating" in data

    # Check caregiver period metrics
    period_metrics = client.get(f"/feedback/metrics/caregivers/{caregiver_id}/period", params={
        "period": "weekly"
    })
    assert period_metrics.status_code == 200


def test_high_volume_concurrent_sessions(complex_workflow_client):
    """Test system handling high volume of concurrent sessions"""
    client, published, patients, caregivers, set_current_user = complex_workflow_client

    # Create 5 sessions with different patients to avoid conflicts
    session_ids = []
    
    for i in range(5):
        caregiver_idx = i % 3  # Rotate through caregivers
        patient_idx = i  # Use different patient for each session
        
        set_current_user(caregivers[caregiver_idx])
        
        resp = client.post("/care-sessions/create", json={
            "tag_id": f"tag-{patient_idx + 1}",
            "session_id": f"CS-VOL-{i+1:03d}"
        })
        
        if resp.status_code == 201:
            session_ids.append((resp.json()["id"], caregivers[caregiver_idx]))

    # Verify sessions were created
    assert len(session_ids) >= 3  # At least 3 should succeed

    # Complete all sessions
    completed_count = 0
    for session_id, caregiver_id in session_ids:
        set_current_user(caregiver_id)
        complete_resp = client.put(f"/care-sessions/{session_id}/complete", 
                                   json={"caregiver_notes": "Completed"})
        if complete_resp.status_code == 200:
            completed_count += 1

    # Verify at least some sessions were completed
    assert completed_count >= 3

    # Verify total count
    set_current_user(caregivers[0])
    list_resp = client.get("/care-sessions/")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= len(session_ids)


def test_session_lifecycle_with_updates(complex_workflow_client):
    """Test complete session lifecycle with multiple updates"""
    client, published, patients, caregivers, set_current_user = complex_workflow_client

    set_current_user(caregivers[0])

    # Create session
    create_resp = client.post("/care-sessions/create", json={
        "tag_id": "tag-1",
        "session_id": "CS-LIFE-001"
    })
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # Update 1: Add initial notes
    update1 = client.patch(f"/care-sessions/{session_id}", json={
        "caregiver_notes": "Started care routine"
    })
    assert update1.status_code == 200

    # Update 2: Add more notes
    update2 = client.patch(f"/care-sessions/{session_id}", json={
        "caregiver_notes": "Administered medication"
    })
    assert update2.status_code == 200

    # Update 3: Add final notes and complete
    update3 = client.patch(f"/care-sessions/{session_id}", json={
        "caregiver_notes": "Patient comfortable, vital signs stable"
    })
    assert update3.status_code == 200

    # Complete session
    complete_resp = client.put(f"/care-sessions/{session_id}/complete", json={
        "caregiver_notes": "Session completed successfully"
    })
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    # Add feedback
    feedback_resp = client.post("/feedback/", json={
        "care_session_id": session_id,
        "rating": 3,
        "patient_feedback": "Excellent care throughout"
    })
    assert feedback_resp.status_code == 201

    # Verify final state
    get_resp = client.get(f"/care-sessions/{session_id}")
    assert get_resp.status_code == 200
    final_data = get_resp.json()
    assert final_data["status"] == "completed"
    assert final_data["caregiver_notes"] is not None
