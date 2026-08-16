"""v2.0 endpoint tests: personalization, notes, pagination, notifications,
community insights, and the new exports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import DEFAULT_PASSWORD, auth_headers, default_profile

DEVICE = "doctordrobe_demo_001"
OTHER_DEVICE = "doctordrobe_demo_002"


async def _register(client, email, device_id=DEVICE, **overrides):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            **default_profile(device_id=device_id, **overrides),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _post_reading(client, device_id=DEVICE, **overrides):
    payload = {
        "device_id": device_id,
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


# ---------------------------------------------------------------------------
# Personalized reference ranges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_reference_ranges_and_report_honors_them(client, created_user):
    """PUT /me with reference_ranges persists; a new checkup uses them."""
    headers = auth_headers(created_user["token"])
    response = await client.put(
        "/api/auth/me",
        json={"reference_ranges": {"glucose": {"low": 10.0, "high": 12.0}}},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["reference_ranges"] == {
        "glucose": {"low": 10.0, "high": 12.0}
    }

    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    assert created.status_code == 201, created.text

    body = (await _get_checkup(client, created_user["token"], created.json()["id"])).json()
    glucose = next(m for m in body["biomarkers"] if m["key"] == "glucose")
    assert glucose["ref_low"] == 10.0
    assert glucose["ref_high"] == 12.0
    assert body["analysis"]["reference_source"] == "personalized"

    # Other markers keep the analyzer defaults.
    crp = next(m for m in body["biomarkers"] if m["key"] == "crp")
    assert crp["ref_low"] == 0.02


@pytest.mark.asyncio
async def test_invalid_reference_ranges_ignored(client, created_user):
    """Malformed overrides are rejected by validation or ignored safely."""
    headers = auth_headers(created_user["token"])
    response = await client.put(
        "/api/auth/me",
        json={"reference_ranges": {"glucose": {"low": 12.0, "high": 5.0}}},
        headers=headers,
    )
    # low >= high is a bad override; Pydantic accepts the shape, the
    # analyzer ignores it, so the report stays on defaults.
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    body = (await _get_checkup(client, created_user["token"], created.json()["id"])).json()
    glucose = next(m for m in body["biomarkers"] if m["key"] == "glucose")
    assert glucose["ref_low"] == 0.5
    assert body["analysis"]["reference_source"] == "default"


# ---------------------------------------------------------------------------
# Checkup notes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkup_note_set_and_cleared(client, created_user):
    """PUT /note stores an encrypted note; empty clears it."""
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]
    headers = auth_headers(created_user["token"])

    response = await client.put(
        f"/api/checkups/{checkup_id}/note", json={"note": "  felt great  "}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["note"] == "felt great"

    body = (await _get_checkup(client, created_user["token"], checkup_id)).json()
    assert body["note"] == "felt great"

    response = await client.put(
        f"/api/checkups/{checkup_id}/note", json={"note": ""}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["note"] is None


@pytest.mark.asyncio
async def test_checkup_note_forbidden_for_other_user(client, created_user):
    """A user cannot edit another user's note."""
    other = await _register(client, "other@example.com", device_id=OTHER_DEVICE)
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])

    response = await client.put(
        f"/api/checkups/{created.json()['id']}/note",
        json={"note": "sneaky"},
        headers=auth_headers(other["token"]),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# History pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkup_list_pagination_and_total(client, created_user):
    """limit/offset page the list; X-Total-Count reports the full size."""
    headers = auth_headers(created_user["token"])
    for _ in range(5):
        await _post_reading(client)
        response = await _create_checkup(client, created_user["token"])
        assert response.status_code == 201

    page1 = await client.get(
        "/api/auth/me/checkups?limit=2&offset=0", headers=headers
    )
    assert page1.status_code == 200
    assert page1.headers["x-total-count"] == "5"
    assert len(page1.json()) == 2

    page2 = await client.get(
        "/api/auth/me/checkups?limit=2&offset=2", headers=headers
    )
    assert len(page2.json()) == 2
    assert page2.json()[0]["id"] != page1.json()[-1]["id"]

    page3 = await client.get(
        "/api/auth/me/checkups?limit=2&offset=4", headers=headers
    )
    assert len(page3.json()) == 1
    assert page3.headers["x-total-count"] == "5"


# ---------------------------------------------------------------------------
# Trends CSV export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trends_csv_export(client, created_user):
    """GET /api/trends/export returns a CSV with header and data rows."""
    for _ in range(2):
        await _post_reading(client)
        assert (await _create_checkup(client, created_user["token"])).status_code == 201

    response = await client.get(
        "/api/trends/export?window_days=30", headers=auth_headers(created_user["token"])
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    text = response.text
    assert text.splitlines()[0] == "date,marker,value,unit,state"
    assert any("Salivary Glucose" in line for line in text.splitlines())


@pytest.mark.asyncio
async def test_trends_csv_export_requires_auth(client, created_user):
    """No token -> 401."""
    response = await client.get("/api/trends/export")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Account data export (export-before-delete)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_export_includes_all_data(client, created_user):
    """GET /api/auth/me/export returns profile, checkups, share events."""
    headers = auth_headers(created_user["token"])
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = created.json()["id"]
    await client.post(f"/api/checkups/{checkup_id}/share", headers=headers)

    response = await client.get("/api/auth/me/export", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]

    payload = response.json()
    assert payload["profile"]["email"] == created_user["user"]["email"]
    assert len(payload["checkups"]) == 1
    assert payload["checkups"][0]["report"]["overall_risk"] in {
        "low",
        "medium",
        "high",
    }
    assert len(payload["share_events"]) == 1
    assert payload["share_events"][0]["tokens_awarded"] == 5
    assert len(payload["sessions"]) >= 1


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


async def _post_varying_burst(client, device_id=DEVICE):
    """A burst whose channel variation forces a poor-quality grade."""
    snapshots = [
        {"rgb_r": 30, "rgb_g": 200, "rgb_b": 60, "temperature_c": 24.5, "humidity_pct": 45.0},
        {"rgb_r": 230, "rgb_g": 200, "rgb_b": 60, "temperature_c": 24.5, "humidity_pct": 45.0},
        {"rgb_r": 130, "rgb_g": 200, "rgb_b": 60, "temperature_c": 24.5, "humidity_pct": 45.0},
    ]
    return await client.post(
        "/api/devices/readings",
        json={"device_id": device_id, "readings": snapshots},
    )


@pytest.mark.asyncio
async def test_poor_quality_checkup_creates_notification(client, created_user):
    """A poor-grade checkup generates a quality notification."""
    headers = auth_headers(created_user["token"])
    response = await _post_varying_burst(client)
    assert response.status_code == 201, response.text

    created = await _create_checkup(client, created_user["token"])
    assert created.status_code == 201, created.text

    notifications = await client.get("/api/notifications", headers=headers)
    assert notifications.status_code == 200, notifications.text
    body = notifications.json()
    kinds = {item["kind"] for item in body["items"]}
    assert "quality" in kinds
    assert body["unread_count"] >= 1


@pytest.mark.asyncio
async def test_share_creates_reward_notification(client, created_user):
    """Sharing a checkup creates a reward notification."""
    headers = auth_headers(created_user["token"])
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    await client.post(
        f"/api/checkups/{created.json()['id']}/share", headers=headers
    )

    notifications = await client.get("/api/notifications", headers=headers)
    body = notifications.json()
    kinds = {item["kind"] for item in body["items"]}
    assert "reward" in kinds


@pytest.mark.asyncio
async def test_mark_all_read_clears_unread(client, created_user):
    """POST /api/notifications/read marks everything read."""
    headers = auth_headers(created_user["token"])
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    await client.post(f"/api/checkups/{created.json()['id']}/share", headers=headers)

    before = (await client.get("/api/notifications", headers=headers)).json()
    assert before["unread_count"] > 0

    after = (await client.post("/api/notifications/read", headers=headers)).json()
    assert after["unread_count"] == 0
    assert all(item["read_at"] is not None for item in after["items"])


@pytest.mark.asyncio
async def test_reminder_notification_after_gap(client, created_user, db_session_factory):
    """A checkup older than NOTIFICATION_REMINDER_DAYS yields a reminder."""
    import uuid

    from app.models.checkup import Checkup

    headers = auth_headers(created_user["token"])
    await _post_reading(client)
    created = await _create_checkup(client, created_user["token"])
    checkup_id = uuid.UUID(created.json()["id"])

    # Age the checkup so the reminder window has passed.
    async with db_session_factory() as session:
        checkup = await session.get(Checkup, checkup_id)
        checkup.created_at = datetime.now(timezone.utc) - timedelta(days=10)
        await session.commit()

    notifications = await client.get("/api/notifications", headers=headers)
    body = notifications.json()
    kinds = {item["kind"] for item in body["items"]}
    assert "reminder" in kinds
    assert any("days since" in item["message"] for item in body["items"])


# ---------------------------------------------------------------------------
# Community Insights
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_community_insights_aggregates_shared_checkups(client, created_user):
    """Insights aggregate other users' shared checkups; no raw rows leak."""
    owner = await _register(client, "owner@example.com")
    for _ in range(3):
        await _post_reading(client)
        created = await _create_checkup(client, owner["token"])
        assert created.status_code == 201, created.text
        share = await client.post(
            f"/api/checkups/{created.json()['id']}/share",
            headers=auth_headers(owner["token"]),
        )
        assert share.status_code == 200, share.text

    viewer = await _register(client, "viewer@example.com", device_id=OTHER_DEVICE)
    await _post_reading(client, device_id=OTHER_DEVICE)
    created = await _create_checkup(client, viewer["token"])
    assert created.status_code == 201

    response = await client.get(
        "/api/shares/insights", headers=auth_headers(viewer["token"])
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cohort_checkups"] == 3
    assert body["cohort_users"] == 1
    assert body["min_cohort"] == 3

    glucose = body["markers"]["glucose"]
    assert glucose["cohort_count"] == 3
    assert glucose["cohort_mean"] is not None
    assert glucose["cohort_p10"] <= glucose["cohort_p50"] <= glucose["cohort_p90"]
    assert glucose["user_latest"] is not None
    assert 0.0 <= glucose["user_percentile"] <= 1.0
    assert glucose["ref_low"] is not None

    # No raw community rows ever leave the server.
    assert "values" not in glucose


@pytest.mark.asyncio
async def test_community_insights_requires_shared_data(client, created_user):
    """With no shared checkups the payload is honest about it."""
    response = await client.get(
        "/api/shares/insights", headers=auth_headers(created_user["token"])
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cohort_checkups"] == 0
    assert body["cohort_users"] == 0
    assert all(
        marker["cohort_count"] == 0 and marker["cohort_mean"] is None
        for marker in body["markers"].values()
    )


@pytest.mark.asyncio
async def test_community_insights_requires_auth(client):
    """No token -> 401."""
    response = await client.get("/api/shares/insights")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Input hygiene
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_device_id_is_trimmed_on_update(client, created_user):
    """Whitespace-padded device ids are normalized."""
    response = await client.put(
        "/api/auth/me",
        json={"device_id": "  doctordrobe_demo_042  "},
        headers=auth_headers(created_user["token"]),
    )
    assert response.status_code == 200
    assert response.json()["device_id"] == "doctordrobe_demo_042"
