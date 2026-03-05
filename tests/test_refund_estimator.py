"""Tests for the refund estimator module."""

from datetime import date

from rcf.scanner.refund_estimator import _MAX_ESTIMATE, _MIN_ESTIMATE, estimate


def test_estimate_with_area():
    result = estimate(permit_type="residential", building_area_sqm=200.0)
    # 200 * 130 = 26,000 base
    assert result >= 26_000


def test_estimate_without_area():
    result = estimate()
    assert result == 25_000  # fallback median


def test_estimate_clamped_low():
    result = estimate(building_area_sqm=1.0)
    # 1 * 130 = 130, but clamped to min
    assert result == _MIN_ESTIMATE


def test_estimate_clamped_high():
    result = estimate(building_area_sqm=100_000.0)
    assert result == _MAX_ESTIMATE


def test_estimate_with_inflation():
    old_date = date(2019, 1, 1)
    without = estimate(building_area_sqm=200.0)
    with_date = estimate(building_area_sqm=200.0, decision_date=old_date)
    # Older decision should yield higher estimate due to CPI adjustment
    assert with_date > without
