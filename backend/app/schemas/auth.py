"""Auth request/response schemas.

Registration carries the profile fields (reused from ``user.py``) plus
the email/password credential pair. Every authenticated response returns
the opaque session token and the full user profile.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserBase, UserResponse


class RegisterRequest(UserBase):
    """Payload for POST /api/auth/register."""

    email: EmailStr
    password: str = Field(min_length=1, description="Checked against PASSWORD_MIN_LENGTH")


class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""

    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    """Payload for POST /api/auth/change-password."""

    current_password: str
    new_password: str = Field(min_length=1, description="Checked against PASSWORD_MIN_LENGTH")


class AuthResponse(BaseModel):
    """Successful register/login: the bearer token plus the profile."""

    token: str
    user: UserResponse
