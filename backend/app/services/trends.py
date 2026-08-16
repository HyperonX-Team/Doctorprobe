"""Longitudinal trends: per-marker time series, statistics, and alerts.

Also builds a CSV export of the same data (``build_trends_csv``) so the
user can pull their series into a spreadsheet.

A single reading is a snapshot; a sequence of checkups is a signal. This
service decrypts a user's checkups, builds a per-marker time series over
a window, and derives explainable, deterministic alerts:

* ``rising_trend`` / ``falling_trend`` — the last three values moved in
  the same direction;
* ``deviation_from_baseline`` — the latest value is more than 2 standard
  deviations away from the mean of the user's earlier readings;
* ``repeated_out_of_range`` — at least two of the last three readings
  fell outside the reference range;
* ``new_out_of_range`` — the latest reading is out of range after in-range
  readings.

Alert thresholds are intentionally simple and conservative; they are a
heads-up for the user to look closer, never a diagnosis.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkup import Checkup
from app.utils import crypto

# Marker keys in panel order (matches the analyzer's panel).
MARKER_ORDER = ("glucose", "crp", "cortisol", "ph", "siga")

_MIN_TREND_POINTS = 3
_TREND_RUN = 3
_DEVIATION_Z = 2.0


def _marker_meta(biomarkers: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Pull name/unit/reference bounds from the latest reported biomarker."""
    for marker in biomarkers:
        if marker.get("key") == key:
            return {
                "name": marker["name"],
                "unit": marker["unit"],
                "ref_low": marker.get("ref_low"),
                "ref_high": marker.get("ref_high"),
            }
    return {"name": key, "unit": "", "ref_low": None, "ref_high": None}


