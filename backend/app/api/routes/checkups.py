"""Checkup endpoints: create (device-driven), read, delete, share."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.checkup import Checkup
from app.models.share_event import ShareEvent
from app.models.user import User
from app.schemas.checkup import (
    CheckupCreate,
    CheckupCreateResponse,
    CheckupResponse,
    DeleteCheckupRequest,
    ShareCheckupRequest,
    ShareResponse,
)
from app.services.report import ReportService
from app.utils import crypto

router = APIRouter(prefix="/api/checkups", tags=["checkups"])


async def _get_checkup_or_404(db: AsyncSession, checkup_id: uuid.UUID) -> Checkup:
    """Load a checkup by id or raise 404."""
    result = await db.execute(select(Checkup).where(Checkup.id == checkup_id))
    checkup = result.scalar_one_or_none()
    if checkup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Checkup not found"
        )
    return checkup


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Load a user by id or raise 404."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def _assert_ownership(checkup: Checkup, user_id: uuid.UUID) -> None:
    """Guard: only the owning user may act on a checkup."""
    if checkup.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Checkup does not belong to this user",
        )


@router.post("", response_model=CheckupCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_checkup(
    payload: CheckupCreate, db: AsyncSession = Depends(get_db)
) -> CheckupCreateResponse:
    """Analyse the user's latest device reading.

    Reports are always derived from physical sensor data; when the user's
    device has never posted a reading, a 409 is returned. The full report
    is encrypted at rest.
    """
    user = await _get_user_or_404(db, payload.user_id)
    try:
        checkup = await ReportService.create_checkup(db, user)
        await db.commit()
        await db.refresh(checkup)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surfaced to ops via the log
        await db.rollback()
        logger.exception("checkup generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate checkup",
        )

    return CheckupCreateResponse(
        id=checkup.id,
        user_id=checkup.user_id,
        summary=checkup.summary,
        overall_risk=checkup.overall_risk,
        created_at=checkup.created_at,
        is_shared=checkup.is_shared,
    )


@router.get("/{checkup_id}", response_model=CheckupResponse)
async def get_checkup(
    checkup_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="Owning user id"),
    db: AsyncSession = Depends(get_db),
) -> CheckupResponse:
    """Return a checkup with its decrypted full report."""
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, user_id)

    report = crypto.decrypt_json(checkup.encrypted_data)
    return CheckupResponse(
        id=checkup.id,
        user_id=checkup.user_id,
        summary=checkup.summary,
        overall_risk=report["overall_risk"],
        text_summary=report["text_summary"],
        biomarkers=report["biomarkers"],
        created_at=checkup.created_at,
        is_shared=checkup.is_shared,
    )


@router.delete("/{checkup_id}", status_code=status.HTTP_200_OK)
async def delete_checkup(
    checkup_id: uuid.UUID,
    payload: DeleteCheckupRequest | None = None,
    user_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a checkup. Ownership may be passed as JSON body or query param."""
    checkup = await _get_checkup_or_404(db, checkup_id)
    owner_id = payload.user_id if payload else user_id
    if owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required (body or query parameter)",
        )
    _assert_ownership(checkup, owner_id)

    try:
        await db.execute(delete(Checkup).where(Checkup.id == checkup_id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete checkup",
        )
    return {"detail": "Checkup deleted"}


@router.post("/{checkup_id}/share", response_model=ShareResponse)
async def share_checkup(
    checkup_id: uuid.UUID,
    payload: ShareCheckupRequest,
    db: AsyncSession = Depends(get_db),
) -> ShareResponse:
    """Share a checkup and award tokens (once per checkup)."""
    settings = get_settings()
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, payload.user_id)

    if checkup.is_shared:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This checkup has already been shared",
        )

    user = await _get_user_or_404(db, payload.user_id)
    try:
        checkup.is_shared = True
        user.token_balance += settings.TOKEN_REWARD
        db.add(
            ShareEvent(
                checkup_id=checkup.id,
                tokens_awarded=settings.TOKEN_REWARD,
            )
        )
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not share checkup",
        )

    return ShareResponse(
        checkup_id=checkup.id,
        tokens_awarded=settings.TOKEN_REWARD,
        new_balance=user.token_balance,
        is_shared=True,
    )
