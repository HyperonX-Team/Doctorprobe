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

    The owning user is taken from the session token — no user id is
    accepted from the client. A checkup is always derived from the
    user's latest physical device reading; the endpoint returns 409 when
    no reading exists yet.
    """


class Biomarker(BaseModel):
    """One analyzed biomarker with its reference range and state."""

    key: str
    name: str
    value: float
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None
    state: BiomarkerState
    message: str
    confidence: float | None = None


class AnalysisInfo(BaseModel):
    """How a report was produced: solver, prior and measurement quality."""

    method: str
    prior_source: str
    n_measurements: int
    condition_number: float | None = None
    rank: int | None = None
    reconstruction_residual: float | None = None


class MeasurementQuality(BaseModel):
    """How trustworthy the raw sensor capture was.

    ``grade`` is one of "good" | "fair" | "poor"; ``reasons`` lists the
    human-readable findings and ``recommended_action`` suggests what to
    do next (e.g. "retake_reading").
    """

    grade: Literal["good", "fair", "poor"]
    reasons: list[str]
    recommended_action: str | None = None


class Report(BaseModel):
    """Full decrypted report body."""

    overall_risk: RiskState
    text_summary: str
    biomarkers: list[Biomarker]
    analysis: AnalysisInfo | None = None
    quality: MeasurementQuality | None = None


class CheckupSummary(BaseModel):
    """Lightweight checkup representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    overall_risk: RiskState
    quality_grade: str | None = None
    created_at: datetime
    is_shared: bool


class CheckupResponse(Report):
    """Full checkup with decrypted report data."""

    id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    created_at: datetime
    is_shared: bool


class ShareResponse(BaseModel):
    """Result of sharing a checkup, including the updated token balance."""

    checkup_id: uuid.UUID
    tokens_awarded: int
    new_balance: int
    is_shared: bool


class CheckupCreateResponse(BaseModel):
    """Response returned by POST /api/checkups."""

    id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    overall_risk: RiskState
    quality_grade: str | None = None
    created_at: datetime
    is_shared: bool = Field(default=False)
