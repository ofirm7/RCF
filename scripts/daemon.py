#!/usr/bin/env python3
"""Long-running daemon — continuously ingests addresses from CBS data.gov.il
and scans for rejected plans from iPlan.

Cycle:
  1. Fetch all cities from CBS
  2. For each city: fetch streets, generate house-number candidates, upsert to DB
  3. Scan iPlan for all rejected plans across Israel
  4. Sleep, then repeat

The daemon never exits — it cycles through all 1,300+ Israeli cities,
ingesting addresses and scanning for refund opportunities indefinitely.

Usage:
    python scripts/daemon.py
    python scripts/daemon.py --max-house-number 10   # fewer candidates per street (faster)
    python scripts/daemon.py --sleep 3600             # 1h between full cycles
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rcf.scanner.address_discovery import fetch_cities, ingest_city
from rcf.scanner.runner import scan_rejected_plans

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rcf.daemon")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d — shutting down after current city...", signum)
    _shutdown = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RCF continuous ingestion & scan daemon")
    p.add_argument("--max-house-number", type=int, default=int(os.environ.get("INGEST_MAX_HOUSE", "20")),
                    help="House numbers per street (default: 20)")
    p.add_argument("--step", type=int, default=int(os.environ.get("INGEST_STEP", "1")),
                    help="House number step (default: 1)")
    p.add_argument("--batch-size", type=int, default=500,
                    help="DB upsert batch size (default: 500)")
    p.add_argument("--sleep", type=int, default=int(os.environ.get("DAEMON_SLEEP", "1800")),
                    help="Seconds between full cycles (default: 1800 = 30min)")
    p.add_argument("--city-delay", type=float, default=1.0,
                    help="Seconds pause between cities (rate limiting, default: 1)")
    return p.parse_args()


async def run_cycle(args: argparse.Namespace, cycle_num: int) -> dict:
    """Run one full ingestion + scan cycle."""
    global _shutdown

    logger.info("=== CYCLE %d START ===", cycle_num)
    cycle_start = time.time()

    # ── Phase 1: Fetch city list from CBS ────────────────────────
    logger.info("[Phase 1] Fetching city list from CBS data.gov.il...")
    cities = await fetch_cities()
    logger.info("  Loaded %d cities from CBS", len(cities))

    # ── Phase 2: Ingest addresses city by city ───────────────────
    logger.info("[Phase 2] Ingesting addresses (max_house=%d, step=%d)...",
                args.max_house_number, args.step)
    total_streets = 0
    total_addresses = 0
    cities_done = 0

    for city in cities:
        if _shutdown:
            logger.info("Shutdown requested — stopping ingestion")
            break

        try:
            result = await ingest_city(
                city,
                max_house_number=args.max_house_number,
                step=args.step,
                batch_size=args.batch_size,
            )
            total_streets += result["streets"]
            total_addresses += result["inserted"]
            cities_done += 1
        except Exception:
            logger.exception("Failed to ingest city %s — skipping", city.name_he)

        # Rate limit: small pause between cities
        await asyncio.sleep(args.city_delay)

    logger.info("  Ingestion: %d cities, %d streets, %d addresses",
                cities_done, total_streets, total_addresses)

    # ── Phase 3: Scan rejected plans from iPlan ──────────────────
    if not _shutdown:
        logger.info("[Phase 3] Scanning rejected plans from iPlan...")
        try:
            scan_result = await scan_rejected_plans()
            logger.info("  Scan: %d total, %d scanned, %d errors",
                        scan_result["total"], scan_result["scanned"], scan_result["errors"])
        except Exception:
            logger.exception("Failed to scan rejected plans")
            scan_result = {"total": 0, "scanned": 0, "errors": 0}
    else:
        scan_result = {"total": 0, "scanned": 0, "errors": 0}

    elapsed = time.time() - cycle_start
    logger.info("=== CYCLE %d DONE in %.0fs — %d addresses ingested, %d plans scanned ===",
                cycle_num, elapsed, total_addresses, scan_result["total"])

    return {
        "cycle": cycle_num,
        "cities": cities_done,
        "streets": total_streets,
        "addresses": total_addresses,
        "plans_scanned": scan_result["total"],
        "eligible_found": scan_result["scanned"],
        "elapsed_seconds": round(elapsed),
    }


async def main() -> None:
    args = parse_args()

    logger.info("RCF Daemon starting — max_house=%d, step=%d, sleep=%ds",
                args.max_house_number, args.step, args.sleep)

    cycle_num = 0
    while not _shutdown:
        cycle_num += 1
        try:
            await run_cycle(args, cycle_num)
        except Exception:
            logger.exception("Cycle %d failed unexpectedly", cycle_num)

        if _shutdown:
            break

        logger.info("Sleeping %d seconds before next cycle...", args.sleep)
        # Interruptible sleep
        for _ in range(args.sleep):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("Daemon stopped after %d cycles.", cycle_num)


if __name__ == "__main__":
    asyncio.run(main())
