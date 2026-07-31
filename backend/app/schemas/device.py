"""Device reading request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceReadingCreate(BaseModel):
    """Payload posted by the ESP32 firmware to /api/devices/reading."""

    device_id: str = Field(min_length=1, max_length=64)
    rgb_r: int = Field(ge=0, le=255)
    rgb_g: int = Field(ge=0, le=255)
    rgb_b: int = Field(ge=0, le=255)
    temperature_c: float = Field(ge=-40, le=85)
    humidity_pct: float = Field(ge=0, le=100)


class DeviceReadingResponse(BaseModel):
    """A stored device reading."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: str
    rgb_r: int
    rgb_g: int
    rgb_b: int
    temperature_c: float
    humidity_pct: float
    created_at: datetime


class DeviceStatus(BaseModel):
    """Connection status for a device."""

    connected: bool
    last_seen: datetime | None = None
