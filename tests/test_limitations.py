"""Tests for the statute of limitations module."""

from datetime import date, timedelta

from rcf.scanner.limitations import expiry_date, is_urgent, is_within_window


def test_expiry_date():
    d = date(2020, 6, 15)
    assert expiry_date(d) == date(2027, 6, 15)


def test_within_window_recent():
    recent = date.today() - timedelta(days=365)
    assert is_within_window(recent) is True


def test_within_window_expired():
    old = date.today() - timedelta(days=365 * 8)
    assert is_within_window(old) is False


def test_within_window_none():
    assert is_within_window(None) is False


def test_is_urgent():
    # Expires in 3 months → urgent
    almost_expired = date.today() - timedelta(days=365 * 7 - 90)
    assert is_urgent(almost_expired) is True


def test_not_urgent():
    recent = date.today() - timedelta(days=365)
    assert is_urgent(recent) is False
