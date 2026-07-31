"""CalibrationSample ORM model.

A labeled sensor capture used to retrain SaliNet on real data: the
firmware reads a control standard with a known analyte concentration
and records the resulting RGB/temperature/humidity snapshot. Enough
samples per analyte -> retrain the model with
``scripts/train_model.py`` (export via GET /api/calibration/export).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class CalibrationSample(Base):
    """One labeled sensor snapshot for model training."""

    __tablename__ = "calibration_samples"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # One of: glucose, crp, cortisol, siga (pH is a ratio measurement and
    # needs no calibration).
    analyte: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    concentration: Mapped[float] = mapped_column(Float, nullable=False)
    rgb_r: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_g: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_b: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
