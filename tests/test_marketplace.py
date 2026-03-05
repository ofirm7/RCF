"""Tests for the marketplace matching and notification modules."""

from __future__ import annotations

import logging
from unittest.mock import patch

from rcf.marketplace.matching import find_matching_lawyers, match_case_to_lawyers
from rcf.marketplace.notifications import notify_lawyer_new_case, notify_owner_refund_found


# --- find_matching_lawyers ---

@patch("rcf.marketplace.matching.repository")
def test_find_matching_lawyers_empty(mock_repo):
    mock_repo.get_lawyers_for_municipality.return_value = []
    result = find_matching_lawyers("nonexistent city")
    assert result == []


@patch("rcf.marketplace.matching.repository")
def test_find_matching_lawyers_ranking(mock_repo):
    mock_repo.get_lawyers_for_municipality.return_value = [
        {"id": "1", "is_verified": False, "subscription": "free"},
        {"id": "2", "is_verified": True, "subscription": "premium"},
        {"id": "3", "is_verified": True, "subscription": "free"},
    ]
    result = find_matching_lawyers("תל אביב")
    # Verified first, then premium among verified
    assert result[0]["id"] == "2"
    assert result[1]["id"] == "3"
    assert result[2]["id"] == "1"


@patch("rcf.marketplace.matching.repository")
def test_find_matching_lawyers_limit(mock_repo):
    mock_repo.get_lawyers_for_municipality.return_value = [
        {"id": str(i), "is_verified": True, "subscription": "free"} for i in range(10)
    ]
    result = find_matching_lawyers("חיפה", limit=3)
    assert len(result) == 3


# --- match_case_to_lawyers ---

@patch("rcf.marketplace.matching.repository")
def test_match_case_to_lawyers_with_city(mock_repo):
    mock_repo.get_lawyers_for_municipality.return_value = [
        {"id": "1", "is_verified": True, "subscription": "free"},
    ]
    case = {"id": "case-1", "properties": {"city": "תל אביב"}}
    result = match_case_to_lawyers(case)
    assert len(result) == 1


@patch("rcf.marketplace.matching.repository")
def test_match_case_no_city(mock_repo):
    case = {"id": "case-1", "properties": {}}
    result = match_case_to_lawyers(case)
    assert result == []


@patch("rcf.marketplace.matching.repository")
def test_match_case_no_properties(mock_repo):
    case = {"id": "case-1"}
    result = match_case_to_lawyers(case)
    assert result == []


# --- Notifications (logging stubs) ---

def test_notify_lawyer_with_amount(caplog):
    with caplog.at_level(logging.INFO):
        notify_lawyer_new_case("a@b.com", "עו״ד כהן", "תל אביב", 25000, "case-1")
    assert "25,000" in caplog.text


def test_notify_lawyer_no_amount(caplog):
    with caplog.at_level(logging.INFO):
        notify_lawyer_new_case("a@b.com", "עו״ד כהן", "חיפה", None, "case-2")
    assert "unknown" in caplog.text


def test_notify_owner_with_amount(caplog):
    with caplog.at_level(logging.INFO):
        notify_owner_refund_found("o@b.com", "ישראל", "הרצל 10", 30000)
    assert "30,000" in caplog.text


def test_notify_owner_no_name(caplog):
    with caplog.at_level(logging.INFO):
        notify_owner_refund_found("o@b.com", None, "הרצל 10", None)
    assert "Owner" in caplog.text
    assert "unknown amount" in caplog.text
