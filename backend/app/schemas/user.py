"""User request/response schemas.

All inputs are validated by Pydantic v2 before they reach the service
layer: bounds, enums, and string lengths are enforced here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sex = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "athlete"]


class UserBase(BaseModel):
    """Shared fields for create/update operations."""

    age: int = Field(ge=1, le=120, description="Age in years")
    sex: Sex
    height_cm: float = Field(ge=50, le=250, description="Height in centimetres")
    weight_kg: float = Field(ge=2, le=500, description="Weight in kilograms")
    activity_level: ActivityLevel = "moderate"
    share_data: bool = False
    device_id: str = Field(
        default="doctordrobe_demo_001", min_length=1, max_length=64
    )


class UserCreate(UserBase):
    """Payload for POST /api/users."""


class UserUpdate(BaseModel):
    """Payload for PUT /api/users/{user_id} — every field is optional."""

    age: int | None = Field(default=None, ge=1, le=120)
    sex: Sex | None = None
    height_cm: float | None = Field(default=None, ge=50, le=250)
    weight_kg: float | None = Field(default=None, ge=2, le=500)
    activity_level: ActivityLevel | None = None
    share_data: bool | None = None
    device_id: str | None = Field(default=None, min_length=1, max_length=64)


class UserResponse(UserBase):
    """Full user representation returned to the SPA."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    token_balance: int
    created_at: datetime
