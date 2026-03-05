"""Fetch Israeli cities and streets from CBS data.gov.il and populate the
properties table with address candidates for scanning.

The CBS (Central Bureau of Statistics) publishes an official street register
via a CKAN API.  This module paginates through it, generates house-number
candidates for every street, and upserts them as ``pending`` rows in the
``properties`` table.  The existing scanner pipeline then picks them up.

Typical usage::

    from rcf.scanner.address_discovery import run_ingestion
    asyncio.run(run_ingestion(city_filter="תל אביב"))
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rcf.config import get_config
from rcf.db import repository
from rcf.db.models import PropertyCreate

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data transfer objects
# ------------------------------------------------------------------

@dataclass(frozen=True)
class CityRecord:
    code: str
    name_he: str


@dataclass(frozen=True)
class StreetRecord:
    city_code: str
    city_name: str
    street_code: str
    street_name: str


# ------------------------------------------------------------------
# CKAN API helpers
# ------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _fetch_page(
    client: httpx.AsyncClient,
    resource_id: str,
    offset: int,
    limit: int,
    filters: dict | None = None,
) -> dict:
    """Fetch a single page from the CKAN datastore_search API."""
    cfg = get_config()
    params: dict = {
        "resource_id": resource_id,
        "limit": limit,
        "offset": offset,
    }
    if filters:
        params["filters"] = json.dumps(filters, ensure_ascii=False)

    resp = await client.get(cfg.ckan_base_url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


async def fetch_all_records(
    resource_id: str,
    filters: dict | None = None,
) -> list[dict]:
    """Paginate through an entire CKAN resource and return all records."""
    cfg = get_config()
    records: list[dict] = []
    offset = 0

    async with httpx.AsyncClient() as client:
        while True:
            payload = await _fetch_page(
                client, resource_id, offset=offset,
                limit=cfg.ckan_page_size, filters=filters,
            )
            result = payload.get("result", {})
            page = result.get("records", [])
            records.extend(page)

            total = result.get("total", 0)
            offset += len(page)

            logger.debug(
                "Fetched %d / %d records from resource %s",
                offset, total, resource_id,
            )

            if offset >= total or not page:
                break

    return records


# ------------------------------------------------------------------
# Domain helpers
# ------------------------------------------------------------------

async def fetch_cities() -> list[CityRecord]:
    """Return all Israeli cities/settlements from the CBS cities resource."""
    cfg = get_config()
    raw = await fetch_all_records(cfg.ckan_cities_resource_id)
    cities = []
    for r in raw:
        code = r.get("סמל_ישוב")
        name = r.get("שם_ישוב")
        if code and name:
            cities.append(CityRecord(code=str(code).strip(), name_he=name.strip()))
    return cities


async def fetch_streets_for_city(city_code: str) -> list[StreetRecord]:
    """Return all streets for *city_code* from the CBS streets resource."""
    cfg = get_config()
    raw = await fetch_all_records(
        cfg.ckan_streets_resource_id,
        filters={"סמל_ישוב": city_code},
    )
    streets = []
    for r in raw:
        street_name = r.get("שם_רחוב")
        city_name = r.get("שם_ישוב")
        if street_name and city_name:
            streets.append(StreetRecord(
                city_code=str(r["סמל_ישוב"]).strip(),
                city_name=city_name.strip(),
                street_code=str(r.get("סמל_רחוב", "")).strip(),
                street_name=street_name.strip(),
            ))
    return streets


def generate_address_candidates(
    street: StreetRecord,
    max_house_number: int,
    step: int = 1,
) -> list[tuple[str, str]]:
    """Return ``(address_text, city)`` pairs for every house-number candidate."""
    return [
        (f"{street.street_name} {n}", street.city_name)
        for n in range(1, max_house_number + 1, step)
    ]


# ------------------------------------------------------------------
# Batch upsert
# ------------------------------------------------------------------

def _flush_batch(batch: list[tuple[str, str]]) -> int:
    """Upsert a batch of ``(address_text, city)`` tuples. Returns count."""
    count = 0
    for address_text, city_name in batch:
        repository.upsert_property(
            PropertyCreate(address_text=address_text, city=city_name)
        )
        count += 1
    return count


# ------------------------------------------------------------------
# Orchestrators
# ------------------------------------------------------------------

async def ingest_city(
    city: CityRecord,
    max_house_number: int,
    step: int,
    batch_size: int,
) -> dict:
    """Fetch all streets for *city*, generate candidates, and upsert them."""
    logger.info("Ingesting city: %s (code=%s)", city.name_he, city.code)
    streets = await fetch_streets_for_city(city.code)
    logger.info("  Found %d streets in %s", len(streets), city.name_he)

    inserted = 0
    batch: list[tuple[str, str]] = []

    for street in streets:
        batch.extend(generate_address_candidates(street, max_house_number, step))

        if len(batch) >= batch_size:
            inserted += _flush_batch(batch)
            batch = []

    if batch:
        inserted += _flush_batch(batch)

    logger.info(
        "  City %s done — %d streets, %d candidates upserted",
        city.name_he, len(streets), inserted,
    )
    return {"city": city.name_he, "streets": len(streets), "inserted": inserted}


async def run_ingestion(
    city_filter: str | None = None,
    max_house_number: int | None = None,
    step: int | None = None,
) -> dict:
    """Main entry point — fetch cities and streets from CBS, generate address
    candidates, and upsert them all as ``pending`` properties.

    Args:
        city_filter: Hebrew city name to restrict to a single city.
        max_house_number: Override the config default.
        step: Override the config default house-number step.

    Returns:
        Summary dict with ``cities_processed``, ``total_streets``,
        ``total_candidates_upserted``.
    """
    cfg = get_config()
    max_hn = max_house_number if max_house_number is not None else cfg.ingestion_max_house_number
    hn_step = step if step is not None else cfg.ingestion_house_number_step
    batch_sz = cfg.ingestion_batch_size

    all_cities = await fetch_cities()
    logger.info("CBS cities loaded: %d total", len(all_cities))

    if city_filter:
        # CBS names may differ slightly (e.g. "תל אביב - יפו" for "תל אביב"),
        # so match on substring containment in either direction.
        cf = city_filter.strip()
        target_cities = [
            c for c in all_cities
            if cf in c.name_he or c.name_he in cf
        ]
        if not target_cities:
            raise ValueError(
                f"City {city_filter!r} not found in CBS data. "
                f"Check spelling — CBS uses full official Hebrew names "
                f"(e.g. 'תל אביב - יפו' not 'תל אביב')."
            )
    else:
        target_cities = all_cities

    logger.info(
        "Processing %d city/cities, max_house_number=%d, step=%d",
        len(target_cities), max_hn, hn_step,
    )

    total_streets = 0
    total_inserted = 0

    for city in target_cities:
        result = await ingest_city(city, max_hn, hn_step, batch_sz)
        total_streets += result["streets"]
        total_inserted += result["inserted"]

    summary = {
        "cities_processed": len(target_cities),
        "total_streets": total_streets,
        "total_candidates_upserted": total_inserted,
    }
    logger.info("Ingestion complete: %s", summary)
    return summary
