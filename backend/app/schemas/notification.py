"""Notification request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """One in-app notification."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    message: str
    created_at: datetime
    read_at: datetime | None = None


class NotificationsResponse(BaseModel):
    """Notification list with the unread count."""

    unread_count: int
    items: list[NotificationResponse]
