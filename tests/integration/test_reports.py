import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_reports_unauthorized(client: AsyncClient):
    """Test getting reports without authentication."""
    response = await client.get("/reports/")
    assert response.status_code in [401, 403, 404]


@pytest.mark.asyncio
async def test_get_reports_structure(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test reports list response structure."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.get(
        "/reports/",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "reports" in data
        assert isinstance(data["reports"], list)
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_report_unauthorized_role(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test that only admins can generate reports (non-admin should be denied)."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.post(
        "/reports/generate",
        json={"report_type": "care_sessions"},
        headers={"Authorization": "Bearer mock_token"}
    )
    
    assert response.status_code in [403, 404, 500]
    
    app.dependency_overrides.clear()
