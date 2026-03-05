#!/usr/bin/env python3
"""Entry point — run the RCF scanner batch job.

Usage:
    python scripts/run_scanner.py                          # scan all pending
    python scripts/run_scanner.py --city "תל אביב" --limit 10
    python scripts/run_scanner.py --seed addresses.csv     # seed + scan
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rcf.db import repository
from rcf.scanner.runner import run_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("rcf.cli")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RCF Scanner — batch refund detection")
    p.add_argument("--city", type=str, help="Limit scan to a specific city")
    p.add_argument("--limit", type=int, default=1000, help="Max addresses to scan")
    p.add_argument("--concurrency", type=int, default=5, help="Parallel requests")
    p.add_argument(
        "--seed",
        type=str,
        help="Path to CSV file with columns: address,city — seeds DB before scanning",
    )
    return p.parse_args()


def seed_from_csv(csv_path: str) -> int:
    """Load addresses from a CSV into the properties table. Returns count."""
    from rcf.db.models import PropertyCreate

    count = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            address = row.get("address") or row.get("כתובת") or ""
            city = row.get("city") or row.get("עיר") or ""
            if not address or not city:
                continue
            repository.upsert_property(
                PropertyCreate(address_text=address.strip(), city=city.strip())
            )
            count += 1
    return count


async def main() -> None:
    args = parse_args()

    # Optionally seed addresses first
    if args.seed:
        n = seed_from_csv(args.seed)
        logger.info("Seeded %d addresses from %s", n, args.seed)

    # Load pending addresses from DB
    rows = repository.get_pending_properties(city=args.city, limit=args.limit)
    if not rows:
        logger.info("No pending addresses to scan.")
        return

    addresses = [(r["address_text"], r["city"]) for r in rows]
    logger.info("Starting scan of %d addresses …", len(addresses))

    summary = await run_batch(addresses, concurrency=args.concurrency)

    logger.info(
        "Done — scanned: %d, errors: %d, total: %d",
        summary["scanned"],
        summary["errors"],
        summary["total"],
    )


if __name__ == "__main__":
    asyncio.run(main())
