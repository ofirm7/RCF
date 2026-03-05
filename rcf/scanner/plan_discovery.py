"""Discover rejected planning applications directly from iPlan ArcGIS."""

from __future__ import annotations

import logging
import ssl
from datetime import date, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rcf.db.models import PermitCreate

logger = logging.getLogger(__name__)

_IPLAN_QUERY_URL = (
    "https://ags.iplan.gov.il/arcgisiplan/rest/services/"
    "PlanningPublic/Xplan/MapServer/1/query"
)


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    return ctx


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
async def fetch_rejected_plans(
    city_filter: str | None = None,
    max_results: int = 500,
) -> list[dict]:
    """Query iPlan for all rejected/withdrawn planning applications.

    Returns raw plan dicts with geometry centroids for address matching.
    """
    # Build WHERE clause for rejected plans
    where_parts = [
        "(internet_short_status LIKE '%דחי%' OR internet_short_status LIKE '%נדחתה%' "
        "OR internet_short_status LIKE '%ביטול%')"
    ]
    if city_filter:
        where_parts.append(f"plan_county_name LIKE '%{city_filter}%'")

    where = " AND ".join(where_parts)

    params = {
        "where": where,
        "outFields": (
            "pl_number,pl_name,station_desc,internet_short_status,"
            "plan_county_name,pl_date7,pl_rejection_date,pl_url,"
            "receiving_date,pl_landuse_string,ja_concat"
        ),
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": str(max_results),
        "f": "json",
    }

    async with httpx.AsyncClient(timeout=60, verify=_ssl_ctx()) as client:
        resp = await client.get(_IPLAN_QUERY_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    features = payload.get("features", [])
    logger.info("iPlan returned %d rejected plans%s",
                len(features),
                f" for city={city_filter}" if city_filter else "")

    plans = []
    for feature in features:
        attrs = feature.get("attributes", {})
        geometry = feature.get("geometry", {})

        # Get centroid from polygon rings
        lat, lng = _centroid_from_geometry(geometry)

        plans.append({
            "pl_number": attrs.get("pl_number"),
            "pl_name": attrs.get("pl_name"),
            "station_desc": attrs.get("station_desc"),
            "internet_short_status": attrs.get("internet_short_status"),
            "city": attrs.get("plan_county_name") or "unknown",
            "committee_name": attrs.get("ja_concat"),
            "decision_date": _epoch_to_date(attrs.get("pl_date7"))
                            or _epoch_to_date(attrs.get("pl_rejection_date")),
            "application_date": _epoch_to_date(attrs.get("receiving_date")),
            "source_url": attrs.get("pl_url"),
            "lat": lat,
            "lng": lng,
        })

    return plans


def _centroid_from_geometry(geometry: dict) -> tuple[float | None, float | None]:
    """Calculate rough centroid from ArcGIS polygon geometry."""
    rings = geometry.get("rings", [])
    if not rings:
        return None, None

    all_points = [pt for ring in rings for pt in ring]
    if not all_points:
        return None, None

    avg_lng = sum(p[0] for p in all_points) / len(all_points)
    avg_lat = sum(p[1] for p in all_points) / len(all_points)
    return avg_lat, avg_lng


def _epoch_to_date(epoch_ms: int | float | None) -> date | None:
    if not epoch_ms:
        return None
    try:
        return datetime.fromtimestamp(epoch_ms / 1000).date()
    except (ValueError, TypeError, OSError):
        return None
