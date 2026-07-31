"""Linear value mapping helper used by the biomarker simulator."""

from __future__ import annotations


def map_range(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float,
    out_max: float,
) -> float:
    """Map ``value`` from [in_min, in_max] onto [out_min, out_max].

    The result is clamped to the output range. This is the Arduino-style
    ``map()`` extended with clamping, used to turn raw sensor units into
    plausible biomarker base values.
    """
    if in_max == in_min:
        return out_min
    normalized = (value - in_min) / (in_max - in_min)
    mapped = out_min + normalized * (out_max - out_min)
    return max(min(mapped, max(out_min, out_max)), min(out_min, out_max))
