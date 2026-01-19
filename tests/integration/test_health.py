import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]  # Can be healthy or degraded depending on DB
    assert data["service"] == "care-session-service"
    assert "dependencies" in data


@pytest.mark.asyncio
async def test_health_check_response_structure(client: AsyncClient):
    """Test that health check returns proper JSON structure."""
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert isinstance(data["status"], str)
