"""Tests for the permit fetcher module (iPlan ArcGIS)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rcf.scanner.iplan_client import epoch_to_date as _epoch_to_date
from rcf.scanner.permit_fetcher import _classify_status


# --- _classify_status ---

def test_classify_status_rejected_keyword():
    assert _classify_status("דחיית תכנית", "") == "rejected"


def test_classify_status_rejected_in_station():
    assert _classify_status("", "התכנית נדחתה") == "rejected"


def test_classify_status_withdrawn_bitul():
    assert _classify_status("ביטול תכנית", "") == "withdrawn"


def test_classify_status_withdrawn_nimshakh():
    assert _classify_status("נמשך", "") == "withdrawn"


def test_classify_status_withdrawn_butal():
    assert _classify_status("", "בוטל") == "withdrawn"


def test_classify_status_none_for_approved():
    assert _classify_status("אושרה", "תקפה") is None


def test_classify_status_none_for_empty():
    assert _classify_status("", "") is None


# --- _epoch_to_date ---

def test_epoch_to_date_valid():
    # 2020-01-01 00:00:00 UTC = 1577836800000 ms
    result = _epoch_to_date(1577836800000)
    assert isinstance(result, date)
    assert result.year == 2020


def test_epoch_to_date_none():
    assert _epoch_to_date(None) is None


def test_epoch_to_date_zero():
    assert _epoch_to_date(0) is None


def test_epoch_to_date_invalid():
    assert _epoch_to_date(-99999999999999999) is None


# --- fetch_permits ---

@pytest.mark.asyncio
async def test_fetch_permits_no_features():
    """Returns empty list when iPlan has no features at location."""
    with patch("rcf.scanner.permit_fetcher.query_plans", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        from rcf.scanner.permit_fetcher import fetch_permits
        result = await fetch_permits(32.08, 34.78, str(uuid4()))

    assert result == []


@pytest.mark.asyncio
async def test_fetch_permits_with_rejected_plan():
    """Returns PermitCreate for rejected plans."""
    features = [
        {
            "attributes": {
                "pl_number": "101-999",
                "pl_name": "test plan",
                "station_desc": "",
                "internet_short_status": "דחיית תכנית",
                "plan_county_name": "תל אביב",
                "pl_date7": 1577836800000,
                "pl_rejection_date": None,
                "pl_url": "https://example.com/plan",
                "receiving_date": 1546300800000,
                "ja_concat": "ועדה מקומית",
            }
        },
        {
            "attributes": {
                "pl_number": "101-888",
                "internet_short_status": "אושרה",
                "station_desc": "תקפה",
            }
        },
    ]

    prop_id = str(uuid4())
    with patch("rcf.scanner.permit_fetcher.query_plans", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = features
        from rcf.scanner.permit_fetcher import fetch_permits
        result = await fetch_permits(32.08, 34.78, prop_id)

    assert len(result) == 1
    assert result[0].permit_number == "101-999"
    assert result[0].decision_type == "rejected"
    assert str(result[0].property_id) == prop_id
