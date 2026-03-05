"""Tests for the fee analyzer and fee rates modules."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from rcf.scanner.fee_analyzer import FeeComparisonResult, analyze_fees
from rcf.scanner.fee_rates import compute_correct_fee, get_all_rates, get_rate


# --- fee_rates ---

def test_get_rate_known_year():
    rate = get_rate(2024, "residential")
    assert rate == 32.0


def test_get_rate_service():
    rate = get_rate(2024, "service")
    assert rate == 16.0


def test_get_rate_cpi_adjusted():
    rate = get_rate(2025, "residential")
    # 32.0 * 1.03 = 32.96
    assert rate == pytest.approx(32.96, abs=0.01)


def test_get_rate_unknown_year_extrapolates():
    rate = get_rate(2030, "residential")
    # 32.0 * (1.03 ** 6) ≈ 38.20
    assert rate > 37
    assert rate < 40


def test_get_rate_unknown_type_defaults_to_residential():
    rate = get_rate(2024, "unknown_type")
    assert rate == 32.0


def test_get_all_rates():
    rates = get_all_rates(2024)
    assert "residential" in rates
    assert "service" in rates
    assert "parking_open" in rates
    assert rates["parking_open"] == 0.0


def test_compute_correct_fee_basic():
    fee = compute_correct_fee(100.0, 50.0, 2024)
    # (100 * 32) + (50 * 16) = 3200 + 800 = 4000 NIS = 400000 agorot
    assert fee == 400000


def test_compute_correct_fee_zero_area():
    fee = compute_correct_fee(0.0, 0.0, 2024)
    assert fee == 0


def test_compute_correct_fee_commercial():
    fee = compute_correct_fee(100.0, 0.0, 2024, residential_type="commercial")
    # 100 * 40 = 4000 NIS = 400000 agorot
    assert fee == 400000


# --- fee_analyzer ---

def test_analyze_fees_overcharge_detected():
    result = analyze_fees(
        invoice_total_agorot=600000,  # 6000 NIS
        permit_residential_sqm=100.0,
        permit_service_sqm=50.0,
        fee_year=2024,
    )
    # Correct = (100*32) + (50*16) = 4000 NIS = 400000 agorot
    assert isinstance(result, FeeComparisonResult)
    assert result.is_overcharged is True
    assert result.correct_fee == 400000
    assert result.overcharge_amount == 200000  # 2000 NIS


def test_analyze_fees_no_overcharge():
    result = analyze_fees(
        invoice_total_agorot=300000,  # 3000 NIS
        permit_residential_sqm=100.0,
        permit_service_sqm=50.0,
        fee_year=2024,
    )
    # Correct = 4000 NIS > 3000 NIS → no overcharge
    assert result.is_overcharged is False
    assert result.overcharge_amount == 0


def test_analyze_fees_exact_match():
    result = analyze_fees(
        invoice_total_agorot=400000,
        permit_residential_sqm=100.0,
        permit_service_sqm=50.0,
        fee_year=2024,
    )
    assert result.is_overcharged is False
    assert result.overcharge_amount == 0


def test_analyze_fees_with_previously_paid():
    result = analyze_fees(
        invoice_total_agorot=400000,
        permit_residential_sqm=100.0,
        permit_service_sqm=50.0,
        fee_year=2024,
        previously_paid_sqm=50.0,
    )
    # Net residential = 50 sqm → correct = (50*32)+(50*16) = 2400 NIS = 240000
    assert result.correct_fee == 240000
    assert result.is_overcharged is True
    assert result.overcharge_amount == 160000


def test_analyze_fees_classification_mismatch():
    result = analyze_fees(
        invoice_total_agorot=500000,
        invoice_rate_per_sqm=50.0,  # municipality used 50
        permit_residential_sqm=100.0,
        permit_service_sqm=0.0,
        fee_year=2024,
    )
    assert "classification_mismatch" in result.breakdown


def test_analyze_fees_breakdown_contains_rates():
    result = analyze_fees(
        invoice_total_agorot=500000,
        permit_residential_sqm=100.0,
        permit_service_sqm=50.0,
        fee_year=2024,
    )
    assert "residential_rate" in result.breakdown
    assert "service_rate" in result.breakdown
    assert "fee_year" in result.breakdown


# --- document_extractor (mocked) ---

@pytest.mark.asyncio
async def test_extract_fee_invoice_no_api_key():
    with patch("rcf.scanner.document_extractor.get_config") as mock_cfg:
        mock_cfg.return_value.anthropic_api_key = None
        from rcf.scanner.document_extractor import extract_fee_invoice
        result = await extract_fee_invoice(b"fake pdf")
    assert result is None


@pytest.mark.asyncio
async def test_extract_permit_areas_no_api_key():
    with patch("rcf.scanner.document_extractor.get_config") as mock_cfg:
        mock_cfg.return_value.anthropic_api_key = None
        from rcf.scanner.document_extractor import extract_permit_areas
        result = await extract_permit_areas(b"fake pdf")
    assert result is None
