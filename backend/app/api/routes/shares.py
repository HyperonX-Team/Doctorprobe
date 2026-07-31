"""Shared/community endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/shares", tags=["shares"])


@router.get("")
async def list_shared() -> dict:
    """Placeholder for community health-data exchange.

    The share flow currently lives on
    ``POST /api/checkups/{checkup_id}/share``; this router is reserved for
    the anonymized public data marketplace.
    """
    return {"items": []}
