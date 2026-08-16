"""Community Insights response schemas.

The marketplace only ever exposes server-side aggregates — per-marker
means, standard deviations and percentiles computed over anonymized
shared checkups. Raw biomarker rows never leave the server.
"""

from __future__ import annotations

from pydantic import BaseModel


class CommunityMarkerInsight(BaseModel):
    """One biomarker's cohort comparison for the authenticated user."""

    key: str
    name: str
    unit: str
    # User's own latest value over the window (from their checkups).
    user_latest: float | None
    user_state: str | None
    # Cohort aggregate over shared checkups from *other* users.
    cohort_count: int
    cohort_mean: float | None
    cohort_std: float | None
    cohort_p10: float | None
    cohort_p50: float | None
    cohort_p90: float | None
    # Approximate percentile of the user's latest value within the cohort
    # (0..1); None when the cohort is too small to be meaningful.
    user_percentile: float | None
    # Reference range displayed to the user (default or personalized).
    ref_low: float | None
    ref_high: float | None


class CommunityInsightsResponse(BaseModel):
    """Cohort aggregates plus the similar-profile comparison."""

    # How many shared checkups from other users fed the aggregates.
    cohort_checkups: int
    # How many distinct community members contributed.
    cohort_users: int
    # Minimum cohort size before a marker's comparison is meaningful.
    min_cohort: int
    # Similar-profile filter applied (sex + age band + activity level).
    similar_profile: dict[str, str] | None
    similar_profile_count: int
    markers: dict[str, CommunityMarkerInsight]
