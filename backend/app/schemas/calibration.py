"""Calibration sample request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CalibrationAnalyte = Literal["glucose", "crp", "cortisol", "siga"]

# Generous validation envelopes for labeled concentrations; the model
# clamps to reference-relative bounds during analysis. pH is a ratio
# measurement and is never calibrated.
ANALYTE_BOUNDS: dict[str, tuple[float, float]] = {
    "glucose": (0.05, 50.0),  # mg/dL
    "crp": (0.005, 20.0),  # ng/mL
    "cortisol": (0.005, 5.0),  # µg/dL
    "siga": (0.5, 200.0),  # mg/dL
}


class CalibrationSampleCreate(BaseModel):
    """Payload for POST /api/calibration/samples (firmware calibration mode)."""

    device_id: str = Field(min_length=1, max_length=64)
    analyte: CalibrationAnalyte
    concentration: float = Field(ge=0.0, le=1000.0)
    rgb_r: int = Field(ge=0, le=255)
    rgb_g: int = Field(ge=0, le=255)
    rgb_b: int = Field(ge=0, le=255)
    temperature_c: float = Field(ge=-40, le=85)
    humidity_pct: float = Field(ge=0, le=100)


class CalibrationSampleResponse(BaseModel):
    """A stored calibration sample."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: str
    analyte: str
    concentration: float
    rgb_r: int
    rgb_g: int
    rgb_b: int
    temperature_c: float
    humidity_pct: float
    created_at: datetime
