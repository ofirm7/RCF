"""Lawyer-case matching algorithm.

When a new eligible refund case is detected, find and rank lawyers who
cover that municipality and are best suited to handle the case.
"""

from __future__ import annotations

import logging

from rcf.db import repository

logger = logging.getLogger(__name__)


def find_matching_lawyers(city: str, limit: int = 5) -> list[dict]:
    """Return lawyers covering *city*, ranked by suitability.

    Ranking criteria (in order of priority):
    1. Verified lawyers first
    2. Premium subscribers first
    3. Fewer active cases (lower caseload = more capacity)
    """
    lawyers = repository.get_lawyers_for_municipality(city)
    if not lawyers:
        logger.info("No lawyers found covering %s", city)
        return []

    def _sort_key(lawyer: dict) -> tuple:
        return (
            not lawyer.get("is_verified", False),   # verified first
            lawyer.get("subscription") != "premium",  # premium first
        )

    lawyers.sort(key=_sort_key)
    return lawyers[:limit]


def match_case_to_lawyers(refund_case: dict) -> list[dict]:
    """Given a refund case dict (with nested property), find matching lawyers."""
    # Extract city from nested property data
    prop = refund_case.get("properties") or {}
    city = prop.get("city") or ""
    if not city:
        logger.warning("Case %s has no city — cannot match", refund_case.get("id"))
        return []

    return find_matching_lawyers(city)
