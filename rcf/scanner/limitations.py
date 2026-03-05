"""Statute of limitations check — 7-year civil claim window."""

from __future__ import annotations

from datetime import date, timedelta

LIMITATION_YEARS = 7
URGENCY_THRESHOLD_DAYS = 180  # flag cases expiring within 6 months


def expiry_date(decision_date: date) -> date:
    """Return the date on which the refund claim expires."""
    return decision_date.replace(year=decision_date.year + LIMITATION_YEARS)


def is_within_window(decision_date: date | None) -> bool:
    """Return True if *decision_date* is recent enough to still claim a refund."""
    if decision_date is None:
        return False
    return expiry_date(decision_date) > date.today()


def is_urgent(decision_date: date) -> bool:
    """Return True if the claim window closes within 6 months."""
    remaining = (expiry_date(decision_date) - date.today()).days
    return 0 < remaining <= URGENCY_THRESHOLD_DAYS
