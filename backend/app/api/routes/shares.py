"""Community endpoints: the anonymized Insights marketplace.

``POST /api/checkups/{id}/share`` awards tokens and opts a checkup into
the cohort; this router serves the aggregates. Only server-side
statistics (means, percentiles, counts) ever leave the API — raw shared
checkups are never exposed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import CommunityInsightsResponse
from app.services.community import build_community_insights

router = APIRouter(prefix="/api/shares", tags=["shares"])


@router.get("/insights", response_model=CommunityInsightsResponse)
async def community_insights(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Return anonymized cohort aggregates and a \"you vs similar
    profiles\" comparison.

    The cohort is built exclusively from *shared* checkups of *other*
    users. Every value in the response is a server-side aggregate (or the
    caller's own data) — raw community rows are never returned.
    """
    return await build_community_insights(db, current)
