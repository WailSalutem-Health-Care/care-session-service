import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace
from datetime import datetime

# Ensure DB env vars exist so importing db.postgres (engine creation) doesn't error during tests
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "testdb")


@pytest.fixture
def fake_db():
    """A lightweight AsyncSession-like mock with common methods used by the code under test."""
    db = AsyncMock()

    # Provide common DB coroutine behaviors used by repository/service
    async def fake_execute(stmt):
        # Default: return a result-like object with scalar_one_or_none/scalars
        class DummyResult:
            def __init__(self, val=None):
                self._val = val

            def scalar_one_or_none(self):
                return self._val

            def scalar(self):
                return self._val

            def scalars(self):
                class _S:
                    def __init__(self, vals):
                        self._vals = vals or []

                    def all(self):
                        return self._vals

                    def __iter__(self):
                        return iter(self._vals)

                return _S([])

        return DummyResult()

    db.execute.side_effect = fake_execute
    db.add = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def fake_jwt_payload():
    # Minimal object with attributes expected by router/service
    return SimpleNamespace(
        internal_user_id="00000000-0000-0000-0000-000000000000",
        tenant_schema="test_schema",
        permissions=[
            "care-session:create",
            "care-session:read",
            "care-session:update",
            "care-session:admin",
            "care-session:report",
            # Feedback permissions used by feedback router tests
            "feedback:create",
            "feedback:read",
            "feedback:delete",
        ],
    )


@pytest.fixture
def dummy_care_session():
    # Simple object used as a return value from mocked service/repo
    return SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        session_id="CS-0001",
        patient_id="22222222-2222-2222-2222-222222222222",
        caregiver_id="33333333-3333-3333-3333-333333333333",
        check_in_time=datetime.utcnow(),
        check_out_time=None,
        status="in_progress",
        caregiver_notes=None,
        created_at=datetime.utcnow(),
        updated_at=None,
    )


@pytest.fixture
def client_with_care_session_service(monkeypatch, fake_db, fake_jwt_payload):
    """Reusable TestClient + patched CareSessionService fixture for care_sessions router tests.

    - Overrides `get_db` and `verify_token` with provided fixtures
    - Patches `app.care_sessions.router.CareSessionService` to return an AsyncMock service
    - Yields (client, service)
    """
    from app.care_sessions import router as cs_router
    from app.auth.middleware import verify_token
    from app.db.postgres import get_db
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock

    service = AsyncMock()

    # Override dependencies used by the router
    app = __import__("app.main", fromlist=["app"]).app
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[verify_token] = lambda: fake_jwt_payload

    # Patch the CareSessionService used inside the router to return our mock
    monkeypatch.setattr(cs_router, "CareSessionService", lambda db, schema: service)

    with TestClient(app) as client:
        yield client, service

    app.dependency_overrides.clear()
