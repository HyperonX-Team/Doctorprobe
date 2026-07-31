"""Simulator unit tests: determinism, sensor influence, and mapping."""

from datetime import date

from app.services import simulator
from app.utils.map_range import map_range

PROFILE = {
    "age": 34,
    "sex": "female",
    "height_cm": 165.0,
    "weight_kg": 62.0,
    "activity_level": "moderate",
}

USER_KEY = "11111111-2222-3333-4444-555555555555"
DAY = date(2026, 7, 31)


def test_map_range_basic_and_clamped():
    """Linear mapping plus clamping at both ends."""
    assert map_range(0, 0, 255, 20, 300) == 20
    assert map_range(255, 0, 255, 20, 300) == 300
    assert map_range(127.5, 0, 255, 20, 300) == 160
    assert map_range(500, 0, 255, 20, 300) == 300  # clamped high
    assert map_range(-50, 0, 255, 20, 300) == 20  # clamped low
    assert map_range(42, 0, 0, 10, 20) == 10  # degenerate input range


def test_generate_report_deterministic_for_same_user_and_day():
    """Same user + same day yields an identical report."""
    report_a = simulator.generate_report(PROFILE, user_key=USER_KEY, today=DAY)
    report_b = simulator.generate_report(PROFILE, user_key=USER_KEY, today=DAY)

    assert report_a == report_b
    assert report_a["overall_risk"] in {"low", "medium", "high"}
    assert report_a["summary"]
    assert report_a["text_summary"]
    assert len(report_a["biomarkers"]) >= 3


def test_generate_report_varies_by_user():
    """Different users get different (but valid) reports."""
    report_a = simulator.generate_report(PROFILE, user_key=USER_KEY, today=DAY)
    report_b = simulator.generate_report(
        PROFILE, user_key="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", today=DAY
    )

    assert report_a["biomarkers"] != report_b["biomarkers"]
    states_a = {m["name"]: m["state"] for m in report_a["biomarkers"]}
    states_b = {m["name"]: m["state"] for m in report_b["biomarkers"]}
    assert set(states_a.keys()) == set(states_b.keys())


def test_sensor_reading_changes_base_values():
    """Extreme sensor inputs push biomarker values apart (same seed)."""
    dark_reading = {
        "rgb_r": 0,
        "rgb_g": 0,
        "rgb_b": 0,
        "temperature_c": 15.0,
        "humidity_pct": 20.0,
    }
    bright_reading = {
        "rgb_r": 255,
        "rgb_g": 255,
        "rgb_b": 255,
        "temperature_c": 40.0,
        "humidity_pct": 90.0,
    }

    dark = simulator.generate_report(
        PROFILE, sensor_reading=dark_reading, user_key=USER_KEY, today=DAY
    )
    bright = simulator.generate_report(
        PROFILE, sensor_reading=bright_reading, user_key=USER_KEY, today=DAY
    )

    values_dark = {m["name"]: m["value"] for m in dark["biomarkers"]}
    values_bright = {m["name"]: m["value"] for m in bright["biomarkers"]}

    # Iron rises with red channel; glucose rises with temperature.
    assert values_bright["Iron (Ferritin)"] > values_dark["Iron (Ferritin)"]
    assert values_bright["Fasting Glucose"] > values_dark["Fasting Glucose"]
    # CRP rises with blue channel.
    assert values_bright["C-Reactive Protein"] > values_dark["C-Reactive Protein"]


def test_sensor_reading_is_fully_deterministic():
    """The same reading produces the same report on the same day."""
    reading = {
        "rgb_r": 90,
        "rgb_g": 140,
        "rgb_b": 210,
        "temperature_c": 26.0,
        "humidity_pct": 55.0,
    }
    report_a = simulator.generate_report(
        PROFILE, sensor_reading=reading, user_key=USER_KEY, today=DAY
    )
    report_b = simulator.generate_report(
        PROFILE, sensor_reading=reading, user_key=USER_KEY, today=DAY
    )
    assert report_a == report_b


def test_biomarkers_have_valid_states_and_ranges():
    """Every biomarker carries reference bounds and a matching state."""
    report = simulator.generate_report(PROFILE, user_key=USER_KEY, today=DAY)
    for marker in report["biomarkers"]:
        assert marker["state"] in {"low", "normal", "high"}
        assert marker["ref_low"] < marker["ref_high"]
        assert marker["message"]
