"""DeviceReading ORM model: raw sensor snapshot posted by the ESP32."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class DeviceReading(Base):
    """One sensor snapshot from a physical device."""

    __tablename__ = "device_readings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    rgb_r: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_g: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_b: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
