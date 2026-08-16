"""Checkup endpoints: create (device-driven), read, delete, share.

The owning user is always derived from the session token
(``get_current_user``) — no user id is accepted from the client, so a
token can never act on another user's checkups.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.checkup import Checkup
from app.models.share_event import ShareEvent
from app.models.user import User
from app.schemas.checkup import (
    CheckupCreate,
    CheckupCreateResponse,
    CheckupResponse,
    NoteUpdate,
    ShareResponse,
)
from app.services.export import build_clinician_pdf
from app.services.notifications import generate_for_checkup, generate_for_share
from app.services.report import ReportService
from app.utils import crypto

logger = logging.getLogger(__name__)

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


def _assert_ownership(checkup: Checkup, user: User) -> None:
    """Guard: only the owning user may act on a checkup."""
    if checkup.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Checkup does not belong to this user",
        )


@router.post("", response_model=CheckupCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_checkup(
    payload: CheckupCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> CheckupCreateResponse:
    """Analyse the authenticated user's latest device reading.

    Reports are always derived from physical sensor data; when the user's
    device has never posted a reading, a 409 is returned. The full report
    is encrypted at rest.
    """
    try:
        checkup = await ReportService.create_checkup(db, current)
        await generate_for_checkup(db, current, checkup)
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
        quality_grade=checkup.quality_grade,
        created_at=checkup.created_at,
        is_shared=checkup.is_shared,
    )


@router.get("/{checkup_id}", response_model=CheckupResponse)
async def get_checkup(
    checkup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> CheckupResponse:
    """Return a checkup with its decrypted full report."""
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, current)

    report = crypto.decrypt_json(checkup.encrypted_data)
    return CheckupResponse(
        id=checkup.id,
        user_id=checkup.user_id,
        summary=checkup.summary,
        overall_risk=report["overall_risk"],
        text_summary=report["text_summary"],
        biomarkers=report["biomarkers"],
        analysis=report.get("analysis"),
        quality=report.get("quality"),
        note=report.get("note"),
        created_at=checkup.created_at,
        is_shared=checkup.is_shared,
    )


@router.get("/{checkup_id}/export", response_class=Response)
async def export_checkup_pdf(
    checkup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    """Return a clinician-facing PDF of the checkup (owner only)."""
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, current)

    pdf_bytes = await build_clinician_pdf(db, checkup, current)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="doctordrobe-report-{checkup.id}.pdf"'
            )
        },
    )


@router.delete("/{checkup_id}", status_code=status.HTTP_200_OK)
async def delete_checkup(
    checkup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Delete one of the authenticated user's checkups."""
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, current)

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
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ShareResponse:
    """Share a checkup and award tokens (once per checkup)."""
    settings = get_settings()
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, current)

    if checkup.is_shared:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This checkup has already been shared",
        )

    try:
        checkup.is_shared = True
        current.token_balance += settings.TOKEN_REWARD
        db.add(
            ShareEvent(
                checkup_id=checkup.id,
                tokens_awarded=settings.TOKEN_REWARD,
            )
        )
        await db.commit()
        await db.refresh(current)
    except IntegrityError:
        # Concurrent share lost the race: the unique constraint on
        # share_events.checkup_id is the source of truth.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This checkup has already been shared",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not share checkup",
        )

    await generate_for_share(db, current, checkup)
    await db.commit()

    return ShareResponse(
        checkup_id=checkup.id,
        tokens_awarded=settings.TOKEN_REWARD,
        new_balance=current.token_balance,
        is_shared=True,
    )


@router.put("/{checkup_id}/note", response_model=CheckupResponse)
async def update_checkup_note(
    checkup_id: uuid.UUID,
    payload: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> CheckupResponse:
    """Set or clear the user's note on a checkup.

    The note is stored inside the encrypted report payload, so it is
    protected at rest exactly like the biomarker data itself.
    """
    checkup = await _get_checkup_or_404(db, checkup_id)
    _assert_ownership(checkup, current)

    report = crypto.decrypt_json(checkup.encrypted_data)
    report["note"] = payload.note.strip() if payload.note else None
    checkup.encrypted_data = crypto.encrypt_json(report)
    try:
        await db.commit()
        await db.refresh(checkup)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not save the note",
        )

    return CheckupResponse(
        id=checkup.id,
        user_id=checkup.user_id,
        summary=checkup.summary,
        overall_risk=report["overall_risk"],
        text_summary=report["text_summary"],
        biomarkers=report["biomarkers"],
        analysis=report.get("analysis"),
        quality=report.get("quality"),
        note=report.get("note"),
        created_at=checkup.created_at,
        is_shared=checkup.is_shared,
    )
