"""Notification endpoints for the in-app notification center.

Notifications are generated from the user's own data by
``app/services/notifications.py``; these endpoints just serve them and
track read state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationsResponse
from app.services.notifications import list_notifications, mark_all_read

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> NotificationsResponse:
    """Return the user's notifications (newest first) plus unread count.

    Cheap reminders are topped up on read, so no background scheduler is
    required.
    """
    items, unread = await list_notifications(db, current)
    return NotificationsResponse(unread_count=unread, items=items)


@router.post("/read", response_model=NotificationsResponse)
async def mark_read(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> NotificationsResponse:
    """Mark all notifications as read and return the refreshed list."""
    await mark_all_read(db, current)
    items, unread = await list_notifications(db, current)
    return NotificationsResponse(unread_count=unread, items=items)
