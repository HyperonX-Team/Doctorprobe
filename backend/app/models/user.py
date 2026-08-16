"""User ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.session import Session


class User(Base):
    """A home user of the device.

    Identity is an email + password. Sessions are opaque bearer tokens
    (see ``app/models/session.py``); devices are linked by ``device_id``.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    # Personalized biomarker reference ranges, e.g.
    # {"glucose": {"low": 0.5, "high": 7.0}}. None = analyzer defaults.
    reference_ranges: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    checkups: Mapped[List["Checkup"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["Session"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
