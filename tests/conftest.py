import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.main import app
from app.db.models import Base
from app.db.postgres import get_db
import os

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://localadmin:Stoplying!@localhost:5432/wailsalutem-local"
)

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

# Create async session maker
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except Exception:
            pass
    
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session):
    """Create a test client with overridden dependencies."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_jwt_payload():
    """Create a mock JWT payload for testing."""
    from app.auth.middleware import JWTPayload
    return JWTPayload(
        user_id="123e4567-e89b-12d3-a456-426614174000",
        email="test@example.com",
        org_id="org-alpha",
        tenant_id="org-alpha",
        tenant_schema="org_alpha",
        roles=["CAREGIVER"],
        permissions=["care-session:create", "care-session:read", "care-session:update"],
    )


@pytest.fixture
def auth_headers(mock_jwt_payload):
    """Create authorization headers with a mock token."""
    return {
        "Authorization": "Bearer mock_token_for_testing"
    }
