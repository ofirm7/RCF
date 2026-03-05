"""Fetch building/planning permits for a location from iPlan ArcGIS REST API."""

from __future__ import annotations

import logging
import ssl
from datetime import date, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rcf.config import get_config
from rcf.db.models import PermitCreate

logger = logging.getLogger(__name__)

# iPlan ArcGIS layer 1 = planning polygons with status, dates, URLs
_IPLAN_QUERY_URL = (
    "https://ags.iplan.gov.il/arcgisiplan/rest/services/"
    "PlanningPublic/Xplan/MapServer/1/query"
)

# Status keywords indicating rejection / withdrawal
_REJECTED_KEYWORDS = {"דחיית תכנית", "התכנית נדחתה"}


def _iplan_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    return ctx


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
async def fetch_permits(
    lat: float,
    lng: float,
    property_id: str,
) -> list[PermitCreate]:
    """Query iPlan for planning applications at the given coordinates.

    Uses an ArcGIS spatial query (point-in-polygon) on the Xplan layer.
    Returns only permits with a rejection status.
    """
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": (
            "pl_number,pl_name,station_desc,internet_short_status,"
            "plan_county_name,pl_date7,pl_rejection_date,pl_url,"
            "receiving_date,pl_landuse_string,ja_concat"
        ),
        "returnGeometry": "false",
        "f": "json",
    }

    async with httpx.AsyncClient(timeout=30, verify=_iplan_ssl_context()) as client:
        resp = await client.get(_IPLAN_QUERY_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    features = payload.get("features", [])
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
                application_date=_epoch_to_date(attrs.get("receiving_date")),
                decision_date=(
                    _epoch_to_date(attrs.get("pl_date7"))
                    or _epoch_to_date(attrs.get("pl_rejection_date"))
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


def _epoch_to_date(epoch_ms: int | float | None) -> date | None:
    """Convert epoch milliseconds to a date object."""
    if not epoch_ms:
        return None
    try:
        return datetime.fromtimestamp(epoch_ms / 1000).date()
    except (ValueError, TypeError, OSError):
        return None