def _stats(values: list[float]) -> dict[str, float]:
    """Mean / std / min / max over the window (deterministic)."""
    count = len(values)
    mean = sum(values) / count
    if count > 1:
        variance = sum((v - mean) ** 2 for v in values) / (count - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0
    return {
        "count": count,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "latest": round(values[-1], 2),
    }


def _alerts(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive deterministic alerts for one marker's series (oldest→newest)."""
    alerts: list[dict[str, Any]] = []
    if len(points) < _MIN_TREND_POINTS:
        return alerts

    last_run = points[-_TREND_RUN:]
    rising = all(
        last_run[i]["value"] < last_run[i + 1]["value"]
        for i in range(len(last_run) - 1)
    )
    falling = all(
        last_run[i]["value"] > last_run[i + 1]["value"]
        for i in range(len(last_run) - 1)
    )
    name = points[-1]["name"]
    if rising:
        alerts.append(
            {
                "type": "rising_trend",
                "severity": "warning",
                "message": (
                    f"{name} has risen over the last {_TREND_RUN} checkups "
                    f"({last_run[0]['value']:.2f} → {last_run[-1]['value']:.2f} "
                    f"{points[-1]['unit']}). Worth keeping an eye on."
                ),
            }
        )
    elif falling:
        alerts.append(
            {
                "type": "falling_trend",
                "severity": "info",
                "message": (
                    f"{name} has fallen over the last {_TREND_RUN} checkups "
                    f"({last_run[0]['value']:.2f} → {last_run[-1]['value']:.2f} "
                    f"{points[-1]['unit']})."
                ),
            }
        )

    # Deviation of the latest value from the user's own earlier baseline.
    if len(points) >= _MIN_TREND_POINTS + 1:
        prior = [p["value"] for p in points[:-1]]
        mean = sum(prior) / len(prior)
        variance = sum((v - mean) ** 2 for v in prior) / (len(prior) - 1)
        std = math.sqrt(variance)
        latest = points[-1]["value"]
        if std > 1e-9 and abs(latest - mean) > _DEVIATION_Z * std:
            direction = "above" if latest > mean else "below"
            alerts.append(
                {
                    "type": "deviation_from_baseline",
                    "severity": "warning",
                    "message": (
                        f"Latest {name} ({latest:.2f} {points[-1]['unit']}) is "
                        f"more than 2 standard deviations {direction} your "
                        f"typical range (mean {mean:.2f})."
                    ),
                }
            )

    # Out-of-range persistence across the last three readings.
    last_three = points[-3:]
    out_of_range = [p for p in last_three if p["state"] != "normal"]
    if len(out_of_range) >= 2:
        alerts.append(
            {
                "type": "repeated_out_of_range",
                "severity": "warning",
                "message": (
                    f"{name} has been {out_of_range[-1]['state']} in "
                    f"{len(out_of_range)} of the last {len(last_three)} checkups. "
                    "Consider repeating the test or speaking with a clinician."
                ),
            }
        )
    elif len(out_of_range) == 1 and out_of_range[0] is last_three[-1]:
        alerts.append(
            {
                "type": "new_out_of_range",
                "severity": "info",
                "message": (
                    f"Latest {name} is {out_of_range[0]['state']} "
                    "after being within range — consider a follow-up test."
                ),
            }
        )

    return alerts


def _as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; assume they are UTC and tag them."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def build_trends(
    db: AsyncSession, user_id: Any, window_days: int
) -> dict[str, Any]:
    """Build the trends payload for a user over the last ``window_days``.

    Returns a dict keyed by marker with ``points`` (oldest→newest),
    ``stats`` and ``alerts``, plus top-level counts for the UI.

    The window filter runs in Python (not SQL) because SQLite returns
    naive datetimes; comparing them against an aware cutoff in SQL would
    silently drop rows.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    result = await db.execute(
        select(Checkup)
        .where(Checkup.user_id == user_id)
        .order_by(Checkup.created_at.asc())
    )
    checkups = [
        c for c in result.scalars().all() if _as_aware(c.created_at) >= cutoff
    ]

    markers: dict[str, dict[str, Any]] = {
        key: {"key": key, "points": []} for key in MARKER_ORDER
    }
    meta_seen: dict[str, dict[str, Any]] = {}

    for checkup in checkups:
        report = crypto.decrypt_json(checkup.encrypted_data)
        for biomarker in report.get("biomarkers", []):
            key = biomarker.get("key")
            if key not in markers:
                continue
            meta_seen[key] = _marker_meta(report["biomarkers"], key)
            markers[key]["points"].append(
                {
                    "date": checkup.created_at,
                    "value": biomarker["value"],
                    "state": biomarker["state"],
                    "confidence": biomarker.get("confidence"),
                }
            )

    alert_count = 0
    for key, data in markers.items():
        meta = meta_seen.get(key)
        if meta:
            data["name"] = meta["name"]
            data["unit"] = meta["unit"]
            data["ref_low"] = meta["ref_low"]
            data["ref_high"] = meta["ref_high"]
        else:
            data["name"] = key
            data["unit"] = ""
            data["ref_low"] = None
            data["ref_high"] = None

        points = data["points"]
        data["stats"] = _stats([p["value"] for p in points]) if points else None
        for point in points:
            point["name"] = data["name"]
            point["unit"] = data["unit"]
        alerts = _alerts(points) if points else []
        data["alerts"] = alerts
        alert_count += len(alerts)

    return {
        "window_days": window_days,
        "checkup_count": len(checkups),
        "alert_count": alert_count,
        "markers": markers,
    }


async def build_trends_csv(
    db: AsyncSession, user_id: Any, window_days: int
) -> str:
    """Render the trends payload as CSV (date, marker, value, unit, state).

    One row per (checkup, marker) point, oldest first, matching the
    ``build_trends`` payload exactly — the export is just the same
    series in spreadsheet form.
    """
    import csv
    import io

    trends = await build_trends(db, user_id, window_days)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "marker", "value", "unit", "state"])
    for key in MARKER_ORDER:
        marker = trends["markers"][key]
        for point in marker.get("points", []):
            writer.writerow(
                [
                    point["date"].date().isoformat()
                    if hasattr(point["date"], "date")
                    else str(point["date"])[:10],
                    marker["name"],
                    f"{point['value']:.2f}",
                    marker["unit"],
                    point["state"],
                ]
            )
    return buffer.getvalue()
