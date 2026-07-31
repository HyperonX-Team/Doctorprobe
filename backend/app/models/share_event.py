"""ShareEvent ORM model: token reward ledger for shared checkups."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.checkup import Checkup


class ShareEvent(Base):
    """Record of a checkup being shared, and the tokens awarded."""

    __tablename__ = "share_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    checkup_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("checkups.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tokens_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    checkup: Mapped["Checkup"] = relationship(back_populates="share_event")
