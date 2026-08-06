"""Spectral reconstruction tests: NNLS solver, forward/inverse physics,
multi-measurement redundancy, regularization prior, identifiability."""

import numpy as np
import pytest

from app.services import spectral


def _snapshot_from_absorbance(
    d: np.ndarray,
    temperature_c: float = 26.0,
    humidity_pct: float = 45.0,
) -> dict:
    """Forward model: optical densities -> normalized 0..255 channels."""
    reflectance = spectral.BLANK_REFLECTANCE * 10 ** (-np.asarray(d, dtype=float))
    rgb = np.clip(np.round(reflectance * 255), 0, 255).astype(int)
    return {
        "rgb_r": int(rgb[0]),
        "rgb_b": int(rgb[1]),
        "rgb_g": int(rgb[2]),
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
    }


def _truth() -> dict[str, float]:
    return {"glucose": 2.5, "crp": 0.4, "cortisol": 0.3, "siga": 12.0}


def test_nnls_matches_scipy():
    """Our numpy Lawson-Hanson NNLS agrees with scipy's reference solver."""
    scipy_opt = pytest.importorskip("scipy.optimize")
    rng = np.random.default_rng(7)
    for _ in range(25):
        a = rng.normal(size=(9, 4))
        b = rng.normal(size=9)
        x_ours = spectral.nnls(a, b)
        x_ref, _ = scipy_opt.nnls(a, b)
        assert np.allclose(x_ours, x_ref, atol=1e-8)


def test_nnls_is_nonnegative_and_vanilla_case():
    """NNLS output is non-negative and fits an exactly-representable system."""
    a = np.array([[2.0, 1.0], [1.0, 2.0]])
    b = np.array([4.0, 5.0])  # exact non-negative solution x=[1, 2]
    x = spectral.nnls(a, b)
    assert (x >= 0).all()
    assert np.allclose(a @ x, b, atol=1e-10)


def test_reconstruct_requires_measurements():
    with pytest.raises(ValueError):
        spectral.reconstruct([])


def test_reconstruct_recovers_truth_with_replicates():
    """Multiple clean replicates of one strip invert to the true cocktail."""
    truth = _truth()
    e = spectral.extinction_matrix(26.0, 45.0)
    d = e @ [truth[k] for k in spectral.ANALYTES]
    rng = np.random.default_rng(3)
    measurements = [
        _snapshot_from_absorbance(d + rng.normal(0.0, 0.001, size=3)) for _ in range(4)
    ]
    rec = spectral.reconstruct(measurements)
    for name in spectral.ANALYTES:
        # Integer channel quantisation (~0.5/255) blurs the weakest
        # channel (glucose), so a 12% tolerance still proves the
        # deconvolution inverts the physics rather than a lookup table.
        assert rec["concentrations"][name] == pytest.approx(truth[name], rel=0.12)
    assert all(value >= 0.0 for value in rec["concentrations"].values())


def test_reconstruction_is_deterministic():
    """Same input, same output — no randomness anywhere."""
    truth = _truth()
    e = spectral.extinction_matrix(26.0, 45.0)
    d = e @ [truth[k] for k in spectral.ANALYTES]
    measurements = [_snapshot_from_absorbance(d) for _ in range(3)]
    assert spectral.reconstruct(measurements) == spectral.reconstruct(measurements)


def test_replicate_measurements_shrink_error_bars():
    """More snapshots of the same strip -> smaller standard errors."""
    truth = _truth()
    e = spectral.extinction_matrix(26.0, 45.0)
    d = e @ [truth[k] for k in spectral.ANALYTES]
    rng = np.random.default_rng(11)
    noisy = [_snapshot_from_absorbance(d + rng.normal(0.0, 0.02, size=3)) for _ in range(5)]

    single = spectral.reconstruct([noisy[0]], prior=truth)
    burst = spectral.reconstruct(noisy, prior=truth)

    for name in spectral.ANALYTES:
        assert burst["standard_errors"][name] < single["standard_errors"][name]
    assert burst["n_measurements"] == 5


def test_prior_steers_underdetermined_single_measurement():
    """With one snapshot (3 eq, 4 unknowns) the prior decides the weak axis."""
    truth = _truth()
    e = spectral.extinction_matrix(26.0, 45.0)
    d = e @ [truth[k] for k in spectral.ANALYTES]
    measurement = _snapshot_from_absorbance(d)

    zero_prior = spectral.reconstruct([measurement], prior=None)
    high_siga_prior = spectral.reconstruct(
        [measurement], prior={"glucose": 0, "crp": 0, "cortisol": 0, "siga": 40.0}
    )

    assert zero_prior["concentrations"]["siga"] < high_siga_prior["concentrations"]["siga"]
    # The well-determined analytes are barely moved by the prior.
    for name in ("crp", "cortisol"):
        assert abs(
            zero_prior["concentrations"][name]
            - high_siga_prior["concentrations"][name]
        ) < 1.0


def test_temperature_scales_extinction_columns():
    """Hotter reaction -> higher effective extinction for pad analytes."""
    cold = spectral.extinction_matrix(15.0, 50.0)
    hot = spectral.extinction_matrix(40.0, 50.0)
    for j, name in enumerate(spectral.ANALYTES[:3]):
        assert (hot[:, j] > cold[:, j]).all()
    # sIgA turbidity is temperature-independent; humidity scaling applies.
    assert np.allclose(hot[:, 3], cold[:, 3])
    humid = spectral.extinction_matrix(26.0, 90.0)
    assert (humid[:, 3] < cold[:, 3]).all()


def test_absorbance_is_beer_lambert():
    """A blank pad reads zero optical density; dark pads absorb."""
    blank = {"rgb_r": 255, "rgb_g": 255, "rgb_b": 255}
    dark = {"rgb_r": 30, "rgb_g": 30, "rgb_b": 30}
    assert np.allclose(spectral.absorbance(blank), 0.0, atol=1e-9)
    assert (spectral.absorbance(dark) > 0.0).all()
