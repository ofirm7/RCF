"""Estimate the refund amount for a rejected permit.

Uses published municipal fee schedules (תקנות אגרות בנייה).  For the MVP
this is a rough heuristic — actual amounts are confirmed by lawyers during
the claim process.
"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

# Base fee per sqm (ILS) — simplified schedule from the 2024 regulations.
# In production, load per-municipality fee tables from a data file.
_BASE_FEE_PER_SQM: dict[str, int] = {
    "residential": 130,
    "commercial": 180,
    "industrial": 100,
    "default": 130,
}

# Minimum / maximum bounds for estimates (ILS)
_MIN_ESTIMATE = 5_000
_MAX_ESTIMATE = 500_000


def estimate(
    permit_type: str | None = None,
    building_area_sqm: float | None = None,
    decision_date: date | None = None,
    municipality: str | None = None,
) -> int:
    """Return an estimated refund amount in ILS (whole shekels).

    Falls back to a conservative flat estimate when area data is unavailable.
    """
    if building_area_sqm and building_area_sqm > 0:
        category = (permit_type or "default").lower()
        rate = _BASE_FEE_PER_SQM.get(category, _BASE_FEE_PER_SQM["default"])
        raw = int(building_area_sqm * rate)
    else:
        # No area info — use a conservative median estimate
        raw = 25_000

    # Apply CPI adjustment for older decisions (rough 3% annual inflation)
    if decision_date:
        years_ago = (date.today() - decision_date).days / 365.25
        raw = int(raw * (1.03 ** years_ago))

    # Clamp to reasonable range
    return max(_MIN_ESTIMATE, min(raw, _MAX_ESTIMATE))
