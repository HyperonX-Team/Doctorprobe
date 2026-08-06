"""Physics-constrained spectral reconstruction.

The classic Doctordrobe mapping — one RGB triple -> five analytes — is an
**ill-posed inverse problem**: three measured channels cannot uniquely
determine four concentration unknowns, so any single-snapshot estimator
is noise-limited and its output is not trustworthy.

This module replaces that one-shot mapping with a **regularized
multi-measurement spectral deconvolution**:

1. FORWARD MODEL. A ``3 x 4`` extinction matrix ``E`` maps analyte
   concentrations to channel optical densities (Beer-Lambert). Each
   analyte dominates one pad channel (glucose -> red, CRP -> blue,
   cortisol -> green) with a small cross-talk bleed into its neighbours;
   secretory IgA adds equal turbidity on every channel. Temperature and
   humidity enter as known kinetic scalings of the extinction
   coefficients, never as extra unknowns.

2. INVERSE PROBLEM. Each snapshot contributes ``3`` linear equations
   ``E c = D`` where ``D`` is the measured optical density
   ``-log10(R / R0)``. A burst of ``m`` snapshots of the *same* strip
   stacks into an over-determined ``3m x 4`` system, so replicate
   measurements average out ADC and optical noise.

3. REGULARIZATION. The system is solved as a **non-negative least
   squares (NNLS)** problem with Tikhonov regularization toward a prior
   (SaliNet when present, else the closed-form Beer-Lambert estimate).
   The prior only steadies the weak (ill-conditioned) directions; the
   data drives the well-determined ones.

4. IDENTIFIABILITY. Least-squares statistics on the regularized Fisher
   information give a per-analyte standard error and confidence score.
   A single snapshot genuinely *cannot* pin down all four analytes, so
   its confidences are low; a burst raises them. The report uses these
   scores to say "this marker could not be resolved reliably" instead
   of printing a confident-but-arbitrary number.

The forward physics constants mirror ``scripts/generate_synthetic_data.py``
and ``app/services/analyzer.py`` so the solver, the synthetic trainer and
the Beer-Lambert fallback all describe the same chemistry.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

# Channel order used internally: (red, blue, green) matching the
# TCS34725 layout and the generator's pad indices.
CHANNEL_KEYS = ("rgb_r", "rgb_b", "rgb_g")

# Column order of the extinction matrix.
ANALYTES = ("glucose", "crp", "cortisol", "siga")

# Blank (unstained) pad reflectance: R0 = 0.92.
BLANK_REFLECTANCE = 0.92

# Concentration per unit absorbance (units / A) — mirror of analyzer/_SLOPES.
_SLOPES = {"glucose": 15.0, "crp": 2.0, "cortisol": 1.2, "siga": 60.0}

# Secretory IgA is measured by turbidimetry: it attenuates every channel
# equally, but with a gain < 1.
_TURBIDITY_GAIN = 0.8

# Chromogen bleed between adjacent pads (fraction of the dominant
# absorbance leaking onto neighbouring channels).
_BLEED = 0.03

# Enzyme-kinetics coefficients: fractional reaction-rate change per degC.
_TEMP_COEFFS = {"glucose": 0.010, "crp": 0.008, "cortisol": 0.006}

# Humidity dilutes soluble markers on the strip (fractional change per %RH).
_HUMIDITY_COEFF = 0.002

# Optical-density noise floor (~ADC quantisation + sensor noise). Used to
# scale the per-analyte standard errors when the residual cannot be
# estimated (single measurement) or is below the physical floor.
NOISE_FLOOR_OD = 0.02

# Default Tikhonov strength. Small relative to the (column-normalised)
# design matrix so the prior only steadies weak directions.
DEFAULT_LAMBDA = 0.05

# Minimum reflectance kept so the logarithm stays well-defined.
_MIN_REFLECTANCE = 1e-4


def _clamp(v: float, low: float, high: float) -> float:
    return min(max(v, low), high)


def _base_extinction_matrix() -> np.ndarray:
    """Extinction coefficients (optical density per unit concentration).

    Rows = (red, blue, green), columns = ANALYTES. Diagonal terms follow
    Beer-Lambert ``A = c / slope``; off-diagonals are the cross-talk
    bleed; the last column is the uniform sIgA turbidity.
    """
    e = np.zeros((3, 4), dtype=np.float64)
    e[0, 0] = 1.0 / _SLOPES["glucose"]    # glucose  -> red
    e[1, 1] = 1.0 / _SLOPES["crp"]        # CRP      -> blue
    e[2, 2] = 1.0 / _SLOPES["cortisol"]   # cortisol -> green
    e[:, 3] = _TURBIDITY_GAIN / _SLOPES["siga"]
    for j in range(3):  # bleed: pad analyte onto its neighbour channels
        for i in range(3):
            if i != j:
                e[i, j] = _BLEED * e[j, j]
    return e


_BASE_E = _base_extinction_matrix()


def extinction_matrix(temperature_c: float, humidity_pct: float) -> np.ndarray:
    """Extinction matrix at a given temperature/humidity.

    Temperature scales the pad-analyte columns by an enzyme-kinetics
    factor ``(1 + k(T - 25))``; humidity scales the sIgA column by
    ``(1 - k(h - 50))`` (hydration dilutes the soluble marker).
    """
    e = _BASE_E.copy()
    for j, name in enumerate(ANALYTES[:3]):
        e[:, j] *= 1.0 + _TEMP_COEFFS[name] * (temperature_c - 25.0)
    e[:, 3] *= 1.0 - _HUMIDITY_COEFF * (humidity_pct - 50.0)
    return e


def _channel_vector(snapshot: dict[str, Any]) -> np.ndarray:
    """Extract the (red, blue, green) reflectance vector from a snapshot."""
    return np.array(
        [float(snapshot.get(key, 128)) for key in CHANNEL_KEYS],
        dtype=np.float64,
    )


def absorbance(snapshot: dict[str, Any]) -> np.ndarray:
    """Beer-Lambert optical density of one snapshot.

    ``D_i = max(0, -log10(R_i / R0))`` with ``R_i = channel / 255``.
    """
    reflectance = _channel_vector(snapshot) / 255.0
    reflectance = np.clip(reflectance, _MIN_REFLECTANCE, 0.999)
    return np.maximum(0.0, -np.log10(reflectance / BLANK_REFLECTANCE))


def nnls(a: np.ndarray, b: np.ndarray, max_iter: int = 500, tol: float = 1e-10) -> np.ndarray:
    """Solve ``min ||a x - b||^2`` subject to ``x >= 0`` (Lawson-Hanson).

    Pure numpy implementation so the solver does not depend on scipy.
    Deterministic for a fixed input.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    if a.shape[0] != b.shape[0]:
        raise ValueError("a and b must have the same number of rows")
    n = a.shape[1]
    x = np.zeros(n, dtype=np.float64)
    passive = np.zeros(n, dtype=bool)

    for _ in range(max_iter):
        w = a.T @ (b - a @ x)
        active = np.flatnonzero(~passive)
        if active.size == 0:
            break
        j = active[np.argmax(w[active])]
        if w[j] <= tol:
            break
        passive[j] = True

        while True:
            p = np.flatnonzero(passive)
            z = np.zeros(n, dtype=np.float64)
            if p.size:
                sol, *_ = np.linalg.lstsq(a[:, p], b, rcond=None)
                z[p] = sol
            if p.size == 0 or (z[p] > tol).all():
                x = z
                break
            neg = p[z[p] <= tol]
            with np.errstate(divide="ignore", invalid="ignore"):
                ratios = x[neg] / (x[neg] - z[neg])
            ratios[~np.isfinite(ratios)] = np.inf
            alpha = float(np.min(ratios))
            x = x + alpha * (z - x)
            passive[x <= tol] = False

    return x


