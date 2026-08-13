"""Authentication endpoints: register, login, logout, profile, password.

Identity is an email + password. Successful register/login return an
opaque bearer token (stored hashed in ``sessions``) plus the full
profile; every other authenticated request carries that token in the
``Authorization: Bearer`` header and the owning user is derived from it —
never from a client-supplied id.

Login is rate-limited per IP to slow down credential stuffing.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_current_session, get_current_user
from app.db.session import get_db
from app.models.checkup import Checkup
from app.models.session import Session, generate_session_token, token_digest
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
)
from app.schemas.checkup import CheckupSummary
from app.schemas.user import UserResponse, UserUpdate
from app.utils.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def _normalize_email(email: str) -> str:
    """Canonical lowercase form used for lookup and uniqueness."""
    return email.strip().lower()


class _LoginRateLimiter:
    """In-memory per-IP attempt limiter (best-effort, per-process).

    Not a substitute for a distributed limiter, but it raises the cost of
    credential stuffing on a single instance.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, ip: str) -> None:
        now = time.monotonic()
        queue = self._attempts[ip]
        while queue and now - queue[0] > self._window:
            queue.popleft()
        queue.append(now)

    def blocked(self, ip: str) -> bool:
        now = time.monotonic()
        queue = self._attempts[ip]
        while queue and now - queue[0] > self._window:
            queue.popleft()
        return len(queue) >= self._max


def _client_ip(request: Request) -> str:
    """Best-effort client address (honours X-Forwarded-For when present)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_rate_limiter: _LoginRateLimiter | None = None


def _limiter() -> _LoginRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = _LoginRateLimiter(
            settings.AUTH_LOGIN_MAX_ATTEMPTS, settings.AUTH_LOGIN_WINDOW_SECONDS
        )
    return _rate_limiter


def _check_password_strength(password: str) -> None:
    """Enforce the configured minimum length with a 422 envelope."""
    settings = get_settings()
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Password must be at least {settings.PASSWORD_MIN_LENGTH} "
                "characters long"
            ),
        )


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == _normalize_email(email))
    )
    return result.scalar_one_or_none()


async def _create_session(db: AsyncSession, user: User) -> str:
    """Create a session row and return the raw token handed to the client."""
    token = generate_session_token()
    db.add(
        Session(
            user_id=user.id,
            token_hash=token_digest(token),
        )
    )
    await db.commit()
    return token


def _auth_response(token: str, user: User) -> AuthResponse:
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    """Create a user from email + password + profile and log them in."""
    _check_password_strength(payload.password)
    email = _normalize_email(payload.email)
    if await _find_user_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    profile = payload.model_dump(exclude={"email", "password"})
    user = User(**profile, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        # Race: another request created the same email first.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create account",
        )

    token = await _create_session(db, user)
    logger.info("registered user %s", user.id)
    return _auth_response(token, user)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Exchange email + password for a session token."""
    ip = _client_ip(request)
    limiter = _limiter()
    if limiter.blocked(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts — try again later",
        )
    limiter.hit(ip)

    user = await _find_user_by_email(db, payload.email)
    if user is None or not user.password_hash or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers=_AUTH_HEADERS,
        )

    token = await _create_session(db, user)
    logger.info("login ok for user %s", user.id)
    return _auth_response(token, user)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    session: Session = Depends(get_current_session),
) -> dict:
    """Revoke the current session token."""
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("logout for user %s", current.id)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile."""
    return current


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> User:
    """Partially update the authenticated user's profile."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current, field, value)
    try:
        await db.commit()
        await db.refresh(current)
        return current
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update profile",
        )


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_me(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Delete the account. Checkups and sessions cascade."""
    await db.execute(delete(Session).where(Session.user_id == current.id))
    await db.execute(delete(User).where(User.id == current.id))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete account",
        )
    logger.info("deleted account %s", current.id)
    return {"detail": "Account deleted"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    session: Session = Depends(get_current_session),
) -> dict:
    """Change the password, revoking every other session."""
    if not current.password_hash or not verify_password(
        payload.current_password, current.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
            headers=_AUTH_HEADERS,
        )
    _check_password_strength(payload.new_password)

    current.password_hash = hash_password(payload.new_password)
    # Revoke all sessions except the one making the change.
    await db.execute(
        delete(Session).where(
            Session.user_id == current.id, Session.id != session.id
        )
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not change password",
        )
    return {"detail": "Password changed"}


@router.get(
    "/me/checkups",
    response_model=list[CheckupSummary],
    response_model_exclude={"user_id"},
)
async def my_checkups(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[Checkup]:
    """List the authenticated user's checkups (summaries, newest first)."""
    result = await db.execute(
        select(Checkup)
        .where(Checkup.user_id == current.id)
        .order_by(Checkup.created_at.desc())
    )
    return list(result.scalars().all())
