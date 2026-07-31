"""User endpoint tests: full CRUD lifecycle."""

import pytest


@pytest.mark.asyncio
async def test_create_user(client):
    """POST /api/users creates a user with defaults applied."""
    payload = {
        "age": 40,
        "sex": "male",
        "height_cm": 180.0,
        "weight_kg": 80.0,
    }
    response = await client.post("/api/users", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["age"] == 40
    assert body["sex"] == "male"
    assert body["token_balance"] == 0
    assert body["share_data"] is False
    assert body["device_id"] == "doctordrobe_demo_001"
    assert body["activity_level"] == "moderate"


@pytest.mark.asyncio
async def test_create_user_rejects_invalid_input(client):
    """Invalid values are rejected with a 422 and detail envelope."""
    response = await client.post(
        "/api/users", json={"age": 200, "sex": "male", "height_cm": 100, "weight_kg": 50}
    )
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_user(client, created_user):
    """GET /api/users/{id} returns the stored profile."""
    response = await client.get(f"/api/users/{created_user['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created_user["id"]


@pytest.mark.asyncio
async def test_get_user_404(client):
    import uuid

    response = await client.get(f"/api/users/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


@pytest.mark.asyncio
async def test_update_user(client, created_user):
    """PUT /api/users/{id} partially updates fields."""
    response = await client.put(
        f"/api/users/{created_user['id']}",
        json={"share_data": True, "activity_level": "active"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["share_data"] is True
    assert body["activity_level"] == "active"
    assert body["age"] == created_user["age"]  # untouched field preserved


@pytest.mark.asyncio
async def test_delete_user(client, created_user):
    """DELETE /api/users/{id} removes the user; follow-up GET returns 404."""
    response = await client.delete(f"/api/users/{created_user['id']}")
    assert response.status_code == 200
    assert response.json() == {"detail": "User deleted"}

    response = await client.get(f"/api/users/{created_user['id']}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_user_checkups_empty_and_after_creation(client, created_user):
    """GET /api/users/{id}/checkups returns summaries, newest first."""
    response = await client.get(f"/api/users/{created_user['id']}/checkups")
    assert response.status_code == 200
    assert response.json() == []

    await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    response = await client.get(f"/api/users/{created_user['id']}/checkups")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert "summary" in items[0]
    assert "overall_risk" in items[0]
    assert "encrypted_data" not in items[0]
