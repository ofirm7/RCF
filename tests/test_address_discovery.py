"""Tests for the address discovery module (CBS CKAN ingestion)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcf.scanner.address_discovery import (
    StreetRecord,
    generate_address_candidates,
)


# --- generate_address_candidates ---

def test_generate_candidates_basic():
    street = StreetRecord(
        city_code="5000", city_name="תל אביב",
        street_code="100", street_name="הרצל",
    )
    result = generate_address_candidates(street, max_house_number=5)
    assert len(result) == 5
    assert result[0] == ("הרצל 1", "תל אביב")
    assert result[4] == ("הרצל 5", "תל אביב")


def test_generate_candidates_with_step():
    street = StreetRecord(
        city_code="5000", city_name="חיפה",
        street_code="200", street_name="בן גוריון",
    )
    result = generate_address_candidates(street, max_house_number=10, step=2)
    # 1, 3, 5, 7, 9
    assert len(result) == 5
    assert result[0] == ("בן גוריון 1", "חיפה")
    assert result[1] == ("בן גוריון 3", "חיפה")


def test_generate_candidates_single():
    street = StreetRecord(
        city_code="1", city_name="x", street_code="1", street_name="y",
    )
    result = generate_address_candidates(street, max_house_number=1)
    assert len(result) == 1
    assert result[0] == ("y 1", "x")


def test_generate_candidates_zero_max():
    street = StreetRecord(
        city_code="1", city_name="x", street_code="1", street_name="y",
    )
    result = generate_address_candidates(street, max_house_number=0)
    assert result == []


# --- fetch_cities (mocked) ---

@pytest.mark.asyncio
async def test_fetch_cities():
    mock_records = [
        {"סמל_ישוב": "5000", "שם_ישוב": " תל אביב - יפו "},
        {"סמל_ישוב": "3000", "שם_ישוב": " חיפה "},
        {"סמל_ישוב": None, "שם_ישוב": "incomplete"},  # should be skipped
    ]

    with patch("rcf.scanner.address_discovery.fetch_all_records", new_callable=AsyncMock, return_value=mock_records):
        from rcf.scanner.address_discovery import fetch_cities
        cities = await fetch_cities()

    assert len(cities) == 2
    assert cities[0].code == "5000"
    assert cities[0].name_he == "תל אביב - יפו"
    assert cities[1].name_he == "חיפה"


# --- fetch_streets_for_city (mocked) ---

@pytest.mark.asyncio
async def test_fetch_streets_for_city():
    mock_records = [
        {"סמל_ישוב": "5000", "שם_ישוב": "תל אביב", "סמל_רחוב": "100", "שם_רחוב": "הרצל"},
        {"סמל_ישוב": "5000", "שם_ישוב": "תל אביב", "סמל_רחוב": "101", "שם_רחוב": None},  # skipped
    ]

    with patch("rcf.scanner.address_discovery.fetch_all_records", new_callable=AsyncMock, return_value=mock_records):
        from rcf.scanner.address_discovery import fetch_streets_for_city
        streets = await fetch_streets_for_city("5000")

    assert len(streets) == 1
    assert streets[0].street_name == "הרצל"
    assert streets[0].city_name == "תל אביב"


# --- _flush_batch (mocked DB) ---

@patch("rcf.scanner.address_discovery.repository")
def test_flush_batch(mock_repo):
    from rcf.scanner.address_discovery import _flush_batch
    mock_repo.upsert_property.return_value = {"id": "x"}
    batch = [("הרצל 1", "תל אביב"), ("הרצל 2", "תל אביב")]
    count = _flush_batch(batch)
    assert count == 2
    assert mock_repo.upsert_property.call_count == 2


# --- ingest_city (mocked) ---

@pytest.mark.asyncio
async def test_ingest_city():
    from rcf.scanner.address_discovery import CityRecord, ingest_city

    mock_streets = [
        StreetRecord(city_code="5000", city_name="תל אביב", street_code="100", street_name="הרצל"),
    ]

    with patch("rcf.scanner.address_discovery.fetch_streets_for_city", new_callable=AsyncMock, return_value=mock_streets), \
         patch("rcf.scanner.address_discovery.repository") as mock_repo:
        mock_repo.upsert_property.return_value = {"id": "x"}

        city = CityRecord(code="5000", name_he="תל אביב")
        result = await ingest_city(city, max_house_number=3, step=1, batch_size=100)

    assert result["city"] == "תל אביב"
    assert result["streets"] == 1
    assert result["inserted"] == 3
