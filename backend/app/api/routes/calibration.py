"""Calibration endpoints: labeled sensor samples for retraining SaliNet.

Workflow:
1. Build control standards with known analyte concentrations (see the
   calibration protocol in the README).
2. Put a strip under the sensor, arm the firmware with a serial
   ``CAL <analyte> <concentration>`` command, press the button — the
   device averages several captures and POSTs a labeled sample here.
3. Repeat over several concentration levels, then download the training
   CSV via GET /api/calibration/export and retrain with
   ``scripts/train_model.py``.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_device_api_key
from app.db.session import get_db
from app.models.calibration_sample import CalibrationSample
from app.schemas.calibration import (
    ANALYTE_BOUNDS,
    CalibrationAnalyte,
    CalibrationSampleCreate,
    CalibrationSampleResponse,
)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])

_TRAINER_COLUMNS = [
    "rgb_r",
    "rgb_g",
    "rgb_b",
    "temperature_c",
    "humidity_pct",
    "glucose",
    "crp",
    "cortisol",
    "siga",
]


@router.post(
    "/samples",
    response_model=CalibrationSampleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_device_api_key)],
)
async def create_calibration_sample(
    payload: CalibrationSampleCreate, db: AsyncSession = Depends(get_db)
) -> CalibrationSample:
    """Store one labeled sensor capture posted by the firmware."""
    lo, hi = ANALYTE_BOUNDS[payload.analyte]
    if not (lo <= payload.concentration <= hi):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"concentration for '{payload.analyte}' must be between "
                f"{lo} and {hi} "
                f"{'mg/dL' if payload.analyte in ('glucose', 'siga') else 'ng/mL' if payload.analyte == 'crp' else 'µg/dL'}"
            ),
        )
    try:
        sample = CalibrationSample(**payload.model_dump())
        db.add(sample)
        await db.commit()
        await db.refresh(sample)
        return sample
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not store calibration sample",
        )


@router.get("/samples", response_model=list[CalibrationSampleResponse])
async def list_calibration_samples(
    analyte: CalibrationAnalyte | None = None,
    limit: int = Query(default=1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
) -> list[CalibrationSample]:
    """List stored samples, optionally filtered by analyte (newest first)."""
    query = select(CalibrationSample).order_by(CalibrationSample.created_at.desc())
    if analyte:
        query = query.where(CalibrationSample.analyte == analyte)
    result = await db.execute(query.limit(limit))
    return list(result.scalars().all())


@router.get("/export", response_class=Response)
async def export_training_csv(db: AsyncSession = Depends(get_db)) -> Response:
    """Export all samples as the trainer's CSV (data/real_training.csv).

    Rows carry the labeled analyte's concentration; other target columns
    are left empty. The trainer uses per-analyte rows independently.
    """
    result = await db.execute(
        select(CalibrationSample).order_by(CalibrationSample.created_at.asc())
    )
    samples = result.scalars().all()
    if not samples:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No calibration samples recorded yet",
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_TRAINER_COLUMNS)
    writer.writeheader()
    for sample in samples:
        row = {column: "" for column in _TRAINER_COLUMNS}
        row.update(
            {
                "rgb_r": sample.rgb_r,
                "rgb_g": sample.rgb_g,
                "rgb_b": sample.rgb_b,
                "temperature_c": sample.temperature_c,
                "humidity_pct": sample.humidity_pct,
                sample.analyte: sample.concentration,
            }
        )
        writer.writerow(row)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="real_training.csv"'
        },
    )


@router.delete("/samples", status_code=status.HTTP_200_OK)
async def clear_calibration_samples(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all stored samples (after a successful retrain)."""
    await db.execute(delete(CalibrationSample))
    await db.commit()
    return {"detail": "Calibration samples cleared"}
