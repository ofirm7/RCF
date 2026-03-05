#!/usr/bin/env python3
"""Populate the properties table with address candidates from CBS data.gov.il.

Usage:
    python scripts/ingest_addresses.py                                  # all cities
    python scripts/ingest_addresses.py --city "תל אביב"                 # single city
    python scripts/ingest_addresses.py --city "תל אביב" --max-house-number 20
    python scripts/ingest_addresses.py --city "חיפה" --step 2           # odd numbers only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rcf.scanner.address_discovery import run_ingestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("rcf.ingest")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Ingest Israeli address candidates from CBS data.gov.il",
    )
    p.add_argument(
        "--city",
        type=str,
        default=None,
        help="Hebrew city name to restrict ingestion (e.g. 'תל אביב')",
    )
    p.add_argument(
        "--max-house-number",
        type=int,
        default=None,
        help="Maximum house number per street (default: from config, usually 100)",
    )
    p.add_argument(
        "--step",
        type=int,
        default=None,
        help="House number increment — 2 means only odd numbers (default: 1)",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    logger.info(
        "Starting address ingestion — city=%r, max_house_number=%s, step=%s",
        args.city, args.max_house_number, args.step,
    )

    summary = await run_ingestion(
        city_filter=args.city,
        max_house_number=args.max_house_number,
        step=args.step,
    )

    logger.info(
        "Ingestion finished — cities: %d, streets: %d, candidates: %d",
        summary["cities_processed"],
        summary["total_streets"],
        summary["total_candidates_upserted"],
    )


if __name__ == "__main__":
    asyncio.run(main())
