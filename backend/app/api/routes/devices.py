"""Device endpoints: ingest sensor readings from the ESP32 and report status."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_device_api_key
from app.db.session import get_db
from app.models.device_baseline import DeviceBaseline
from app.models.device_reading import DeviceReading
from app.schemas.device import (
    DeviceBaselineCreate,
    DeviceBaselineResponse,
    DeviceReadingCreate,
    DeviceReadingResponse,
    DeviceStatus,
)

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; assume they are UTC and tag them."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post(
    "/reading",
    response_model=DeviceReadingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_device_api_key)],
)
async def create_reading(
    payload: DeviceReadingCreate, db: AsyncSession = Depends(get_db)
) -> DeviceReading:
    """Ingest a sensor snapshot posted by the firmware.

    The endpoint is protected by the ``X-API-Key`` header when
    ``DEVICE_API_KEY`` is configured (see ``app/core/security.py``).
    """
    try:
        reading = DeviceReading(**payload.model_dump())
        db.add(reading)
        await db.commit()
        await db.refresh(reading)
        return reading
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not store device reading",
        )


@router.get("/latest", response_model=DeviceReadingResponse)
async def get_latest_reading(
    device_id: str = Query(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> DeviceReading:
    """Return the most recent reading for a device."""
    result = await db.execute(
        select(DeviceReading)
        .where(DeviceReading.device_id == device_id)
        .order_by(DeviceReading.created_at.desc())
        .limit(1)
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No readings recorded for this device",
        )
    return reading


@router.get("/status", response_model=DeviceStatus)
async def get_device_status(
    device_id: str = Query(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> DeviceStatus:
    """Report whether the device has been seen recently.

    ``connected`` is True when the newest reading falls inside the
    ``DEVICE_STALE_SECONDS`` window.
    """
    settings = get_settings()
    result = await db.execute(
        select(DeviceReading)
        .where(DeviceReading.device_id == device_id)
        .order_by(DeviceReading.created_at.desc())
        .limit(1)
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        return DeviceStatus(connected=False, last_seen=None)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.DEVICE_STALE_SECONDS
    )
    return DeviceStatus(
        connected=_as_aware(reading.created_at) > stale_cutoff,
        last_seen=reading.created_at,
    )


@router.post(
    "/baseline",
    response_model=DeviceBaselineResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_device_api_key)],
)
async def upsert_device_baseline(
    payload: DeviceBaselineCreate, db: AsyncSession = Depends(get_db)
) -> DeviceBaseline:
    """Store (or update) a device's blank-pad baseline (CAL BLANK).

    The analyzer gain-corrects every reading against this baseline, so
    optics/LED drift between units does not bias biomarker estimates.
    """
    result = await db.execute(
        select(DeviceBaseline).where(DeviceBaseline.device_id == payload.device_id)
    )
    baseline = result.scalar_one_or_none()
    try:
        if baseline is None:
            baseline = DeviceBaseline(**payload.model_dump())
            db.add(baseline)
        else:
            baseline.rgb_r = payload.rgb_r
            baseline.rgb_g = payload.rgb_g
            baseline.rgb_b = payload.rgb_b
        await db.commit()
        await db.refresh(baseline)
        return baseline
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not store device baseline",
        )


@router.get("/baseline", response_model=DeviceBaselineResponse)
async def get_device_baseline(
    device_id: str = Query(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> DeviceBaseline:
    """Return the stored blank baseline for a device."""
    result = await db.execute(
        select(DeviceBaseline).where(DeviceBaseline.device_id == device_id)
    )
    baseline = result.scalar_one_or_none()
    if baseline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No baseline recorded for this device — run CAL BLANK on the firmware",
        )
    return baseline
