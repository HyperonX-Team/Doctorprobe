"""Report orchestration: builds, encrypts, and stores a checkup."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkup import Checkup
from app.models.device_reading import DeviceReading
from app.models.user import User
from app.services import simulator
from app.utils import crypto

logger = logging.getLogger(__name__)


class ReportService:
    """Creates checkups from simulated biomarker reports."""

    @staticmethod
    async def _latest_reading(
        db: AsyncSession, device_id: str
    ) -> DeviceReading | None:
        """Fetch the most recent device reading for a device."""
        result = await db.execute(
            select(DeviceReading)
            .where(DeviceReading.device_id == device_id)
            .order_by(DeviceReading.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _profile_from_user(user: User) -> dict[str, Any]:
        """Build the simulator profile dict from a user row."""
        return {
            "age": user.age,
            "sex": user.sex,
            "height_cm": user.height_cm,
            "weight_kg": user.weight_kg,
            "activity_level": user.activity_level,
        }

    @staticmethod
    async def create_checkup(
        db: AsyncSession,
        user: User,
        use_device_reading: bool,
    ) -> Checkup:
        """Run the simulation and persist an encrypted checkup.

        Args:
            db: Async database session.
            user: The owning user (must be loaded in ``db``).
            use_device_reading: When True, require and consume the latest
                physical device reading; raise 409 when none exists.

        Returns:
            The persisted (unflushed) ``Checkup``.
        """
        sensor_reading: dict[str, Any] | None = None
        if use_device_reading:
            reading = await ReportService._latest_reading(db, user.device_id)
            if reading is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "No device reading available. "
                        "Take a reading with your Doctordrobe device first."
                    ),
                )
            sensor_reading = {
                "rgb_r": reading.rgb_r,
                "rgb_g": reading.rgb_g,
                "rgb_b": reading.rgb_b,
                "temperature_c": reading.temperature_c,
                "humidity_pct": reading.humidity_pct,
            }
            logger.info("using device reading %s", reading.id)

        report = simulator.generate_report(
            profile=ReportService._profile_from_user(user),
            sensor_reading=sensor_reading,
            user_key=str(user.id),
        )

        checkup = Checkup(
            user_id=user.id,
            summary=report["summary"],
            overall_risk=report["overall_risk"],
            encrypted_data=crypto.encrypt_json(
                {
                    "text_summary": report["text_summary"],
                    "overall_risk": report["overall_risk"],
                    "biomarkers": report["biomarkers"],
                }
            ),
        )
        db.add(checkup)
        return checkup
