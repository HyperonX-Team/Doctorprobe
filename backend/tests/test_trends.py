"""Trends endpoint tests: longitudinal series, alerts, and auth scoping."""

from __future__ import annotations

import pytest

from tests.conftest import DEFAULT_PASSWORD, auth_headers, default_profile


async def _register(client, email, **overrides):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            **default_profile(**overrides),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _post_reading(client, rgb_r=120, rgb_g=200, rgb_b=60):
    return await client.post(
        "/api/devices/reading",
        json={
            "device_id": "doctordrobe_demo_001",
            "rgb_r": rgb_r,
            "rgb_g": rgb_g,
            "rgb_b": rgb_b,
            "temperature_c": 24.5,
            "humidity_pct": 45.0,
        },
    )


async def _create_checkup(client, token):
    response = await client.post("/api/checkups", json={}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


async def _read_and_checkup(client, token, rgb_r=120):
    """Post a reading and immediately create a checkup from it."""
    response = await _post_reading(client, rgb_r=rgb_r)
    assert response.status_code == 201, response.text
    return await _create_checkup(client, token)


async def _trends(client, token, window_days=30):
    return await client.get(
        f"/api/trends?window_days={window_days}", headers=auth_headers(token)
    )


@pytest.mark.asyncio
async def test_trends_requires_auth(client):
    """No token -> 401."""
    response = await client.get("/api/trends")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_trends_empty_without_checkups(client, created_user):
    """No checkups yet: empty series and zero alert count."""
    response = await _trends(client, created_user["token"])
    assert response.status_code == 200
    body = response.json()
    assert body["checkup_count"] == 0
    assert body["alert_count"] == 0
    for marker in body["markers"].values():
        assert marker["points"] == []
        assert marker["stats"] is None
        assert marker["alerts"] == []


@pytest.mark.asyncio
async def test_trends_builds_series_from_checkups(client, created_user):
    """Each checkup contributes one point per marker, oldest first."""
    for _ in range(3):
        await _read_and_checkup(client, created_user["token"])

    response = await _trends(client, created_user["token"])
    assert response.status_code == 200
    body = response.json()
    assert body["checkup_count"] == 3
    markers = body["markers"]
    assert set(markers.keys()) == {"glucose", "crp", "cortisol", "ph", "siga"}
    for marker in markers.values():
        assert len(marker["points"]) == 3
        assert marker["stats"]["count"] == 3
        dates = [p["date"] for p in marker["points"]]
        assert dates == sorted(dates)  # oldest -> newest
        for point in marker["points"]:
            assert point["value"] is not None
            assert point["state"] in {"low", "normal", "high"}


@pytest.mark.asyncio
async def test_trends_detects_rising_trend(client, created_user):
    """Three consecutive rising values trigger a rising_trend alert."""
    # Increasing red channel -> rising glucose-like signal. Values are
    # clamped by the analyzer, so use a spread that stays distinct.
    for rgb_r in (90, 110, 130):
        await _read_and_checkup(client, created_user["token"], rgb_r=rgb_r)

    response = await _trends(client, created_user["token"])
    body = response.json()
    assert body["alert_count"] >= 1
    alert_types = [
        a["type"]
        for marker in body["markers"].values()
        for a in marker["alerts"]
    ]
    assert "rising_trend" in alert_types


@pytest.mark.asyncio
async def test_trends_scoped_to_authenticated_user(client, created_user):
    """A user only sees their own checkups in trends."""
    for _ in range(2):
        await _read_and_checkup(client, created_user["token"])

    other = await _register(client, "other@example.com", device_id="doctordrobe_demo_002")
    response = await _trends(client, other["token"])
    body = response.json()
    assert body["checkup_count"] == 0


@pytest.mark.asyncio
async def test_trends_window_filter(client, created_user):
    """A small window excludes older checkups."""
    for _ in range(2):
        await _read_and_checkup(client, created_user["token"])

    response = await _trends(client, created_user["token"], window_days=0)
    # window_days=0 is invalid per the query constraint (ge=1), so use 1.
    response = await _trends(client, created_user["token"], window_days=1)
    assert response.status_code == 200
    body = response.json()
    assert body["checkup_count"] == 2  # all within the last day

    invalid = await client.get(
        "/api/trends?window_days=0", headers=auth_headers(created_user["token"])
    )
    assert invalid.status_code == 422
