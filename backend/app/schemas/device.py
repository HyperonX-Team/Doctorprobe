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


class ReadingSnapshot(BaseModel):
    """One snapshot within a firmware burst (device_id lives on the burst)."""

    rgb_r: int = Field(ge=0, le=255)
    rgb_g: int = Field(ge=0, le=255)
    rgb_b: int = Field(ge=0, le=255)
    temperature_c: float = Field(ge=-40, le=85)
    humidity_pct: float = Field(ge=0, le=100)


class DeviceReadingsCreate(BaseModel):
    """Burst payload posted by the firmware to /api/devices/readings.

    A burst is a rapid sequence of snapshots of the *same* strip; the
    analyzer deconvolves them together to average out sensor noise and
    quantify identifiability (see app/services/spectral.py).
    """

    device_id: str = Field(min_length=1, max_length=64)
    readings: list[ReadingSnapshot] = Field(min_length=1, max_length=20)


class DeviceReadingsResponse(BaseModel):
    """Stored burst."""

    device_id: str
    count: int
    readings: list[DeviceReadingResponse]


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


class DeviceBaselineCreate(BaseModel):
    """Blank-pad calibration capture posted by the firmware (CAL BLANK)."""

    device_id: str = Field(min_length=1, max_length=64)
    rgb_r: int = Field(ge=0, le=255)
    rgb_g: int = Field(ge=0, le=255)
    rgb_b: int = Field(ge=0, le=255)


class DeviceBaselineResponse(BaseModel):
    """Stored per-device blank baseline."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: str
    rgb_r: int
    rgb_g: int
    rgb_b: int
    created_at: datetime
    updated_at: datetime
