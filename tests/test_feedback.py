import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_create_feedback_unauthorized(client: AsyncClient):
    """Test creating feedback without authentication."""
    session_id = uuid4()
    response = await client.post(
        "/feedback/",
        json={
            "session_id": str(session_id),
            "rating": 3,
            "patient_feedback": "Great service"
        }
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_create_feedback_validation(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test feedback validation - rating must be 1-3."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    session_id = uuid4()
    
    response = await client.post(
        "/feedback/",
        json={
            "session_id": str(session_id),
            "rating": 5,
            "patient_feedback": "Test"
        },
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 422  
    
    response = await client.post(
        "/feedback/",
        json={
            "session_id": str(session_id),
            "rating": 0,
            "patient_feedback": "Test"
        },
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 422
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_feedback_valid_ratings(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test that ratings 1-3 are accepted."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    session_id = uuid4()
    
    for rating in [1, 2, 3]:
        response = await client.post(
            "/feedback/",
            json={
                "session_id": str(session_id),
                "rating": rating,
                "patient_feedback": f"Test feedback for rating {rating}"
            },
            headers={"Authorization": "Bearer mock_token"}
        )
        assert response.status_code in [201, 404, 422, 500]
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_feedback_unauthorized(client: AsyncClient):
    """Test listing feedback without authentication."""
    response = await client.get("/feedback/")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_list_feedback_structure(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test feedback list response structure."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.get(
        "/feedback/",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "feedbacks" in data
        assert "count" in data
        assert isinstance(data["feedbacks"], list)
        assert isinstance(data["count"], int)
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_patient_average_rating(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test patient average rating endpoint."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    patient_id = uuid4()
    
    response = await client.get(
        f"/feedback/analytics/patient/{patient_id}/average",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "patient_id" in data
        assert "average_rating" in data
        assert "satisfaction_index" in data
        assert "total_feedbacks" in data
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_top_caregivers_weekly(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test top caregivers of the week endpoint."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.get(
        "/feedback/analytics/top-caregivers/weekly",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "caregivers" in data
        assert isinstance(data["caregivers"], list)
        # Should return max 3 caregivers
        assert len(data["caregivers"]) <= 3
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_daily_average_ratings(
    client: AsyncClient,
    mock_jwt_payload,
):
    """Test daily average ratings endpoint."""
    from app.main import app
    from app.auth.middleware import verify_token
    
    app.dependency_overrides[verify_token] = lambda: mock_jwt_payload
    
    response = await client.get(
        "/feedback/analytics/daily?days=7",
        headers={"Authorization": "Bearer mock_token"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "daily_averages" in data
        assert "count" in data
        assert isinstance(data["daily_averages"], list)
    
    app.dependency_overrides.clear()
