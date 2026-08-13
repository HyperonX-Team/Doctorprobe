"""Calibration endpoint tests: labeled samples, CSV export, clearing."""

import csv
import io

import pytest


def _sample_payload(**overrides):
    payload = {
        "device_id": "doctordrobe_demo_001",
        "analyte": "glucose",
        "concentration": 3.5,
        "rgb_r": 90,
        "rgb_g": 150,
        "rgb_b": 200,
        "temperature_c": 24.5,
        "humidity_pct": 45.0,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_calibration_sample(client):
    """POST /api/calibration/samples stores a labeled capture."""
    response = await client.post(
        "/api/calibration/samples", json=_sample_payload()
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["analyte"] == "glucose"
    assert body["concentration"] == 3.5
    assert body["rgb_r"] == 90


@pytest.mark.asyncio
async def test_calibration_sample_validation(client):
    """Bad analyte and out-of-envelope concentrations are rejected."""
    response = await client.post(
        "/api/calibration/samples", json=_sample_payload(analyte="ferritin")
    )
    assert response.status_code == 422

    # Glucose envelope is 0.05..50 mg/dL.
    response = await client.post(
        "/api/calibration/samples", json=_sample_payload(concentration=500.0)
    )
    assert response.status_code == 422
    assert "between" in response.json()["detail"]


@pytest.mark.asyncio
async def test_calibration_export_csv(client):
    """GET /api/calibration/export returns trainer-format CSV."""
    response = await client.get("/api/calibration/export")
    assert response.status_code == 404  # nothing recorded yet

    await client.post(
        "/api/calibration/samples", json=_sample_payload(analyte="glucose")
    )
    await client.post(
        "/api/calibration/samples", json=_sample_payload(analyte="cortisol")
    )

    response = await client.get("/api/calibration/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 2
    glucose_row = next(r for r in rows if r["glucose"])
    assert float(glucose_row["glucose"]) == 3.5
    assert glucose_row["rgb_r"] == "90"
    # The other target column for the same row is empty (per-analyte).
    assert glucose_row["cortisol"] == ""

    cortisol_row = next(r for r in rows if r["cortisol"])
    assert float(cortisol_row["cortisol"]) == 3.5
    assert cortisol_row["glucose"] == ""


@pytest.mark.asyncio
async def test_calibration_stats_empty(client):
    """No samples: every analyte shows zero count, not enough, no coverage."""
    response = await client.get("/api/calibration/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_samples"] == 0
    assert body["min_real_samples"] == 15
    assert set(body["analytes"]) == {"glucose", "crp", "cortisol", "siga"}
    for analyte in body["analytes"].values():
        assert analyte["count"] == 0
        assert analyte["enough"] is False
        assert analyte["min_concentration"] is None
    # The shipped SaliNet artifact is present in the repo.
    assert body["model"]["present"] is True
    assert body["model"]["model_version"]


@pytest.mark.asyncio
async def test_calibration_stats_tracks_coverage(client):
    """Counts and concentration spans accumulate per analyte."""
    for _ in range(4):
        await client.post(
            "/api/calibration/samples", json=_sample_payload(analyte="glucose")
        )
    await client.post(
        "/api/calibration/samples",
        json=_sample_payload(analyte="glucose", concentration=1.0),
    )

    response = await client.get("/api/calibration/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_samples"] == 5
    glucose = body["analytes"]["glucose"]
    assert glucose["count"] == 5
    assert glucose["min_concentration"] == 1.0
    assert glucose["max_concentration"] == 3.5
    assert glucose["enough"] is False  # 5 < 15
    assert body["analytes"]["crp"]["count"] == 0


@pytest.mark.asyncio
async def test_calibration_stats_meets_threshold(client):
    """At 15 samples an analyte flips to enough=True."""
    for _ in range(15):
        await client.post(
            "/api/calibration/samples", json=_sample_payload(analyte="siga")
        )

    response = await client.get("/api/calibration/stats")
    body = response.json()
    assert body["analytes"]["siga"]["enough"] is True
    assert body["total_samples"] == 15


@pytest.mark.asyncio
async def test_calibration_list_and_clear(client):
    """Samples can be listed per analyte and cleared."""
    await client.post(
        "/api/calibration/samples", json=_sample_payload(analyte="glucose")
    )
    await client.post(
        "/api/calibration/samples", json=_sample_payload(analyte="crp")
    )

    response = await client.get("/api/calibration/samples")
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = await client.get("/api/calibration/samples?analyte=crp")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["analyte"] == "crp"

    response = await client.delete("/api/calibration/samples")
    assert response.status_code == 200
    assert response.json() == {"detail": "Calibration samples cleared"}

    response = await client.get("/api/calibration/samples")
    assert response.json() == []
