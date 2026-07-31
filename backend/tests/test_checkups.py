"""Checkup endpoint tests: simulation mode, device mode, sharing."""

import pytest


async def _create_user(client, **overrides):
    payload = {
        "age": 34,
        "sex": "female",
        "height_cm": 165.0,
        "weight_kg": 62.0,
        "activity_level": "moderate",
        "share_data": True,
        "device_id": "doctordrobe_demo_001",
    }
    payload.update(overrides)
    response = await client.post("/api/users", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _post_reading(client, **overrides):
    payload = {
        "device_id": "doctordrobe_demo_001",
        "rgb_r": 120,
        "rgb_g": 200,
        "rgb_b": 60,
        "temperature_c": 24.5,
        "humidity_pct": 45.0,
    }
    payload.update(overrides)
    return await client.post("/api/devices/reading", json=payload)


@pytest.mark.asyncio
async def test_create_checkup_simulation_mode(client, created_user):
    """Simulated checkup returns a full, valid report."""
    response = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_id"] == created_user["id"]
    assert body["overall_risk"] in {"low", "medium", "high"}
    assert body["summary"]
    assert body["is_shared"] is False


@pytest.mark.asyncio
async def test_get_checkup_decrypts_report(client, created_user):
    """GET /api/checkups/{id} returns the decrypted biomarker report."""
    created = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    checkup_id = created.json()["id"]

    response = await client.get(
        f"/api/checkups/{checkup_id}?user_id={created_user['id']}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text_summary"]
    assert len(body["biomarkers"]) >= 3
    marker = body["biomarkers"][0]
    assert {"name", "value", "unit", "ref_low", "ref_high", "state", "message"} <= set(
        marker.keys()
    )
    assert marker["state"] in {"low", "normal", "high"}


@pytest.mark.asyncio
async def test_get_checkup_forbidden_for_other_user(client, created_user):
    """A user cannot read another user's checkup."""
    other = await _create_user(client, device_id="doctordrobe_demo_002")
    created = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    checkup_id = created.json()["id"]

    response = await client.get(f"/api/checkups/{checkup_id}?user_id={other['id']}")
    assert response.status_code == 403
    assert response.json() == {"detail": "Checkup does not belong to this user"}


@pytest.mark.asyncio
async def test_create_checkup_with_device_reading_conflict(client, created_user):
    """409 when a device checkup is requested but no reading exists."""
    response = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": True},
    )
    assert response.status_code == 409
    body = response.json()
    assert "device" in body["detail"].lower()


@pytest.mark.asyncio
async def test_create_checkup_with_device_reading(client, created_user):
    """Succeeds once a reading has been posted by the device."""
    reading = await _post_reading(client)
    assert reading.status_code == 201, reading.text

    response = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": True},
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_device_reading_endpoint_validation(client):
    """RGB values outside 0-255 are rejected."""
    response = await _post_reading(client, rgb_r=300)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_device_status_connected_and_stale(client):
    """Status reports connected=True right after a reading."""
    await _post_reading(client)
    response = await client.get(
        "/api/devices/status?device_id=doctordrobe_demo_001"
    )
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["last_seen"] is not None

    response = await client.get("/api/devices/status?device_id=unknown_device")
    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["last_seen"] is None


@pytest.mark.asyncio
async def test_device_latest_returns_newest(client, created_user):
    """GET /api/devices/latest returns the most recent snapshot."""
    await _post_reading(client, rgb_r=10)
    await _post_reading(client, rgb_r=250)

    response = await client.get(
        "/api/devices/latest?device_id=doctordrobe_demo_001"
    )
    assert response.status_code == 200
    assert response.json()["rgb_r"] == 250


@pytest.mark.asyncio
async def test_delete_checkup(client, created_user):
    """DELETE /api/checkups/{id} works with a body or query param."""
    created = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    checkup_id = created.json()["id"]

    response = await client.request(
        "DELETE",
        f"/api/checkups/{checkup_id}",
        json={"user_id": created_user["id"]},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Checkup deleted"}

    response = await client.get(
        f"/api/checkups/{checkup_id}?user_id={created_user['id']}"
    )
    assert response.status_code == 404

    # Query-param variant.
    created2 = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    response = await client.delete(
        f"/api/checkups/{created2.json()['id']}?user_id={created_user['id']}"
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Checkup deleted"}


@pytest.mark.asyncio
async def test_share_checkup_awards_tokens_once(client, created_user):
    """Sharing awards tokens exactly once; re-sharing conflicts."""
    created = await client.post(
        "/api/checkups",
        json={"user_id": created_user["id"], "use_device_reading": False},
    )
    checkup_id = created.json()["id"]

    response = await client.post(
        f"/api/checkups/{checkup_id}/share", json={"user_id": created_user["id"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tokens_awarded"] == 5
    assert body["new_balance"] == 5
    assert body["is_shared"] is True

    # Token balance persisted on the user.
    user = await client.get(f"/api/users/{created_user['id']}")
    assert user.json()["token_balance"] == 5

    # Second share attempt conflicts.
    response = await client.post(
        f"/api/checkups/{checkup_id}/share", json={"user_id": created_user["id"]}
    )
    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()

    # No double credit.
    user = await client.get(f"/api/users/{created_user['id']}")
    assert user.json()["token_balance"] == 5
