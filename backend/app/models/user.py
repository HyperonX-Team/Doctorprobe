"""User ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class User(Base):
    """A home user of the device.

    No passwords: identity is a server-generated UUID kept in the SPA's
    localStorage. Devices are linked by ``device_id``.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    activity_level: Mapped[str] = mapped_column(String(32), default="moderate")
    share_data: Mapped[bool] = mapped_column(Boolean, default=False)
    token_balance: Mapped[int] = mapped_column(Integer, default=0)
    device_id: Mapped[str] = mapped_column(
        String(64), default="doctordrobe_demo_001", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    checkups: Mapped[List["Checkup"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
