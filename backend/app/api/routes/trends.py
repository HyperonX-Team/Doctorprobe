"""Trends endpoints: longitudinal per-marker series and alerts.

The owning user is always derived from the session token. Trends decrypt
the user's own checkups server-side and return only aggregated series,
stats and alerts — never the encrypted payloads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.trends import build_trends, build_trends_csv

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
async def get_trends(
    window_days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Return per-marker time series, statistics and alerts.

    ``window_days`` bounds how far back checkups are considered
    (default 30 days, up to 365). Only the authenticated user's own
    checkups are ever read.
    """
    return await build_trends(db, current.id, window_days)


@router.get("/export", response_class=Response)
async def export_trends(
    window_days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    """Download the trends series as CSV (one row per marker point)."""
    csv_text = await build_trends_csv(db, current.id, window_days)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="doctordrobe-trends-{window_days}d.csv"'
            )
        },
    )
