"""Analyzer unit tests: deterministic Beer-Lambert sensor-to-report mapping."""

import pytest

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
    with pytest.raises(ValueError):
        analyzer.generate_report(PROFILE, {})


def test_report_is_deterministic_for_same_reading():
    """Same reading + same profile always yields the identical report."""
    report_a = analyzer.generate_report(PROFILE, SENSOR)
    report_b = analyzer.generate_report(PROFILE, SENSOR)

    assert report_a == report_b
    assert report_a["overall_risk"] in {"low", "medium", "high"}
    assert report_a["summary"]
    assert report_a["text_summary"]
    assert len(report_a["biomarkers"]) >= 4


def test_panel_is_saliva_plausible():
    """The panel contains saliva-valid analytes with sane units."""
    report = analyzer.generate_report(PROFILE, SENSOR)
    names = {m["name"] for m in report["biomarkers"]}

    assert "Salivary Glucose" in names
    assert "Salivary CRP" in names
    assert "Salivary Cortisol" in names
    assert "Salivary pH" in names
    assert "Secretory IgA" in names

    glucose = next(m for m in report["biomarkers"] if m["name"] == "Salivary Glucose")
    assert glucose["unit"] == "mg/dL"
    assert glucose["ref_high"] <= 7.0  # saliva scale, not serum


def test_darker_pad_means_higher_concentration():
    """Beer-Lambert: chromogen development darkens the pad, raising the
    measured concentration (blank pad -> near-zero concentration)."""
    blank = {
        "rgb_r": 255,
        "rgb_g": 255,
        "rgb_b": 255,
        "temperature_c": 25.0,
        "humidity_pct": 50.0,
    }
    developed = {
        "rgb_r": 30,
        "rgb_g": 30,
        "rgb_b": 30,
        "temperature_c": 25.0,
        "humidity_pct": 50.0,
    }

    blank_report = analyzer.generate_report(PROFILE, blank)
    developed_report = analyzer.generate_report(PROFILE, developed)

    values_blank = {m["name"]: m["value"] for m in blank_report["biomarkers"]}
    values_dev = {m["name"]: m["value"] for m in developed_report["biomarkers"]}

    assert values_dev["Salivary Glucose"] > values_blank["Salivary Glucose"]
    assert values_dev["Salivary CRP"] > values_blank["Salivary CRP"]
    assert values_dev["Salivary Cortisol"] > values_blank["Salivary Cortisol"]
    assert values_dev["Secretory IgA"] > values_blank["Secretory IgA"]


def test_ph_tracks_indicator_ratio():
    """Blue-dominant colouring reads alkaline, green-dominant acidic."""
    blue_dominant = {
        "rgb_r": 128,
        "rgb_g": 60,
        "rgb_b": 220,
        "temperature_c": 25.0,
        "humidity_pct": 50.0,
    }
    green_dominant = {
        "rgb_r": 128,
        "rgb_g": 220,
        "rgb_b": 60,
        "temperature_c": 25.0,
        "humidity_pct": 50.0,
    }

    alkaline = analyzer.generate_report(PROFILE, blue_dominant)
    acidic = analyzer.generate_report(PROFILE, green_dominant)

    ph_alkaline = next(
        m["value"] for m in alkaline["biomarkers"] if m["name"] == "Salivary pH"
    )
    ph_acidic = next(
        m["value"] for m in acidic["biomarkers"] if m["name"] == "Salivary pH"
    )
    assert ph_alkaline > 7.4  # high / alkaline
    assert ph_acidic < 6.5  # low / acidic


def test_profile_adjustments_apply():
    """Profile physiology shifts the same reading deterministically."""
    athlete = {**PROFILE, "activity_level": "athlete"}
    sedentary = {**PROFILE, "activity_level": "sedentary"}

    athlete_report = analyzer.generate_report(athlete, SENSOR)
    sedentary_report = analyzer.generate_report(sedentary, SENSOR)

    siga_athlete = next(
        m["value"] for m in athlete_report["biomarkers"] if m["name"] == "Secretory IgA"
    )
    siga_sedentary = next(
        m["value"]
        for m in sedentary_report["biomarkers"]
        if m["name"] == "Secretory IgA"
    )
    assert siga_athlete > siga_sedentary

    # Higher BMI raises salivary glucose.
    high_bmi = {**PROFILE, "weight_kg": 95.0}  # BMI ~34.9 vs ~22.8
    low_bmi = {**PROFILE, "weight_kg": 62.0}

    glucose_high_bmi = next(
        m["value"]
        for m in analyzer.generate_report(high_bmi, SENSOR)["biomarkers"]
        if m["name"] == "Salivary Glucose"
    )
    glucose_low_bmi = next(
        m["value"]
        for m in analyzer.generate_report(low_bmi, SENSOR)["biomarkers"]
        if m["name"] == "Salivary Glucose"
    )
    assert glucose_high_bmi > glucose_low_bmi


def test_biomarkers_have_valid_states_and_ranges():
    """Every biomarker carries reference bounds and a matching state."""
    report = analyzer.generate_report(PROFILE, SENSOR)
    for marker in report["biomarkers"]:
        assert marker["state"] in {"low", "normal", "high"}
        assert marker["ref_low"] < marker["ref_high"]
        assert marker["message"]


def test_salinet_model_is_loaded():
    """The committed SaliNet artifact is found and loads."""
    loaded = analyzer._get_model()
    assert loaded is not None
    manifest = loaded["manifest"]
    assert manifest["model_name"] == "SaliNet"
    assert manifest["features"] == [
        "rgb_r",
        "rgb_g",
        "rgb_b",
        "temperature_c",
        "humidity_pct",
    ]
    assert set(manifest["targets"]) == {"glucose", "crp", "cortisol", "siga"}


def test_salinet_predictions_are_plausible():
    """Model outputs stay inside the calibration envelope across a sweep."""
    import math

    for r in (0, 64, 128, 192, 255):
        for g in (0, 128, 255):
            reading = {
                "rgb_r": r,
                "rgb_g": g,
                "rgb_b": 128,
                "temperature_c": 25.0,
                "humidity_pct": 50.0,
            }
            report = analyzer.generate_report(PROFILE, reading)
            for marker in report["biomarkers"]:
                if marker["name"] == "Salivary pH":
                    continue  # ratio formula, clamped to [5.0, 8.5]
                ref_low = marker["ref_low"]
                ref_high = marker["ref_high"]
                assert math.isfinite(marker["value"])
                assert ref_low * 0.4 <= marker["value"] <= ref_high * 1.6


def test_beer_lambert_fallback_without_model(monkeypatch):
    """Without the SaliNet artifact the closed-form chemistry still works."""
    monkeypatch.setattr(analyzer, "_get_model", lambda: None)
    report = analyzer.generate_report(PROFILE, SENSOR)
    assert report["overall_risk"] in {"low", "medium", "high"}
    assert len(report["biomarkers"]) >= 4
    glucose = next(
        m for m in report["biomarkers"] if m["name"] == "Salivary Glucose"
    )
    assert 0.0 < glucose["value"]
