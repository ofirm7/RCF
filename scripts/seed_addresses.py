#!/usr/bin/env python3
"""Seed the properties table with Israeli addresses for scanning.

This script provides multiple seeding strategies:
  1. From a CSV file
  2. From a hardcoded list of sample addresses (for development)

Usage:
    python scripts/seed_addresses.py                  # seed sample addresses
    python scripts/seed_addresses.py --csv data.csv   # seed from CSV
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rcf.db import repository
from rcf.db.models import PropertyCreate

# Sample addresses for development / proof-of-concept
SAMPLE_ADDRESSES: list[tuple[str, str]] = [
    ("רחוב הרצל 10", "תל אביב"),
    ("רחוב יפו 97", "ירושלים"),
    ("שדרות העצמאות 15", "חיפה"),
    ("רחוב רוטשילד 5", "ראשון לציון"),
    ("רחוב ביאליק 20", "פתח תקווה"),
    ("רחוב ויצמן 30", "כפר סבא"),
    ("רחוב סוקולוב 12", "הרצליה"),
    ("רחוב הנשיא 8", "רמת גן"),
    ("רחוב ז'בוטינסקי 44", "בני ברק"),
    ("שדרות בן גוריון 1", "באר שבע"),
]


def seed_samples() -> int:
    count = 0
    for address, city in SAMPLE_ADDRESSES:
        repository.upsert_property(PropertyCreate(address_text=address, city=city))
        count += 1
    return count


def seed_csv(path: str) -> int:
    count = 0
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            address = row.get("address") or row.get("כתובת") or ""
            city = row.get("city") or row.get("עיר") or ""
            if not address.strip() or not city.strip():
                continue
            repository.upsert_property(
                PropertyCreate(address_text=address.strip(), city=city.strip())
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed RCF address database")
    parser.add_argument("--csv", type=str, help="Path to CSV file with address,city columns")
    args = parser.parse_args()

    if args.csv:
        n = seed_csv(args.csv)
        print(f"Seeded {n} addresses from {args.csv}")
    else:
        n = seed_samples()
        print(f"Seeded {n} sample addresses for development")


if __name__ == "__main__":
    main()
