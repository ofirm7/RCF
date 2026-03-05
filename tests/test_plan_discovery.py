"""Tests for the plan discovery module (iPlan ArcGIS rejected plan queries)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcf.scanner.plan_discovery import _centroid_from_geometry, _epoch_to_date


# --- _centroid_from_geometry ---

def test_centroid_simple_square():
    geometry = {
        "rings": [
            [[34.0, 32.0], [35.0, 32.0], [35.0, 33.0], [34.0, 33.0], [34.0, 32.0]]
        ]
    }
    lat, lng = _centroid_from_geometry(geometry)
    assert abs(lat - 32.4) < 0.5
    assert abs(lng - 34.4) < 0.5


def test_centroid_empty_rings():
    lat, lng = _centroid_from_geometry({"rings": []})
    assert lat is None
    assert lng is None


def test_centroid_no_rings():
    lat, lng = _centroid_from_geometry({})
    assert lat is None
    assert lng is None


def test_centroid_multiple_rings():
    geometry = {
        "rings": [
            [[34.0, 32.0], [35.0, 32.0]],
            [[36.0, 33.0], [37.0, 33.0]],
        ]
    }
    lat, lng = _centroid_from_geometry(geometry)
    assert lat is not None
    assert lng is not None


# --- _epoch_to_date ---

def test_epoch_to_date_valid():
    result = _epoch_to_date(1577836800000)
    assert isinstance(result, date)
    assert result.year == 2020


def test_epoch_to_date_none():
    assert _epoch_to_date(None) is None


def test_epoch_to_date_zero():
    assert _epoch_to_date(0) is None


def test_epoch_to_date_invalid():
    assert _epoch_to_date(-99999999999999999) is None


# --- fetch_rejected_plans ---

@pytest.mark.asyncio
async def test_fetch_rejected_plans_returns_plans():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "features": [
            {
                "attributes": {
                    "pl_number": "101-999",
                    "pl_name": "test plan",
                    "station_desc": "rejected",
                    "internet_short_status": "דחיית תכנית",
                    "plan_county_name": "תל אביב",
                    "pl_date7": 1577836800000,
                    "pl_rejection_date": None,
                    "pl_url": "https://example.com/plan",
                    "receiving_date": 1546300800000,
                    "ja_concat": "ועדה",
                },
                "geometry": {
                    "rings": [[[34.78, 32.08], [34.79, 32.08], [34.79, 32.09], [34.78, 32.09]]]
                },
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rcf.scanner.plan_discovery.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.plan_discovery import fetch_rejected_plans
        plans = await fetch_rejected_plans()

    assert len(plans) == 1
    assert plans[0]["pl_number"] == "101-999"
    assert plans[0]["city"] == "תל אביב"
    assert plans[0]["lat"] is not None
    assert plans[0]["lng"] is not None


@pytest.mark.asyncio
async def test_fetch_rejected_plans_empty():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": []}
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rcf.scanner.plan_discovery.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.plan_discovery import fetch_rejected_plans
        plans = await fetch_rejected_plans(city_filter="nonexistent")

    assert plans == []


@pytest.mark.asyncio
async def test_fetch_rejected_plans_city_filter_in_query():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": []}
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rcf.scanner.plan_discovery.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.plan_discovery import fetch_rejected_plans
        await fetch_rejected_plans(city_filter="ירושלים")

    call_args = mock_client.get.call_args
    where = call_args[1]["params"]["where"] if "params" in call_args[1] else call_args[0][1]["where"]
    assert "ירושלים" in where
