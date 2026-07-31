"""Biomarker analysis pipeline.

Transforms a real device reading (RGB colour channels, temperature,
humidity) plus the user profile into a biomarker report.

Fully deterministic: the same sensor snapshot and profile always produce
the same report. There is no random sampling and no simulated data — a
checkup can only be created from a physical device reading.

The sensor-to-biomarker mapping below is a linear calibration
placeholder; it is meant to be replaced by a trained ML model once real
spectral calibration data is available.
"""

from __future__ import annotations

from typing import Any

from app.utils.map_range import map_range

# Reference ranges for each biomarker (name, unit, low, high).
_REFERENCE_RANGES: dict[str, tuple[str, float, float]] = {
    "iron": ("ng/mL", 20, 300),
    "vitamin_d": ("ng/mL", 20, 80),
    "crp": ("mg/L", 0.1, 3.0),
    "glucose": ("mg/dL", 70, 140),
    "hdl": ("mg/dL", 40, 90),
}

_RISK_WEIGHTS = {
    "iron": 0.25,
    "vitamin_d": 0.20,
    "crp": 0.30,
    "glucose": 0.15,
    "hdl": 0.10,
}


def _sensor_to_bases(sensor_reading: dict[str, Any]) -> dict[str, float]:
    """Map raw sensor values onto biomarker base values.

    This mapping is a linear calibration placeholder. Replace with a
    trained ML model once real spectral calibration data is available.
    """
    r, g, b = (
        int(sensor_reading.get("rgb_r", 128)),
        int(sensor_reading.get("rgb_g", 128)),
        int(sensor_reading.get("rgb_b", 128)),
    )
    temperature = float(sensor_reading.get("temperature_c", 25.0))
    humidity = float(sensor_reading.get("humidity_pct", 50.0))

    bases: dict[str, float] = {
        # Red channel drives iron (deep colour = higher ferritin).
        "iron": map_range(r, 0, 255, 20, 300),
        # Green channel drives vitamin D (brightness correlates with assay).
        "vitamin_d": map_range(g, 0, 255, 10, 80),
        # Blue channel drives inflammation (CRP).
        "crp": map_range(b, 0, 255, 0.1, 10.0),
        # Temperature offsets glucose.
        "glucose": map_range(temperature, 15, 40, 70, 180),
        # Humidity affects HDL.
        "hdl": map_range(humidity, 20, 90, 30, 90),
    }
    return bases


def _profile_adjustments(profile: dict[str, Any]) -> dict[str, float]:
    """Compute deterministic biomarker adjustments from the user profile.

    - Older age shifts glucose/CRP slightly upward.
    - Higher activity level raises HDL and lowers CRP.
    - Higher BMI (derived from height/weight) raises glucose.
    - Sex nudges iron and HDL (calibration placeholder).
    """
    deltas: dict[str, float] = {}
    age = int(profile.get("age", 35))
    activity = profile.get("activity_level", "moderate")
    height_cm = float(profile.get("height_cm", 170))
    weight_kg = float(profile.get("weight_kg", 70))
    bmi = weight_kg / ((height_cm / 100) ** 2) if height_cm > 0 else 22.0

    deltas["glucose"] = max(0, (age - 50)) * 0.3 + max(0, bmi - 25) * 1.2
    deltas["crp"] = max(0, (age - 50)) * 0.02

    activity_deltas = {
        "sedentary": {"hdl": -6, "crp": +0.6},
        "light": {"hdl": -2, "crp": +0.2},
        "moderate": {"hdl": +0, "crp": +0.0},
        "active": {"hdl": +4, "crp": -0.3},
        "athlete": {"hdl": +8, "crp": -0.5},
    }
    for key, value in activity_deltas.get(activity, {}).items():
        deltas[key] = deltas.get(key, 0.0) + value

    if profile.get("sex") == "male":
        deltas["iron"] = deltas.get("iron", 0.0) + 15
        deltas["hdl"] = deltas.get("hdl", 0.0) + 3
    elif profile.get("sex") == "female":
        deltas["iron"] = deltas.get("iron", 0.0) - 10

    return deltas


def _state_for(value: float, ref_low: float, ref_high: float) -> str:
    """Classify a value against its reference range."""
    if value < ref_low:
        return "low"
    if value > ref_high:
        return "high"
    return "normal"


def _build_biomarker(key: str, value: float) -> dict[str, Any]:
    """Build the public biomarker record with a human-friendly message."""
    unit, ref_low, ref_high = _REFERENCE_RANGES[key]
    state = _state_for(value, ref_low, ref_high)

    friendly_names = {
        "iron": "Iron (Ferritin)",
        "vitamin_d": "Vitamin D (25-OH)",
        "crp": "C-Reactive Protein",
        "glucose": "Fasting Glucose",
        "hdl": "HDL Cholesterol",
    }
    state_messages = {
        "low": f"{friendly_names[key]} is below the reference range. "
        f"Consider reviewing your diet or speaking with a clinician.",
        "normal": f"{friendly_names[key]} is within the reference range. Keep it up!",
        "high": f"{friendly_names[key]} is above the reference range. "
        f"Consider a follow-up conversation with a clinician.",
    }

    return {
        "name": friendly_names[key],
        "value": round(value, 2),
        "unit": unit,
        "ref_low": ref_low,
        "ref_high": ref_high,
        "state": state,
        "message": state_messages[state],
    }


def generate_report(
    profile: dict[str, Any],
    sensor_reading: dict[str, Any],
) -> dict[str, Any]:
    """Generate a deterministic report from a real device reading.

    Args:
        profile: User fields (age, sex, height_cm, weight_kg, activity_level).
        sensor_reading: Raw device snapshot (rgb_r, rgb_g, rgb_b,
            temperature_c, humidity_pct). Required — the report is always
            derived from physical sensor data.

    Returns:
        Dict with ``overall_risk``, ``summary``, ``text_summary`` and
        ``biomarkers``.
    """
    if not sensor_reading:
        raise ValueError("sensor_reading is required to generate a report")

    bases = _sensor_to_bases(sensor_reading)
    deltas = _profile_adjustments(profile)

    biomarkers = []
    for key, (unit, ref_low, ref_high) in _REFERENCE_RANGES.items():
        value = bases[key] + deltas.get(key, 0.0)
        value = max(ref_low * 0.4, min(ref_high * 1.6, value))
        biomarkers.append(_build_biomarker(key, value))

    # Weighted risk score: each out-of-range marker contributes its weight.
    score = 0.0
    for marker in biomarkers:
        if marker["state"] != "normal":
            score += _RISK_WEIGHTS.get(marker["name"], 0.1)

    if score >= 0.45:
        overall_risk = "high"
    elif score >= 0.2:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    out_of_range = [
        f"{m['name']} ({m['state']})" for m in biomarkers if m["state"] != "normal"
    ]
    if out_of_range:
        text_summary = (
            "Analysis based on your latest Doctordrobe device reading. "
            f"Overall risk: {overall_risk.upper()}. "
            f"Attention needed on: {', '.join(out_of_range)}."
        )
    else:
        text_summary = (
            "Analysis based on your latest Doctordrobe device reading. "
            f"Overall risk: {overall_risk.upper()}. "
            "All markers are within their reference ranges. "
            "Continue your healthy routine and check again tomorrow."
        )

    summary = (
        f"Device reading · Overall risk {overall_risk.upper()} · "
        f"{len([m for m in biomarkers if m['state'] != 'normal'])} marker(s) out of range"
    )

    return {
        "overall_risk": overall_risk,
        "summary": summary,
        "text_summary": text_summary,
        "biomarkers": biomarkers,
    }
