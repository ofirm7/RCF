"""Shared iPlan ArcGIS REST API client.

Centralises the SSL context, retry logic and query helpers used by
both the permit fetcher (spatial queries) and the plan discovery /
fee scanner (attribute queries).
"""

from __future__ import annotations

import logging
import ssl
from datetime import date, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_IPLAN_QUERY_URL = (
    "https://ags.iplan.gov.il/arcgisiplan/rest/services/"
    "PlanningPublic/Xplan/MapServer/1/query"
)

# Extended fields that include building-rights quantities
EXTENDED_OUT_FIELDS = (
    "pl_number,pl_name,station_desc,internet_short_status,"
    "plan_county_name,pl_date7,pl_rejection_date,pl_url,"
    "receiving_date,pl_landuse_string,ja_concat,mp_id,"
    "pl_area_dunam,"
    "quantity_delta_105,quantity_delta_110,quantity_delta_120,"
    "quantity_delta_125,quantity_delta_60,quantity_delta_75,quantity_delta_80,"
    "pq_authorised_quantity_105,pq_authorised_quantity_110,"
    "pq_authorised_quantity_120"
)

# Basic fields (used by the rejected-plan pipeline)
BASIC_OUT_FIELDS = (
    "pl_number,pl_name,station_desc,internet_short_status,"
    "plan_county_name,pl_date7,pl_rejection_date,pl_url,"
    "receiving_date,pl_landuse_string,ja_concat"
)


def ssl_ctx() -> ssl.SSLContext:
    """Return an SSL context with relaxed security for Israeli gov servers."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    return ctx


def epoch_to_date(epoch_ms: int | float | None) -> date | None:
    """Convert epoch milliseconds to a date object."""
    if not epoch_ms:
        return None
    try:
        return datetime.fromtimestamp(epoch_ms / 1000).date()
    except (ValueError, TypeError, OSError):
        return None


def centroid_from_geometry(geometry: dict) -> tuple[float | None, float | None]:
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
async def query_plans(
    *,
    where: str,
    out_fields: str = BASIC_OUT_FIELDS,
    return_geometry: bool = False,
    max_results: int = 1000,
    geometry: str | None = None,
    geometry_type: str | None = None,
    spatial_rel: str | None = None,
) -> list[dict]:
    """Execute a query against iPlan ArcGIS Layer 1 and return raw features."""

    params: dict = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": str(return_geometry).lower(),
        "resultRecordCount": str(max_results),
        "f": "json",
    }
    if return_geometry:
        params["outSR"] = "4326"
    if geometry:
        params["geometry"] = geometry
        params["geometryType"] = geometry_type or "esriGeometryPoint"
        params["inSR"] = "4326"
        params["spatialRel"] = spatial_rel or "esriSpatialRelIntersects"

    async with httpx.AsyncClient(timeout=60, verify=ssl_ctx()) as client:
        resp = await client.get(_IPLAN_QUERY_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    features = payload.get("features", [])
    logger.debug("iPlan query returned %d features (where=%s)", len(features), where[:80])
    return features


async def fetch_plans_for_city(
    city: str,
    *,
    status_filter: str | None = None,
    max_results: int = 1000,
) -> list[dict]:
    """Fetch all plans for a city with extended fields (including building rights).

    Args:
        city: Hebrew city name (e.g. "חיפה")
        status_filter: Optional iPlan status keyword filter
        max_results: Max plans to return
    """
    where_parts = [f"plan_county_name LIKE '%{city}%'"]
    if status_filter:
        where_parts.append(f"internet_short_status LIKE '%{status_filter}%'")

    where = " AND ".join(where_parts)

    features = await query_plans(
        where=where,
        out_fields=EXTENDED_OUT_FIELDS,
        return_geometry=True,
        max_results=max_results,
    )

    plans = []
    for feature in features:
        attrs = feature.get("attributes", {})
        geometry = feature.get("geometry", {})
        lat, lng = centroid_from_geometry(geometry)

        plans.append({
            **attrs,
            "city": attrs.get("plan_county_name") or city,
            "lat": lat,
            "lng": lng,
            "decision_date": epoch_to_date(attrs.get("pl_date7")),
            "application_date": epoch_to_date(attrs.get("receiving_date")),
        })

    logger.info("Fetched %d plans for city=%s", len(plans), city)
    return plans
