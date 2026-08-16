"""In-app notification generation.

Notifications are derived deterministically from the user's own data and
persisted in the ``notifications`` table. Generation is **idempotent**:
every notification carries a per-user ``dedupe_key`` (guarded by a unique
constraint), so re-running the generators never duplicates rows.

Sources:

* ``generate_for_checkup`` — poor measurement quality and trend alerts
  (called once per created checkup, where decrypting the history is cheap).
* ``generate_for_share`` — the token reward earned by sharing (called by
  the share endpoint).
* ``sync_notifications`` — the weekly checkup reminder, computed lazily
  on read so no scheduler is needed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.checkup import Checkup
from app.models.notification import Notification
from app.models.share_event import ShareEvent
from app.models.user import User
from app.services.trends import build_trends

_TREND_WINDOW_DAYS = 30


def _iso_week_key(now: datetime) -> str:
    """ISO year-week key (e.g. ``2026-W33``) for weekly deduplication."""
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; assume they are UTC and tag them."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _add(
    db: AsyncSession,
    user_id: object,
    dedupe_key: str,
    kind: str,
    message: str,
) -> Notification | None:
    """Insert a notification, ignoring the duplicate-race gracefully.

    The insert runs inside a nested transaction (savepoint): if the
    unique ``(user_id, dedupe_key)`` constraint fires because another
    request already created this notification, only the failed insert is
    rolled back — earlier notifications in the same batch survive.
    """
    notification = Notification(
        user_id=user_id,
        dedupe_key=dedupe_key,
        kind=kind,
        message=message,
    )
    try:
        async with db.begin_nested():
            db.add(notification)
            await db.flush()
        return notification
    except IntegrityError:
        # Already generated — the dedupe key wins, keep the rest of the batch.
        return None


async def generate_for_checkup(
    db: AsyncSession, user: User, checkup: Checkup
) -> list[Notification]:
    """Create notifications tied to a freshly created checkup.

    * A ``quality`` notification when the measurement grade is ``poor``.
    * One ``trend`` notification per deterministic trend alert, keyed to
      the alert's marker/type and the latest point's date so a new
      episode produces a fresh heads-up.
    """
    created: list[Notification] = []

    if checkup.quality_grade == "poor":
        note = await _add(
            db,
            user.id,
            f"poor-quality:{checkup.id}",
            "quality",
            (
                "Your latest reading had poor measurement quality — the "
                "results may not be trustworthy. Consider retaking the "
                "reading with a fresh strip."
            ),
        )
        if note is not None:
            created.append(note)

    trends = await build_trends(db, user.id, _TREND_WINDOW_DAYS)
    for key, marker in trends.get("markers", {}).items():
        for alert in marker.get("alerts", []):
            points = marker.get("points", [])
            latest_date = points[-1]["date"] if points else checkup.created_at
            date_key = _as_aware(latest_date).date().isoformat()
            note = await _add(
                db,
                user.id,
                f"trend:{key}:{alert['type']}:{date_key}",
                "trend",
                alert["message"],
            )
            if note is not None:
                created.append(note)

    return created


async def generate_for_share(
    db: AsyncSession, user: User, checkup: Checkup
) -> Notification | None:
    """Create the token-reward notification for a shared checkup."""
    return await _add(
        db,
        user.id,
        f"reward:{checkup.id}",
        "reward",
        (
            f"You shared a checkup and earned {get_settings().TOKEN_REWARD} "
            f"tokens. Thank you for contributing to Community Insights!"
        ),
    )


async def sync_notifications(db: AsyncSession, user: User) -> list[Notification]:
    """Top up notifications that are cheap to compute on read.

    Currently the weekly checkup reminder: when the user has checkups but
    the most recent one is older than ``NOTIFICATION_REMINDER_DAYS``, a
    ``reminder`` notification is generated once per ISO week.
    """
    settings = get_settings()
    result = await db.execute(
        select(Checkup)
        .where(Checkup.user_id == user.id)
        .order_by(Checkup.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return []

    now = datetime.now(timezone.utc)
    last = _as_aware(latest.created_at)
    days_since = (now - last).total_seconds() / 86400
    if days_since < settings.NOTIFICATION_REMINDER_DAYS:
        return []

    note = await _add(
        db,
        user.id,
        f"reminder:{_iso_week_key(now)}",
        "reminder",
        (
            f"It's been {int(days_since)} days since your last checkup. "
            "Consistent measurements make your trends more meaningful."
        ),
    )
    return [note] if note is not None else []


async def list_notifications(
    db: AsyncSession, user: User
) -> tuple[list[Notification], int]:
    """Sync reminders, then return (newest-first, unread count)."""
    await sync_notifications(db, user)
    await db.commit()

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    items = list(result.scalars().all())
    unread = sum(1 for n in items if n.read_at is None)
    return items, unread


async def mark_all_read(db: AsyncSession, user: User) -> int:
    """Mark every unread notification as read; returns the count touched."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    )
    items = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    for notification in items:
        notification.read_at = now
    await db.commit()
    return len(items)
