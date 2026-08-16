"""Report orchestration: builds, encrypts, and stores a checkup.

A checkup is always derived from a physical device reading. When no
reading exists for the user's device, creation fails with HTTP 409.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.checkup import Checkup
from app.models.device_baseline import DeviceBaseline
from app.models.device_reading import DeviceReading
from app.models.user import User
from app.services import analyzer
from app.utils import crypto

logger = logging.getLogger(__name__)


class ReportService:
    """Creates checkups from real device readings."""

    @staticmethod
    async def _latest_burst(
        db: AsyncSession, device_id: str
    ) -> list[DeviceReading]:
        """Fetch the most recent burst of snapshots for a device.

        A burst is the newest cluster of readings captured within
        ``READING_BURST_GAP_SECONDS`` of each other (a firmware button
        press posts several snapshots of the same strip). Returns an
        empty list when the device has never reported.
        """
        result = await db.execute(
            select(DeviceReading)
            .where(DeviceReading.device_id == device_id)
            .order_by(DeviceReading.created_at.desc(), DeviceReading.id.desc())
        )
        rows = list(result.scalars().all())
        if not rows:
            return []
        gap = get_settings().READING_BURST_GAP_SECONDS
        burst = [rows[0]]
        for row in rows[1:]:
            if (burst[-1].created_at - row.created_at).total_seconds() > gap:
                break
            burst.append(row)
        return burst

    @staticmethod
    async def _get_baseline(
        db: AsyncSession, device_id: str
    ) -> DeviceBaseline | None:
        """Fetch the device's blank-pad baseline, if one exists."""
        result = await db.execute(
            select(DeviceBaseline).where(DeviceBaseline.device_id == device_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _profile_from_user(user: User) -> dict[str, Any]:
        """Build the analysis profile dict from a user row."""
        return {
            "age": user.age,
            "sex": user.sex,
            "height_cm": user.height_cm,
            "weight_kg": user.weight_kg,
            "activity_level": user.activity_level,
        }

    @staticmethod
    async def create_checkup(db: AsyncSession, user: User) -> Checkup:
        """Analyse the user's latest device burst and persist a checkup.

        Args:
            db: Async database session.
            user: The owning user (must be loaded in ``db``).

        Returns:
            The persisted (unflushed) ``Checkup``.

        Raises:
            HTTPException 409: when no device reading exists yet.
        """
        readings = await ReportService._latest_burst(db, user.device_id)
        if not readings:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No device reading available. "
                    "Take a reading with your Doctordrobe device first."
                ),
            )

        baseline = await ReportService._get_baseline(db, user.device_id)

        snapshots = []
        for reading in readings:
            sensor_reading = {
                "rgb_r": reading.rgb_r,
                "rgb_g": reading.rgb_g,
                "rgb_b": reading.rgb_b,
                "temperature_c": reading.temperature_c,
                "humidity_pct": reading.humidity_pct,
            }
            # Per-device white balance: gain-correct against the blank-pad
            # baseline so optics drift does not bias the analysis.
            if baseline is not None:
                sensor_reading = analyzer.correct_reading(
                    sensor_reading,
                    {
                        "rgb_r": baseline.rgb_r,
                        "rgb_g": baseline.rgb_g,
                        "rgb_b": baseline.rgb_b,
                    },
                )
            snapshots.append(sensor_reading)
        if baseline is not None:
            logger.info("applied blank-pad baseline for %s", user.device_id)
        logger.info("analysing burst of %d readings for checkup", len(snapshots))

        report = analyzer.generate_report(
            profile=ReportService._profile_from_user(user),
            sensor_reading=snapshots,
            reference_ranges=user.reference_ranges,
        )

        quality = report.get("quality")
        checkup = Checkup(
            user_id=user.id,
            summary=report["summary"],
            overall_risk=report["overall_risk"],
            quality_grade=quality["grade"] if quality else None,
            encrypted_data=crypto.encrypt_json(
                {
                    "text_summary": report["text_summary"],
                    "overall_risk": report["overall_risk"],
                    "biomarkers": report["biomarkers"],
                    "analysis": report["analysis"],
                    "quality": quality,
                    "note": None,
                }
            ),
        )
        db.add(checkup)
        return checkup
