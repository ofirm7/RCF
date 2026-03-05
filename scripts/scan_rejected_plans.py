#!/usr/bin/env python3
"""Scan rejected planning applications from iPlan for refund eligibility.

This script discovers rejected plans directly from the national iPlan database
and runs the NLP classifier to determine refund eligibility.

Usage:
    python scripts/scan_rejected_plans.py [--city "תל אביב"]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from rcf.scanner.runner import scan_rejected_plans

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan rejected plans for refund eligibility")
    parser.add_argument("--city", type=str, default=None, help="Filter by city name (Hebrew)")
    args = parser.parse_args()

    print(f"=== Scanning rejected plans{f' in {args.city}' if args.city else ' across Israel'} ===")
    result = asyncio.run(scan_rejected_plans(city_filter=args.city))

    print(f"\nDone — scanned: {result['scanned']}, errors: {result['errors']}, total: {result['total']}")

    if result["scanned"] == 0 and result["total"] > 0:
        print("All plans failed. Check logs above for details.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
