"""Checkup request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskState = Literal["low", "medium", "high"]
BiomarkerState = Literal["low", "normal", "high"]


class CheckupCreate(BaseModel):
    """Payload for POST /api/checkups.

    ``use_device_reading`` selects between the pure simulator path and the
    path that consumes the latest physical sensor snapshot.
    """

    user_id: uuid.UUID
    use_device_reading: bool = False


class Biomarker(BaseModel):
    """One analyzed biomarker with its reference range and state."""

    name: str
    value: float
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None
    state: BiomarkerState
    message: str


class Report(BaseModel):
    """Full decrypted report body."""

    overall_risk: RiskState
    text_summary: str
    biomarkers: list[Biomarker]


class CheckupSummary(BaseModel):
    """Lightweight checkup representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    overall_risk: RiskState
    created_at: datetime
    is_shared: bool


class CheckupResponse(Report):
    """Full checkup with decrypted report data."""

    id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    created_at: datetime
    is_shared: bool


class ShareCheckupRequest(BaseModel):
    """Payload for POST /api/checkups/{checkup_id}/share."""

    user_id: uuid.UUID


class ShareResponse(BaseModel):
    """Result of sharing a checkup, including the updated token balance."""

    checkup_id: uuid.UUID
    tokens_awarded: int
    new_balance: int
    is_shared: bool


class DeleteCheckupRequest(BaseModel):
    """Payload for DELETE /api/checkups/{checkup_id}."""

    user_id: uuid.UUID


class CheckupCreateResponse(BaseModel):
    """Response returned by POST /api/checkups."""

    id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    overall_risk: RiskState
    created_at: datetime
    is_shared: bool = Field(default=False)
