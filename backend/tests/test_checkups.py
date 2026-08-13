"""Checkup endpoint tests: device-driven creation, reading, sharing.

The owning user is derived from the bearer token — checkups can never be
created or read on behalf of another user.
"""

from __future__ import annotations

import pytest

from tests.conftest import DEFAULT_PASSWORD, auth_headers, default_profile


async def _register(client, email, **profile_overrides):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            **default_profile(**profile_overrides),
        },
    )
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


async def _create_checkup(client, token):
    return await client.post("/api/checkups", json={}, headers=auth_headers(token))


async def _get_checkup(client, token, checkup_id):
    return await client.get(
        f"/api/checkups/{checkup_id}", headers=auth_headers(token)
    )


@pytest.mark.asyncio
async def test_create_checkup_requires_device_reading(client, created_user):
    """409 when a checkup is requested but the device has never reported."""
    response = await _create_checkup(client, created_user["token"])
    assert response.status_code == 409
    body = response.json()
    assert "device" in body["detail"].lower()


@pytest.mark.asyncio
async def test_create_checkup_requires_auth(client):
    """No token -> 401; the user is never taken from the request body."""
    response = await client.post("/api/checkups", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_checkup_from_device_reading(client, created_user):
    """Succeeds once a reading has been posted by the device."""
    reading = await _post_reading(client)
    assert reading.status_code == 201, reading.text

    response = await _create_checkup(client, created_user["token"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_id"] == created_user["user"]["id"]
    assert body["overall_risk"] in {"low", "medium", "high"}
    assert body["summary"]
    assert body["is_shared"] is False
    assert body["quality_grade"] in {"good", "fair", "poor"}


@pytest.mark.asyncio
async def test_get_checkup_decrypts_report(client, created_user):
    """GET /api/checkups/{id} returns the decrypted biomarker report."""
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]

    response = await _get_checkup(client, created_user["token"], checkup_id)
    assert response.status_code == 200
    body = response.json()
    assert body["text_summary"]
    assert len(body["biomarkers"]) >= 3
    marker = body["biomarkers"][0]
    assert {"key", "name", "value", "unit", "ref_low", "ref_high", "state", "message"} <= set(
        marker.keys()
    )
    assert marker["state"] in {"low", "normal", "high"}
    assert body["quality"]["grade"] in {"good", "fair", "poor"}
    assert isinstance(body["quality"]["reasons"], list)


@pytest.mark.asyncio
async def test_get_checkup_forbidden_for_other_user(client, created_user):
    """A user cannot read another user's checkup (403, not 404)."""
    other = await _register(client, "other@example.com", device_id="doctordrobe_demo_002")
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]

    response = await _get_checkup(client, other["token"], checkup_id)
    assert response.status_code == 403
    assert response.json() == {"detail": "Checkup does not belong to this user"}


@pytest.mark.asyncio
async def test_checkup_list_is_scoped_to_token(client, created_user):
    """The authenticated checkup list only contains the caller's checkups."""
    await _post_reading(client)
    await _create_checkup(client, created_user["token"])

    other = await _register(client, "other@example.com", device_id="doctordrobe_demo_002")
    response = await client.get(
        "/api/auth/me/checkups", headers=auth_headers(other["token"])
    )
    assert response.status_code == 200
    assert response.json() == []


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
    """DELETE /api/checkups/{id} removes the checkup."""
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]

    response = await client.delete(
        f"/api/checkups/{checkup_id}", headers=auth_headers(created_user["token"])
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Checkup deleted"}

    response = await _get_checkup(client, created_user["token"], checkup_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_blank_baseline_upsert_and_get(client):
    """CAL BLANK baseline is stored once and updated in place."""
    payload = {
        "device_id": "doctordrobe_demo_001",
        "rgb_r": 240,
        "rgb_g": 250,
        "rgb_b": 230,
    }

    response = await client.post("/api/devices/baseline", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rgb_r"] == 240
    baseline_id = body["id"]

    # Upsert updates the same row.
    response = await client.post(
        "/api/devices/baseline", json={**payload, "rgb_r": 245}
    )
    assert response.status_code == 200
    assert response.json()["id"] == baseline_id
    assert response.json()["rgb_r"] == 245

    response = await client.get(
        "/api/devices/baseline?device_id=doctordrobe_demo_001"
    )
    assert response.status_code == 200
    assert response.json()["rgb_r"] == 245

    response = await client.get("/api/devices/baseline?device_id=unknown_device")
    assert response.status_code == 404
    assert "CAL BLANK" in response.json()["detail"]


@pytest.mark.asyncio
async def test_blank_baseline_validation(client):
    """Out-of-range channels are rejected."""
    response = await client.post(
        "/api/devices/baseline",
        json={"device_id": "d1", "rgb_r": 300, "rgb_g": 128, "rgb_b": 128},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_checkup_applies_baseline_correction(client, created_user):
    """A stored baseline gain-corrects the reading before analysis."""
    await _post_reading(client)

    first = await _create_checkup(client, created_user["token"])
    assert first.status_code == 201, first.text

    await client.post(
        "/api/devices/baseline",
        json={
            "device_id": "doctordrobe_demo_001",
            "rgb_r": 240,
            "rgb_g": 250,
            "rgb_b": 230,
        },
    )
    second = await _create_checkup(client, created_user["token"])
    assert second.status_code == 201, second.text

    async def biomarker_values(checkup_id):
        response = await _get_checkup(client, created_user["token"], checkup_id)
        assert response.status_code == 200
        return {
            m["name"]: m["value"]
            for m in response.json()["biomarkers"]
            if m["name"] != "Salivary pH"
        }

    before = await biomarker_values(first.json()["id"])
    after = await biomarker_values(second.json()["id"])

    # Same physical reading, different baseline -> different analysis.
    assert before != after


@pytest.mark.asyncio
async def test_share_checkup_awards_tokens_once(client, created_user):
    """Sharing awards tokens exactly once; re-sharing conflicts."""
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]
    headers = auth_headers(created_user["token"])

    response = await client.post(f"/api/checkups/{checkup_id}/share", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["tokens_awarded"] == 5
    assert body["new_balance"] == 5
    assert body["is_shared"] is True

    # Token balance persisted on the user.
    user = await client.get("/api/auth/me", headers=headers)
    assert user.json()["token_balance"] == 5

    # Second share attempt conflicts.
    response = await client.post(f"/api/checkups/{checkup_id}/share", headers=headers)
    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()

    # No double credit.
    user = await client.get("/api/auth/me", headers=headers)
    assert user.json()["token_balance"] == 5


@pytest.mark.asyncio
async def test_export_checkup_pdf(client, created_user):
    """GET /api/checkups/{id}/export returns a real PDF for the owner."""
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]

    response = await client.get(
        f"/api/checkups/{checkup_id}/export",
        headers=auth_headers(created_user["token"]),
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


@pytest.mark.asyncio
async def test_export_checkup_pdf_includes_trends(client, created_user):
    """A multi-checkup export renders the trends appendix without error."""
    for _ in range(3):
        await _post_reading(client)
        await _create_checkup(client, created_user["token"])

    summaries = await client.get(
        "/api/auth/me/checkups", headers=auth_headers(created_user["token"])
    )
    checkup_id = summaries.json()[0]["id"]
    response = await client.get(
        f"/api/checkups/{checkup_id}/export",
        headers=auth_headers(created_user["token"]),
    )
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


@pytest.mark.asyncio
async def test_export_checkup_requires_auth(client, created_user):
    """No token -> 401."""
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])

    response = await client.get(f"/api/checkups/{created.json()['id']}/export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_checkup_forbidden_for_other_user(client, created_user):
    """A user cannot export another user's checkup."""
    other = await _register(
        client, "other@example.com", device_id="doctordrobe_demo_002"
    )
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])

    response = await client.get(
        f"/api/checkups/{created.json()['id']}/export",
        headers=auth_headers(other["token"]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_share_forbidden_for_other_user(client, created_user):
    """A user cannot share another user's checkup."""
    other = await _register(client, "other@example.com", device_id="doctordrobe_demo_002")
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]

    response = await client.post(
        f"/api/checkups/{checkup_id}/share", headers=auth_headers(other["token"])
    )
    assert response.status_code == 403


def _snapshot(rgb_r=120, rgb_g=200, rgb_b=60):
    return {
        "rgb_r": rgb_r,
        "rgb_g": rgb_g,
        "rgb_b": rgb_b,
        "temperature_c": 24.5,
        "humidity_pct": 45.0,
    }


async def _post_burst(client, snapshots, device_id="doctordrobe_demo_001"):
    return await client.post(
        "/api/devices/readings",
        json={"device_id": device_id, "readings": snapshots},
    )


async def _checkup_analysis(client, token, checkup_id):
    response = await _get_checkup(client, token, checkup_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis"] is not None
    return body


@pytest.mark.asyncio
async def test_batch_reading_endpoint_stores_burst(client, created_user):
    """A burst POST stores every snapshot; a checkup deconvolves all of them."""
    response = await _post_burst(client, [_snapshot() for _ in range(3)])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["device_id"] == "doctordrobe_demo_001"
    assert body["count"] == 3
    assert len(body["readings"]) == 3
    assert {r["rgb_r"] for r in body["readings"]} == {120}

    created = await _create_checkup(client, created_user["token"])
    assert created.status_code == 201, created.text
    report = await _checkup_analysis(client, created_user["token"], created.json()["id"])
    assert report["analysis"]["n_measurements"] == 3
    assert report["analysis"]["method"] == "spectral_nnls"
    for marker in report["biomarkers"]:
        assert 0.0 <= marker["confidence"] <= 1.0
    assert report["quality"]["grade"] in {"good", "fair", "poor"}


@pytest.mark.asyncio
async def test_batch_reading_validation(client):
    """Empty bursts, oversized bursts and bad channels are rejected."""
    assert (await _post_burst(client, [])).status_code == 422
    assert (await _post_burst(client, [_snapshot()] * 21)).status_code == 422
    bad = await _post_burst(client, [_snapshot(rgb_r=300)])
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_checkup_clusters_recent_readings_into_one_burst(client, created_user):
    """Readings posted close together form a single burst for the checkup."""
    await _post_burst(client, [_snapshot(rgb_r=100) for _ in range(3)])
    await _post_reading(client, rgb_r=250)  # immediately after -> same burst

    created = await _create_checkup(client, created_user["token"])
    report = await _checkup_analysis(client, created_user["token"], created.json()["id"])
    assert report["analysis"]["n_measurements"] == 4
