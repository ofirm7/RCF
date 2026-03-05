"""Resolve a free-text Israeli address to geographic coordinates via Nominatim."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rcf.config import get_config
from rcf.db.models import CadastralInfo

logger = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
async def resolve(address: str) -> CadastralInfo | None:
    """Geocode *address* using Nominatim (OpenStreetMap).

    Returns a ``CadastralInfo`` with lat/lng populated.
    Block/plot are left empty (no longer available via free API).
    Returns ``None`` when the address cannot be resolved.
    """
    if not address:
        return None

    params = {
        "q": address,
        "format": "json",
        "countrycodes": "il",
        "limit": "1",
        "accept-language": "he",
    }
    headers = {"User-Agent": "RCF-Scanner/1.0 (building-fee-refund-checker)"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        results = resp.json()

    if not results:
        logger.warning("Nominatim returned no results for %r", address)
        return None

    best = results[0]
    lat = float(best["lat"])
    lng = float(best["lon"])

    logger.debug("Resolved %r → lat=%.6f, lng=%.6f", address, lat, lng)

    return CadastralInfo(
        block="",
        plot="",
        municipality_id=None,
        lat=lat,
        lng=lng,
    )
