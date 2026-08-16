"""Community Insights: anonymized cohort aggregates.

Implements the /api/shares marketplace. Shared checkups (``is_shared``,
awarded tokens) are decrypted **server-side only** and reduced to
per-marker aggregates — means, standard deviations and percentiles — so
raw biomarker rows never leave the server. The authenticated user gets
a ``you vs similar profiles`` comparison: their latest value against the
cohort restricted to the same sex, age band (±5 years) and activity
level, plus the community-wide aggregate.

Aggregates are only reported when the cohort is large enough
(``min_cohort``); below that the payload still returns counts so the UI
can show \"keep sharing\" state honestly.
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkup import Checkup
from app.models.share_event import ShareEvent
from app.models.user import User
from app.utils import crypto

#: Marker keys in panel order (matches the analyzer's panel).
MARKER_ORDER = ("glucose", "crp", "cortisol", "ph", "siga")

#: Minimum cohort size before a percentile comparison is meaningful.
MIN_COHORT = 3

#: Age band used for the \"similar profiles\" filter.
AGE_BAND = 5


def _percentile(values: list[float], value: float) -> float:
    """Fraction of ``values`` strictly below ``value`` (0..1)."""
    if not values:
        return 0.0
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return (below + 0.5 * equal) / len(values)


def _aggregate(values: list[float]) -> dict[str, float | None]:
    """Mean / std / p10 / p50 / p90 over a list of values."""
    if not values:
        return {
            "mean": None,
            "std": None,
            "p10": None,
            "p50": None,
            "p90": None,
        }
    ordered = sorted(values)
    n = len(ordered)
    mean = sum(ordered) / n
    variance = sum((v - mean) ** 2 for v in ordered) / (n - 1) if n > 1 else 0.0

    def p(q: float) -> float:
        index = q * (n - 1)
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return {
        "mean": round(mean, 3),
        "std": round(math.sqrt(variance), 3),
        "p10": round(p(0.10), 3),
        "p50": round(p(0.50), 3),
        "p90": round(p(0.90), 3),
    }


def _marker_values(
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract per-marker value/state from a decrypted report."""
    out: dict[str, dict[str, Any]] = {}
    for marker in report.get("biomarkers", []):
        key = marker.get("key")
        if key in MARKER_ORDER:
            out[key] = {
                "value": marker["value"],
                "state": marker["state"],
                "ref_low": marker.get("ref_low"),
                "ref_high": marker.get("ref_high"),
            }
    return out


async def build_community_insights(db: AsyncSession, user: User) -> dict[str, Any]:
    """Build the community insight payload for ``user``.

    Reads only *shared* checkups belonging to *other* users; everything
    is aggregated server-side. The user's own latest checkup supplies
    their comparison values and the reference ranges to display.
    """
    result = await db.execute(
        select(Checkup, User)
        .join(ShareEvent, ShareEvent.checkup_id == Checkup.id)
        .join(User, User.id == Checkup.user_id)
        .where(Checkup.is_shared.is_(True), Checkup.user_id != user.id)
    )
    cohort_rows = result.all()

    # User's own latest checkup for the comparison anchor.
    own_result = await db.execute(
        select(Checkup)
        .where(Checkup.user_id == user.id)
        .order_by(Checkup.created_at.desc())
        .limit(1)
    )
    own_latest = own_result.scalar_one_or_none()

    markers: dict[str, dict[str, Any]] = {
        key: {"key": key, "name": key, "unit": "", "cohort_values": []}
        for key in MARKER_ORDER
    }

    similar_owners: set = set()
    for checkup, owner in cohort_rows:
        report = crypto.decrypt_json(checkup.encrypted_data)
        for key, marker in _marker_values(report).items():
            entry = markers[key]
            entry["cohort_values"].append(marker["value"])
            if not entry["name"] or entry["name"] == key:
                entry["name"] = _friendly_name(key)
                entry["unit"] = _unit(key, marker)
            if _similar(owner, user):
                similar_owners.add(owner.id)

    # User's own latest values (if any) and displayed reference ranges.
    user_values: dict[str, dict[str, Any]] = {}
    if own_latest is not None:
        report = crypto.decrypt_json(own_latest.encrypted_data)
        user_values = _marker_values(report)

    out_markers: dict[str, dict[str, Any]] = {}
    for key in MARKER_ORDER:
        entry = markers[key]
        cohort_values = entry["cohort_values"]
        agg = _aggregate(cohort_values)
        own = user_values.get(key)
        percentile = (
            round(_percentile(cohort_values, own["value"]), 3)
            if own is not None and len(cohort_values) >= MIN_COHORT
            else None
        )
        ref_low, ref_high = None, None
        if own is not None:
            ref_low, ref_high = own.get("ref_low"), own.get("ref_high")
        out_markers[key] = {
            "key": key,
            "name": entry["name"] if entry["name"] != key else _friendly_name(key),
            "unit": entry["unit"] or _unit(key, None),
            "user_latest": own["value"] if own is not None else None,
            "user_state": own["state"] if own is not None else None,
            "cohort_count": len(cohort_values),
            "cohort_mean": agg["mean"],
            "cohort_std": agg["std"],
            "cohort_p10": agg["p10"],
            "cohort_p50": agg["p50"],
            "cohort_p90": agg["p90"],
            "user_percentile": percentile,
            "ref_low": ref_low,
            "ref_high": ref_high,
        }

    return {
        "cohort_checkups": len(cohort_rows),
        "cohort_users": len({owner.id for _, owner in cohort_rows}),
        "min_cohort": MIN_COHORT,
        "similar_profile": {
            "sex": user.sex,
            "age_band": f"{max(1, user.age - AGE_BAND)}-{user.age + AGE_BAND}",
            "activity_level": user.activity_level,
        },
        "similar_profile_count": len(similar_owners),
        "markers": out_markers,
    }


def _similar(owner: User, user: User) -> bool:
    """True when ``owner`` falls in the same profile band as ``user``."""
    return (
        owner.sex == user.sex
        and abs((owner.age or 0) - (user.age or 0)) <= AGE_BAND
        and owner.activity_level == user.activity_level
    )


_FRIENDLY = {
    "glucose": "Salivary Glucose",
    "crp": "Salivary CRP",
    "cortisol": "Salivary Cortisol",
    "ph": "Salivary pH",
    "siga": "Secretory IgA",
}

_UNITS = {
    "glucose": "mg/dL",
    "crp": "ng/mL",
    "cortisol": "µg/dL",
    "ph": "pH",
    "siga": "mg/dL",
}


def _friendly_name(key: str) -> str:
    return _FRIENDLY.get(key, key)


def _unit(key: str, marker: dict[str, Any] | None) -> str:
    if marker is not None and marker.get("unit"):
        return marker["unit"]
    return _UNITS.get(key, "")
