"""Analyzer unit tests: deterministic sensor-to-report mapping."""

from app.services import analyzer
from app.utils.map_range import map_range

PROFILE = {
    "age": 34,
    "sex": "female",
    "height_cm": 165.0,
    "weight_kg": 62.0,
    "activity_level": "moderate",
}

SENSOR = {
    "rgb_r": 120,
    "rgb_g": 200,
    "rgb_b": 60,
    "temperature_c": 24.5,
    "humidity_pct": 45.0,
}


def test_map_range_basic_and_clamped():
    """Linear mapping plus clamping at both ends."""
    assert map_range(0, 0, 255, 20, 300) == 20
    assert map_range(255, 0, 255, 20, 300) == 300
    assert map_range(127.5, 0, 255, 20, 300) == 160
    assert map_range(500, 0, 255, 20, 300) == 300  # clamped high
    assert map_range(-50, 0, 255, 20, 300) == 20  # clamped low
    assert map_range(42, 0, 0, 10, 20) == 10  # degenerate input range


def test_generate_report_requires_reading():
    """A report cannot be generated without a device reading."""
    try:
        analyzer.generate_report(PROFILE, {})
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty sensor_reading")


def test_report_is_deterministic_for_same_reading():
    """Same reading + same profile always yields the identical report."""
    report_a = analyzer.generate_report(PROFILE, SENSOR)
    report_b = analyzer.generate_report(PROFILE, SENSOR)

    assert report_a == report_b
    assert report_a["overall_risk"] in {"low", "medium", "high"}
    assert report_a["summary"]
    assert report_a["text_summary"]
    assert len(report_a["biomarkers"]) >= 3


def test_sensor_reading_changes_base_values():
    """Extreme sensor inputs push biomarker values apart (no randomness)."""
    dark = {
        "rgb_r": 0,
        "rgb_g": 0,
        "rgb_b": 0,
        "temperature_c": 15.0,
        "humidity_pct": 20.0,
    }
    bright = {
        "rgb_r": 255,
        "rgb_g": 255,
        "rgb_b": 255,
        "temperature_c": 40.0,
        "humidity_pct": 90.0,
    }

    dark_report = analyzer.generate_report(PROFILE, dark)
    bright_report = analyzer.generate_report(PROFILE, bright)

    values_dark = {m["name"]: m["value"] for m in dark_report["biomarkers"]}
    values_bright = {m["name"]: m["value"] for m in bright_report["biomarkers"]}

    # Iron rises with red channel; glucose rises with temperature.
    assert values_bright["Iron (Ferritin)"] > values_dark["Iron (Ferritin)"]
    assert values_bright["Fasting Glucose"] > values_dark["Fasting Glucose"]
    # CRP rises with blue channel.
    assert values_bright["C-Reactive Protein"] > values_dark["C-Reactive Protein"]


def test_profile_adjustments_apply():
    """Different profiles shift the same reading deterministically."""
    athlete = {**PROFILE, "activity_level": "athlete"}
    sedentary = {**PROFILE, "activity_level": "sedentary"}

    athlete_report = analyzer.generate_report(athlete, SENSOR)
    sedentary_report = analyzer.generate_report(sedentary, SENSOR)

    values_athlete = {m["name"]: m["value"] for m in athlete_report["biomarkers"]}
    values_sedentary = {
        m["name"]: m["value"] for m in sedentary_report["biomarkers"]
    }

    # Higher activity raises HDL and lowers CRP.
    assert values_athlete["HDL Cholesterol"] > values_sedentary["HDL Cholesterol"]
    assert (
        values_athlete["C-Reactive Protein"]
        < values_sedentary["C-Reactive Protein"]
    )


def test_sex_adjustment_on_iron():
    """Male/female profiles nudge iron deterministically."""
    male = {**PROFILE, "sex": "male"}
    female = {**PROFILE, "sex": "female"}

    male_report = analyzer.generate_report(male, SENSOR)
    female_report = analyzer.generate_report(female, SENSOR)

    male_iron = next(
        m["value"] for m in male_report["biomarkers"] if m["name"] == "Iron (Ferritin)"
    )
    female_iron = next(
        m["value"]
        for m in female_report["biomarkers"]
        if m["name"] == "Iron (Ferritin)"
    )
    assert male_iron > female_iron


def test_biomarkers_have_valid_states_and_ranges():
    """Every biomarker carries reference bounds and a matching state."""
    report = analyzer.generate_report(PROFILE, SENSOR)
    for marker in report["biomarkers"]:
        assert marker["state"] in {"low", "normal", "high"}
        assert marker["ref_low"] < marker["ref_high"]
        assert marker["message"]
