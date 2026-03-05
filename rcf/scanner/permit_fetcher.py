"""Fetch building/planning permits for a location from iPlan ArcGIS REST API."""

from __future__ import annotations

import logging
from datetime import date

from rcf.db.models import PermitCreate
from rcf.scanner.iplan_client import BASIC_OUT_FIELDS, epoch_to_date, query_plans

logger = logging.getLogger(__name__)

# Status keywords indicating rejection / withdrawal
_REJECTED_KEYWORDS = {"דחיית תכנית", "התכנית נדחתה"}


async def fetch_permits(
    lat: float,
    lng: float,
    property_id: str,
) -> list[PermitCreate]:
    """Query iPlan for planning applications at the given coordinates.

    Uses an ArcGIS spatial query (point-in-polygon) on the Xplan layer.
    Returns only permits with a rejection status.
    """
    features = await query_plans(
        where="1=1",
        out_fields=BASIC_OUT_FIELDS,
        geometry=f"{lng},{lat}",
        geometry_type="esriGeometryPoint",
        spatial_rel="esriSpatialRelIntersects",
    )

    if not features:
        logger.info("iPlan returned no plans for lat=%.6f lng=%.6f", lat, lng)
        return []

    permits: list[PermitCreate] = []
    for feature in features:
        attrs = feature.get("attributes", {})
        status = attrs.get("internet_short_status") or ""
        station = attrs.get("station_desc") or ""

        # Check if this plan was rejected
        decision_type = _classify_status(status, station)
        if decision_type is None:
            continue

        permits.append(
            PermitCreate(
                property_id=property_id,
                permit_number=attrs.get("pl_number"),
                application_date=epoch_to_date(attrs.get("receiving_date")),
                decision_date=(
                    epoch_to_date(attrs.get("pl_date7"))
                    or epoch_to_date(attrs.get("pl_rejection_date"))
                ),
                decision_type=decision_type,
                committee_name=attrs.get("ja_concat"),
                source_url=attrs.get("pl_url"),
                raw_decision=None,
            )
        )

    logger.info(
        "Found %d rejected/withdrawn plans for lat=%.6f lng=%.6f (out of %d total)",
        len(permits),
        lat,
        lng,
        len(features),
    )
    return permits


def _classify_status(internet_status: str, station_desc: str) -> str | None:
    """Return a canonical decision type if the plan was rejected, else None."""
    for kw in _REJECTED_KEYWORDS:
        if kw in internet_status or kw in station_desc:
            return "rejected"

    # Also match Hebrew withdrawal/abandonment keywords
    withdrawal_kw = ["ביטול", "נמשך", "בוטל"]
    for kw in withdrawal_kw:
        if kw in internet_status or kw in station_desc:
            return "withdrawn"

    return None
