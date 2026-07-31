"""Generate synthetic spectral calibration data for the sensor model.

This script simulates the physics of colorimetric saliva strips so a
small ML model can be trained to invert the chemistry — i.e. learn
"RGB + temperature + humidity -> analyte concentration" the way a real
calibration dataset would teach it.

The forward model, step by step:

1. GROUND TRUTH. Each analyte concentration is drawn from a plausible
   biological distribution (log-normal: most people are near the centre
   of the range, a few are outliers). Units and reference ranges are
   documented in app/services/analyzer.py.

2. BEER-LAMBERT. The reagent pad develops a chromogen whose absorbance
   is proportional to concentration:  A = c / slope.
   Reflectance follows the Beer-Lambert law:  R = R0 * 10^(-A),
   i.e. more analyte -> more colour -> darker pad (R falls).

3. KINETICS. The reaction rate (and therefore colour yield) rises with
   temperature, so concentration is corrected by (1 + k*(T - 25 degC)).

4. PADS. Each pad maps to a channel: glucose -> red pad, cortisol ->
   green pad, CRP -> blue pad. Secretory IgA is measured by turbidity:
   protein clouds the sample and attenuates all channels equally.

5. OPTICS. The three channel signals are mixed by a cross-talk matrix
   (chromogen bleed between adjacent pads). Gaussian sensor noise is
   added, then the channels are quantised to 0..255 like the TCS34725
   ADC. Lighting is deliberately NOT modelled: the firmware normalises
   every channel against the sensor's clear channel, which removes
   illumination variation before the reading ever reaches the model.

The trained model must therefore learn the INVERSE of steps 5..1.

Output: data/sensor_training.csv (ground truth + features), used by
train_model.py.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

# ------------------------------------------------------------------
# Biology: per-analyte calibration and distributions
# ------------------------------------------------------------------

# concentration per unit absorbance (units / A)
SLOPES = {"glucose": 15.0, "crp": 2.0, "cortisol": 1.2, "siga": 60.0}

# (log-mean, log-sigma, min, max) of the biological distributions
DISTRIBUTIONS = {
    "glucose": (math.log(2.5), 0.45, 0.2, 12.0),   # mg/dL
    "crp": (math.log(0.35), 0.70, 0.01, 4.0),      # ng/mL
    "cortisol": (math.log(0.30), 0.50, 0.02, 1.2), # ug/dL
    "siga": (math.log(12.0), 0.35, 2.0, 40.0),     # mg/dL
}

# temperature coefficient (fractional reaction-rate change per degC)
TEMP_COEFFS = {"glucose": 0.010, "crp": 0.008, "cortisol": 0.006}

# pad -> (channel index, pad efficiency)
PADS = {"glucose": (0, 0.95), "cortisol": (2, 0.90), "crp": (1, 0.90)}
# channels: 0 = red, 1 = blue, 2 = green (TCS34725 layout)

# humidity dilutes soluble markers on the strip (fractional change per %RH)
HUMIDITY_COEFF = 0.002

BLANK_REFLECTANCE = 0.92      # unstained pad
TURBIDITY_GAIN = 0.8          # sIgA absorbance -> channel attenuation
NOISE_SIGMA = 4.0             # ADC noise (out of 255)
CROSS_TALK = (
    (0.94, 0.03, 0.03),
    (0.03, 0.94, 0.03),
    (0.03, 0.03, 0.94),
)

N_SAMPLES = 20_000
SEED = 42

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sensor_training.csv"


def forward_model(rng: random.Random) -> dict:
    """Simulate one strip reading. Returns features and ground truth."""
    temperature = rng.uniform(15.0, 40.0)
    humidity = rng.uniform(20.0, 90.0)

    concentrations = {}
    for analyte, (mu, sigma, lo, hi) in DISTRIBUTIONS.items():
        concentrations[analyte] = min(max(rng.lognormvariate(mu, sigma), lo), hi)

    # Channel intensities from concentration (steps 2-4).
    channel_intensity = [0.0, 0.0, 0.0]
    for analyte, (index, efficiency) in PADS.items():
        c = concentrations[analyte]
        a = c / SLOPES[analyte] * (1.0 + TEMP_COEFFS[analyte] * (temperature - 25.0))
        reflectance = BLANK_REFLECTANCE * 10 ** (-a)
        channel_intensity[index] = 255.0 * reflectance * efficiency

    # Secretory IgA: turbidity attenuates every channel.
    a_siga = concentrations["siga"] / SLOPES["siga"]
    turbidity = 10 ** (-a_siga * TURBIDITY_GAIN)

    # Optics: cross-talk between pads, noise, quantisation.
    raw = [i * turbidity for i in channel_intensity]
    mixed = [
        sum(row[j] * raw[j] for j in range(3)) for row in CROSS_TALK
    ]
    rgb = [
        int(min(max(round(v + rng.gauss(0.0, NOISE_SIGMA)), 0), 255))
        for v in mixed
    ]

    return {
        "features": {
            "rgb_r": rgb[0],
            "rgb_g": rgb[2],
            "rgb_b": rgb[1],
            "temperature_c": round(temperature, 2),
            "humidity_pct": round(humidity, 2),
        },
        "targets": {k: round(v, 4) for k, v in concentrations.items()},
    }


def main() -> None:
    rng = random.Random(SEED)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    feature_names = ["rgb_r", "rgb_g", "rgb_b", "temperature_c", "humidity_pct"]
    target_names = list(DISTRIBUTIONS)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=feature_names + target_names
        )
        writer.writeheader()
        for _ in range(N_SAMPLES):
            sample = forward_model(rng)
            writer.writerow({**sample["features"], **sample["targets"]})

    print(f"wrote {N_SAMPLES} samples -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
