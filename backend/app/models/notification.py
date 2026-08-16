"""Notification ORM model: in-app notifications for the user.

Notifications are generated deterministically from the user's own data
(see ``app/services/notifications.py``): poor-quality measurements,
trend alerts, checkup reminders and token rewards. Each notification
carries a per-user ``dedupe_key`` (e.g. ``poor-quality:<checkup_id>``)
so the generator is idempotent — re-running it never duplicates rows.

``read_at`` marks the notification as seen; unread = ``read_at IS NULL``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """One in-app notification for a user."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Stable per-user key that makes generation idempotent, e.g.
    # "poor-quality:<checkup_id>" or "trend-alert:glucose:rising".
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # One of: "quality", "trend", "reminder", "reward".
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="notifications")

    __table_args__ = (
        # One notification per (user, dedupe key) — the idempotency guard.
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
