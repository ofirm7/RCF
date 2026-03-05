"""Tests for the fee scanner (automatic fee analysis pipeline)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcf.scanner.fee_scanner import _estimate_fee_year, _map_iplan_areas, scan_city_fees


# --- _map_iplan_areas ---

def test_map_areas_residential():
    attrs = {
        "quantity_delta_105": 500.0,
        "quantity_delta_110": 0.0,
        "quantity_delta_125": 50.0,
    }
    res_sqm, svc_sqm, area_type = _map_iplan_areas(attrs)
    assert res_sqm == 500.0
    assert svc_sqm == 50.0
    assert area_type == "residential"


def test_map_areas_commercial():
    attrs = {
        "quantity_delta_105": 100.0,
        "quantity_delta_110": 800.0,
        "quantity_delta_125": 20.0,
    }
    res_sqm, svc_sqm, area_type = _map_iplan_areas(attrs)
    assert res_sqm == 800.0
    assert svc_sqm == 20.0
    assert area_type == "commercial"


def test_map_areas_fallback_pq_fields():
    attrs = {
        "quantity_delta_105": 0.0,
        "quantity_delta_110": 0.0,
        "quantity_delta_125": 0.0,
        "pq_authorised_quantity_105": 1200.0,
        "pq_authorised_quantity_110": 0.0,
    }
    res_sqm, svc_sqm, area_type = _map_iplan_areas(attrs)
    assert res_sqm == 1200.0
    assert area_type == "residential"


def test_map_areas_fallback_dunam():
    attrs = {
        "quantity_delta_105": 0.0,
        "quantity_delta_110": 0.0,
        "quantity_delta_125": 0.0,
        "pq_authorised_quantity_105": 0.0,
        "pl_area_dunam": 2.0,
        "pl_landuse_string": "מגורים",
    }
    res_sqm, svc_sqm, area_type = _map_iplan_areas(attrs)
    # 2 dunam * 1000 * 0.5 = 1000 sqm
    assert res_sqm == 1000.0
    assert svc_sqm == 200.0  # 2 * 1000 * 0.1
    assert area_type == "residential"


def test_map_areas_fallback_dunam_commercial():
    attrs = {
        "quantity_delta_105": 0.0,
        "quantity_delta_110": 0.0,
        "quantity_delta_125": 0.0,
        "pq_authorised_quantity_105": 0.0,
        "pl_area_dunam": 1.0,
        "pl_landuse_string": "מסחר ומשרדים",
    }
    _, _, area_type = _map_iplan_areas(attrs)
    assert area_type == "commercial"


def test_map_areas_all_zeros():
    attrs = {
        "quantity_delta_105": 0.0,
        "quantity_delta_110": 0.0,
        "quantity_delta_125": 0.0,
        "pq_authorised_quantity_105": 0.0,
        "pl_area_dunam": 0.0,
    }
    res_sqm, svc_sqm, _ = _map_iplan_areas(attrs)
    assert res_sqm == 0.0
    assert svc_sqm == 0.0


def test_map_areas_negative_deltas():
    """Negative deltas (reducing building rights) should be clamped to 0."""
    attrs = {
        "quantity_delta_105": -500.0,
        "quantity_delta_110": 0.0,
        "quantity_delta_125": -100.0,
    }
    res_sqm, svc_sqm, _ = _map_iplan_areas(attrs)
    assert res_sqm == 0.0
    assert svc_sqm == 0.0


# --- _estimate_fee_year ---

def test_estimate_fee_year_from_date():
    attrs = {"pl_date7": 1704067200000}  # 2024-01-01
    assert _estimate_fee_year(attrs) == 2024


def test_estimate_fee_year_fallback_receiving():
    attrs = {"receiving_date": 1609459200000}  # 2021-01-01
    assert _estimate_fee_year(attrs) == 2021


def test_estimate_fee_year_no_dates():
    attrs = {}
    year = _estimate_fee_year(attrs)
    # Should return current year
    assert year >= 2024


# --- scan_city_fees (mocked) ---

@pytest.mark.asyncio
async def test_scan_city_fees_processes_plans():
    mock_plans = [
        {
            "pl_number": "304-TEST-001",
            "pl_name": "Test Plan",
            "plan_county_name": "חיפה",
            "internet_short_status": "אישור תכנית",
            "pl_landuse_string": "מגורים",
            "quantity_delta_105": 200.0,
            "quantity_delta_110": 0.0,
            "quantity_delta_120": 0.0,
            "quantity_delta_125": 30.0,
            "pq_authorised_quantity_105": 0.0,
            "pq_authorised_quantity_110": 0.0,
            "pl_area_dunam": 0.5,
            "pl_url": "https://mavat.iplan.gov.il/SV4/1/12345/310",
            "mp_id": 12345,
            "pl_date7": 1704067200000,
            "receiving_date": 1704067200000,
            "ja_concat": "ועדה מקומית חיפה",
            "lat": 32.8,
            "lng": 34.99,
            "city": "חיפה",
            "decision_date": None,
            "application_date": None,
        },
    ]

    with patch("rcf.scanner.fee_scanner.fetch_plans_for_city", new_callable=AsyncMock) as mock_fetch, \
         patch("rcf.scanner.fee_scanner.repository") as mock_repo:

        mock_fetch.return_value = mock_plans

        mock_repo.upsert_property.return_value = {"id": "00000000-0000-0000-0000-000000000001"}
        mock_repo.insert_permit.return_value = {"id": "00000000-0000-0000-0000-000000000002"}
        mock_repo.upsert_fee_analysis.return_value = {"id": "00000000-0000-0000-0000-000000000003"}

        result = await scan_city_fees("חיפה")

    assert result["total"] == 1
    assert result["processed"] == 1
    assert result["skipped"] == 0

    # Verify upsert_fee_analysis was called with correct data
    call_args = mock_repo.upsert_fee_analysis.call_args
    fa_data = call_args[0][0]
    assert fa_data.permit_residential_sqm == 200.0
    assert fa_data.permit_service_sqm == 30.0
    assert fa_data.scan_source == "iplan_auto"
    assert fa_data.status == "pre_computed"
    assert fa_data.plan_number == "304-TEST-001"


@pytest.mark.asyncio
async def test_scan_city_fees_skips_zero_area():
    mock_plans = [
        {
            "pl_number": "304-EMPTY",
            "pl_name": "Empty Plan",
            "plan_county_name": "חיפה",
            "quantity_delta_105": 0.0,
            "quantity_delta_110": 0.0,
            "quantity_delta_125": 0.0,
            "pq_authorised_quantity_105": 0.0,
            "pq_authorised_quantity_110": 0.0,
            "pl_area_dunam": 0.0,
            "pl_date7": None,
            "receiving_date": None,
            "lat": None,
            "lng": None,
            "city": "חיפה",
            "decision_date": None,
            "application_date": None,
        },
    ]

    with patch("rcf.scanner.fee_scanner.fetch_plans_for_city", new_callable=AsyncMock) as mock_fetch, \
         patch("rcf.scanner.fee_scanner.repository") as mock_repo:

        mock_fetch.return_value = mock_plans
        result = await scan_city_fees("חיפה")

    assert result["total"] == 1
    assert result["processed"] == 0
    assert result["skipped"] == 1
    mock_repo.upsert_fee_analysis.assert_not_called()
