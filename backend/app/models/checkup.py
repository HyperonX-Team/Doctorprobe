"""Checkup ORM model.

The full biomarker report is stored encrypted (``encrypted_data``) with a
plain summary/risk kept readable for list views.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.share_event import ShareEvent
    from app.models.user import User


class Checkup(Base):
    """A single biomarker analysis for a user."""

    __tablename__ = "checkups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    overall_risk: Mapped[str] = mapped_column(String(16), nullable=False)
    encrypted_data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="checkups")
    share_event: Mapped["ShareEvent | None"] = relationship(
        back_populates="checkup", cascade="all, delete-orphan"
    )
