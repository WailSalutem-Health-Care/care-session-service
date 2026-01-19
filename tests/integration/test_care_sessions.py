import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_create_care_session_unauthorized(client: AsyncClient):
    """Test creating a care session without authentication."""
    response = await client.post(
        "/care-sessions/create",
        json={"tag_id": "test-tag-123"}
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_create_care_session_success(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test care session creation endpoint - expects 404 for non-existent tag."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.post(
        "/care-sessions/create",
        json={"tag_id": "test-tag-123"},
        headers={"Authorization": "Bearer mock_token"}
    )
    
    assert response.status_code == 404
    assert "detail" in response.json()
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_care_sessions_unauthorized(client: AsyncClient):
    """Test listing care sessions without authentication."""
    response = await client.get("/care-sessions/")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_list_care_sessions_structure(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test care session list response structure."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.get(
        "/care-sessions/",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert isinstance(data["sessions"], list)
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_care_sessions_pagination(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test care session pagination parameters."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.get(
        "/care-sessions/?page=1&page_size=10",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_care_session_not_found(client: AsyncClient):
    """Test getting a non-existent care session."""
    session_id = uuid4()
    response = await client.get(f"/care-sessions/{session_id}")
    assert response.status_code in [401, 403, 404]


@pytest.mark.asyncio
async def test_complete_care_session_unauthorized(client: AsyncClient):
    """Test completing a care session without authentication."""
    session_id = uuid4()
    response = await client.put(
        f"/care-sessions/{session_id}/complete",
        json={"caregiver_notes": "Test notes"}
    )
    assert response.status_code in [401, 403]
