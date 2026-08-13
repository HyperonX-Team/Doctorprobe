"""Auth endpoint tests: register, login, session lifecycle, profile.

Identity is email + password. Successful register/login return an opaque
bearer token; every other endpoint derives the owning user from that
token — never from a client-supplied id.
"""

from __future__ import annotations

import pytest

from tests.conftest import DEFAULT_PASSWORD, auth_headers, default_profile


@pytest.mark.asyncio
async def test_register_creates_user_with_defaults(client):
    """POST /api/auth/register returns a token and the stored profile."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "New.User@Example.com",
            "password": DEFAULT_PASSWORD,
            **default_profile(),
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token"]
    user = body["user"]
    assert user["email"] == "new.user@example.com"  # normalized
    assert user["age"] == 34
    assert user["sex"] == "female"
    assert user["token_balance"] == 0
    assert user["share_data"] is True
    assert user["device_id"] == "doctordrobe_demo_001"
    assert user["activity_level"] == "moderate"
    assert "password" not in user and "password_hash" not in user


@pytest.mark.asyncio
async def test_register_rejects_invalid_profile(client):
    """Invalid profile values are rejected with a 422 envelope."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "bad@example.com",
            "password": DEFAULT_PASSWORD,
            "age": 200,
            "sex": "male",
            "height_cm": 100,
            "weight_kg": 50,
        },
    )
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_register_rejects_weak_password(client):
    """Passwords below PASSWORD_MIN_LENGTH are rejected."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "weak@example.com",
            "password": "short",
            **default_profile(),
        },
    )
    assert response.status_code == 422
    assert "Password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client, created_user):
    """A second registration with the same email conflicts (case-insensitive)."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "TESTER@example.com",
            "password": DEFAULT_PASSWORD,
            **default_profile(),
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_returns_token(client, created_user):
    """Login with correct credentials returns a fresh token."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "tester@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client, created_user):
    """Wrong credentials yield a 401, never a hint about which part was wrong."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "wrong-password-1"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert "Incorrect" in response.json()["detail"]


@pytest.mark.asyncio
async def test_me_requires_token(client):
    """No token -> 401; the user is derived from the token, not a body field."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"

    response = await client.get("/api/auth/me", headers=auth_headers("bogus-token"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_profile(client, created_user):
    """GET /api/auth/me returns the authenticated profile."""
    headers = auth_headers(created_user["token"])
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == created_user["user"]["id"]


@pytest.mark.asyncio
async def test_update_me_partial(client, created_user):
    """PUT /api/auth/me partially updates fields; untouched fields survive."""
    headers = auth_headers(created_user["token"])
    response = await client.put(
        "/api/auth/me",
        json={"share_data": False, "activity_level": "active"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["share_data"] is False
    assert body["activity_level"] == "active"
    assert body["age"] == created_user["user"]["age"]


@pytest.mark.asyncio
async def test_change_password_revokes_other_sessions(client, created_user):
    """Change-password revokes every session except the one making the change."""
    headers = auth_headers(created_user["token"])

    # A second, independent session for the same user.
    second = await client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": DEFAULT_PASSWORD},
    )
    second_token = second.json()["token"]
    assert (
        await client.get("/api/auth/me", headers=auth_headers(second_token))
    ).status_code == 200

    # Wrong current password is rejected and revokes nothing.
    bad = await client.post(
        "/api/auth/change-password",
        json={"current_password": "nope", "new_password": "brand-new-pass-9"},
        headers=headers,
    )
    assert bad.status_code == 401
    assert (
        await client.get("/api/auth/me", headers=auth_headers(second_token))
    ).status_code == 200

    # Correct change succeeds; the other session dies, this one lives.
    good = await client.post(
        "/api/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "brand-new-pass-9"},
        headers=headers,
    )
    assert good.status_code == 200
    assert (
        await client.get("/api/auth/me", headers=headers)
    ).status_code == 200
    assert (
        await client.get("/api/auth/me", headers=auth_headers(second_token))
    ).status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_token(client, created_user):
    """After logout the same token can no longer authenticate."""
    headers = auth_headers(created_user["token"])
    response = await client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200

    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_me_removes_account(client, created_user):
    """DELETE /api/auth/me removes the account; login then fails."""
    headers = auth_headers(created_user["token"])
    response = await client.delete("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "Account deleted"}

    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401

    login = await client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": DEFAULT_PASSWORD},
    )
    assert login.status_code == 401


def test_login_rate_limiter_blocks():
    """The per-IP limiter blocks after the configured attempt budget."""
    from app.api.routes.auth import _LoginRateLimiter

    limiter = _LoginRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        limiter.hit("1.2.3.4")
    assert limiter.blocked("1.2.3.4")
    assert not limiter.blocked("5.6.7.8")  # other IPs unaffected