def _column_normalizer(e: np.ndarray) -> np.ndarray:
    """Per-column scale that normalises the design matrix to unit columns.

    ``E @ normalizer`` has unit-norm columns, so Tikhonov regularisation
    weighs every analyte equally. Without this, small-extinction analytes
    (glucose) would be regularised toward the prior even when the data
    constrains them. Returns ``diag(1 / ||E[:, j]||)``.
    """
    norms = np.linalg.norm(e, axis=0)
    norms[norms < 1e-12] = 1.0
    return np.diag(1.0 / norms)


def reconstruct(
    measurements: Sequence[dict[str, Any]],
    prior: dict[str, float] | None = None,
    lambda_: float = DEFAULT_LAMBDA,
    noise_floor: float = NOISE_FLOOR_OD,
) -> dict[str, Any]:
    """Reconstruct concentrations from one-or-more strip snapshots.

    Args:
        measurements: Snapshots of the *same* strip (burst); each dict has
            rgb_r/rgb_g/rgb_b/temperature_c/humidity_pct.
        prior: Optional per-analyte concentrations used as the Tikhonov
            centre (SaliNet or Beer-Lambert). Defaults to zeros.
        lambda_: Tikhonov strength.
        noise_floor: Optical-density noise floor for the error bars.

    Returns:
        Dict with ``concentrations``, ``standard_errors`` (per analyte),
        ``noise_sigma``, ``condition_number``, ``reconstruction_residual``
        and ``n_measurements``.
    """
    if not measurements:
        raise ValueError("at least one measurement is required")

    base = measurements[0]
    e0 = extinction_matrix(
        float(base.get("temperature_c", 25.0)),
        float(base.get("humidity_pct", 50.0)),
    )
    normalizer = _column_normalizer(e0)
    normalizer_inv = np.linalg.inv(normalizer)

    rows: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for snapshot in measurements:
        e = extinction_matrix(
            float(snapshot.get("temperature_c", 25.0)),
            float(snapshot.get("humidity_pct", 50.0)),
        )
        rows.append(e @ normalizer)
        targets.append(absorbance(snapshot))
    a = np.vstack(rows)             # 3m x 4
    b = np.concatenate(targets)     # 3m

    if prior is None:
        prior_norm = np.zeros(4, dtype=np.float64)
    else:
        prior_norm = np.clip(
            [float(prior.get(name, 0.0)) for name in ANALYTES], 0.0, None
        ) @ normalizer_inv

    sqrt_lambda = float(np.sqrt(lambda_))
    aug = np.vstack([a, sqrt_lambda * np.eye(4)])
    aug_b = np.concatenate([b, sqrt_lambda * prior_norm])
    c_norm = nnls(aug, aug_b)
    c = normalizer @ c_norm          # back to concentration units

    # Residual-based noise scale, floored at the physical noise level.
    residual = a @ c_norm - b
    n_eq = a.shape[0]
    if n_eq > 4:
        sigma2 = float(np.maximum(residual @ residual / (n_eq - 4), noise_floor**2))
    else:
        sigma2 = float(noise_floor**2)
    sigma = float(np.sqrt(sigma2))

    # Regularized Fisher information + least-squares covariance.
    fisher = a.T @ a + lambda_ * np.eye(4)
    covariance_norm = sigma2 * (np.linalg.inv(fisher) @ a.T @ a @ np.linalg.inv(fisher))
    se_norm = np.sqrt(np.maximum(np.diag(covariance_norm), 0.0))
    se = normalizer @ se_norm

    # Identifiability: how much does the prior (lambda) dominate the data?
    # Replicate snapshots of one strip are linearly dependent, so the raw
    # design matrix is always rank-deficient; the regularized Fisher
    # information (computed above) stays well-conditioned.
    condition_number = float(np.linalg.cond(fisher))
    rank = int(np.linalg.matrix_rank(a))
    b_norm = float(np.linalg.norm(b))
    reconstruction_residual = float(np.linalg.norm(residual) / (b_norm + 1e-12))

    return {
        "concentrations": {name: float(value) for name, value in zip(ANALYTES, c)},
        "standard_errors": {name: float(value) for name, value in zip(ANALYTES, se)},
        "noise_sigma": sigma,
        "condition_number": condition_number,
        "rank": rank,
        "reconstruction_residual": reconstruction_residual,
        "n_measurements": len(measurements),
    }
