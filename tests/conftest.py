import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.models import Base
from app.db.postgres import get_db


# ============== E2E Tests: SQLite with temp files ==============
@pytest.fixture(scope="function")
async def e2e_db_session():
    """SQLite session for E2E tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def e2e_client(e2e_db_session):
    """E2E test client with real SQLite DB."""
    async def override_get_db():
        yield e2e_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ============== Integration/Unit Tests: Mocked DB ==============
@pytest.fixture
def mock_db_session():
    """Mocked AsyncSession for integration/unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    
    # Mock execute to return empty results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    
    return session


@pytest.fixture(scope="function")
async def client(mock_db_session):
    """Integration test client with mocked DB."""
    async def override_get_db():
        yield mock_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ============== Common Fixtures ==============
@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_db():
    """Alias for mock_db_session for backward compatibility with unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    
    # Mock execute to return empty results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    
    return session


@pytest.fixture
def dummy_care_session():
    """Create a dummy care session for testing"""
    from uuid import uuid4
    from datetime import datetime
    from app.db.models import CareSession
    return CareSession(
        id=uuid4(),
        session_id="CS-TEST-001",
        patient_id=uuid4(),
        caregiver_id=uuid4(),
        check_in_time=datetime.now(),
        check_out_time=datetime.now(),
        status="in_progress",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_jwt_payload():
    from app.auth.models import JWTPayload
    return JWTPayload(
        sub="123e4567-e89b-12d3-a456-426614174000",
        internal_user_id="123e4567-e89b-12d3-a456-426614174001",
        org_id="org-alpha",
        tenant_schema="org_alpha",
        roles=["CAREGIVER", "ADMIN"],
        permissions=[
            "care-session:create", "care-session:read", "care-session:update",
            "care-session:delete", "care-session:admin", "care-session:report",
            "feedback:create", "feedback:read", "feedback:update", "feedback:delete",
            "report:read", "report:download",
        ],
    )


@pytest.fixture
def fake_jwt_payload(mock_jwt_payload):
    """Alias for mock_jwt_payload for backward compatibility."""
    return mock_jwt_payload


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer mock_token"}
