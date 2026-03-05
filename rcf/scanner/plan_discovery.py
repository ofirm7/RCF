"""Discover rejected planning applications directly from iPlan ArcGIS."""

from __future__ import annotations

import logging

from rcf.scanner.iplan_client import (
    BASIC_OUT_FIELDS,
    centroid_from_geometry,
    epoch_to_date,
    query_plans,
)

logger = logging.getLogger(__name__)


async def fetch_rejected_plans(
    city_filter: str | None = None,
    max_results: int = 500,
) -> list[dict]:
    """Query iPlan for all rejected/withdrawn planning applications.

    Returns raw plan dicts with geometry centroids for address matching.
    """
    where_parts = [
        "(internet_short_status LIKE '%דחי%' OR internet_short_status LIKE '%נדחתה%' "
        "OR internet_short_status LIKE '%ביטול%')"
    ]
    if city_filter:
        where_parts.append(f"plan_county_name LIKE '%{city_filter}%'")

    where = " AND ".join(where_parts)

    features = await query_plans(
        where=where,
        out_fields=BASIC_OUT_FIELDS,
        return_geometry=True,
        max_results=max_results,
    )

    logger.info("iPlan returned %d rejected plans%s",
                len(features),
                f" for city={city_filter}" if city_filter else "")

    plans = []
    for feature in features:
        attrs = feature.get("attributes", {})
        geometry = feature.get("geometry", {})
        lat, lng = centroid_from_geometry(geometry)

        plans.append({
            "pl_number": attrs.get("pl_number"),
            "pl_name": attrs.get("pl_name"),
            "station_desc": attrs.get("station_desc"),
            "internet_short_status": attrs.get("internet_short_status"),
            "city": attrs.get("plan_county_name") or "unknown",
            "committee_name": attrs.get("ja_concat"),
            "decision_date": epoch_to_date(attrs.get("pl_date7"))
                            or epoch_to_date(attrs.get("pl_rejection_date")),
            "application_date": epoch_to_date(attrs.get("receiving_date")),
            "source_url": attrs.get("pl_url"),
            "lat": lat,
            "lng": lng,
        })

    return plans
