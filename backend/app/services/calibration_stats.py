"""Calibration dashboard stats.

Answers the two questions the calibration workflow raises:

* **Do I have enough labeled samples?** Per analyte: sample count,
  concentration span, and whether the count meets the trainer's real-data
  threshold (``MIN_REAL_SAMPLES``, mirrored from ``scripts/train_model.py``).
* **What is the current model trained on?** From the SaliNet manifest:
  version, training time, per-analyte data source (``real`` vs
  ``synthetic``) and held-out metrics.

The payload is read-only; it never mutates samples or the model.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calibration_sample import CalibrationSample
from app.schemas.calibration import ANALYTE_BOUNDS

#: Minimum real samples per analyte before the trainer trusts them over
#: synthetic data (must match scripts/train_model.py).
MIN_REAL_SAMPLES = 15

_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "services" / "model" / "salinet.json"
)

ANALYTE_NAMES = {
    "glucose": "Salivary Glucose",
    "crp": "Salivary CRP",
    "cortisol": "Salivary Cortisol",
    "siga": "Secretory IgA",
}

ANALYTE_UNITS = {
    "glucose": "mg/dL",
    "crp": "ng/mL",
    "cortisol": "µg/dL",
    "siga": "mg/dL",
}


def _read_manifest() -> dict[str, Any]:
    """Load the SaliNet manifest, or return a bare dict when absent."""
    if not _MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


async def build_calibration_stats(db: AsyncSession) -> dict[str, Any]:
    """Build the per-analyte coverage and model status payload."""
    result = await db.execute(
        select(
            CalibrationSample.analyte,
            func.count(CalibrationSample.id),
            func.min(CalibrationSample.concentration),
            func.max(CalibrationSample.concentration),
            func.max(CalibrationSample.created_at),
        ).group_by(CalibrationSample.analyte)
    )
    rows = {
        analyte: {
            "count": count,
            "min_concentration": min_c,
            "max_concentration": max_c,
            "last_sample_at": last_at,
        }
        for analyte, count, min_c, max_c, last_at in result.all()
    }

    manifest = _read_manifest()
    provenance = manifest.get("provenance", {})
    metrics = manifest.get("metrics", {})

    analytes: dict[str, dict[str, Any]] = {}
    for analyte, (envelope_min, envelope_max) in ANALYTE_BOUNDS.items():
        row = rows.get(analyte, {})
        analytes[analyte] = {
            "name": ANALYTE_NAMES[analyte],
            "unit": ANALYTE_UNITS[analyte],
            "count": row.get("count", 0),
            "min_concentration": row.get("min_concentration"),
            "max_concentration": row.get("max_concentration"),
            "envelope_min": envelope_min,
            "envelope_max": envelope_max,
            "enough": (row.get("count") or 0) >= MIN_REAL_SAMPLES,
            "last_sample_at": row.get("last_sample_at"),
            "model_source": provenance.get(analyte, {}).get("source"),
            "model_metrics": metrics.get(analyte, {}),
        }

    return {
        "total_samples": sum(row["count"] for row in analytes.values()),
        "min_real_samples": MIN_REAL_SAMPLES,
        "analytes": analytes,
        "model": {
            "present": bool(manifest),
            "model_name": manifest.get("model_name"),
            "model_version": manifest.get("model_version"),
            "trained_at": manifest.get("trained_at"),
        },
    }
