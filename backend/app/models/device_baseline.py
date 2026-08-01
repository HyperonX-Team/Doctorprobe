"""DeviceBaseline ORM model.

Per-device blank-pad calibration ("white balance"). The firmware's
``CAL BLANK`` command captures an unstained strip and stores it here;
the analyzer then gain-corrects every reading against this baseline so
optics/LED drift between units does not bias biomarker estimates.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class DeviceBaseline(Base):
    """One blank (unstained) strip capture per device."""

    __tablename__ = "device_baselines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    rgb_r: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_g: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_b: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
