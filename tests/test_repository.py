"""Tests for the DB repository module (mocked psycopg)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from rcf.db.models import (
    CaseClaimCreate, LawyerCreate, OwnerCreate,
    PermitCreate, PropertyCreate, RefundCaseCreate,
)

FAKE_PROPERTY = {"id": "test-uuid", "address_text": "הרצל 10", "city": "תל אביב"}
FAKE_PERMIT = {"id": "permit-uuid", "permit_number": "101-123", "property_id": "test-uuid"}
FAKE_CASE = {
    "id": "case-uuid", "classification": "authority_rejected",
    "is_eligible": True, "estimated_refund": 25000, "city": "תל אביב",
    "address_text": "הרצל 10", "permit_number": "101-123",
    "source_url": "https://example.com", "created_at": "2026-01-01",
    "status": "detected", "block": "6134", "plot": "78",
    "decision_date": "2025-01-01", "decision_type": "rejected",
}
FAKE_LAWYER = {
    "id": "lawyer-uuid", "full_name": "עו״ד ישראל",
    "email": "lawyer@example.com", "municipalities": ["תל אביב"],
}
FAKE_OWNER = {"id": "owner-uuid", "full_name": "בעל נכס", "email": "owner@example.com"}
FAKE_CLAIM = {
    "id": "claim-uuid", "refund_case_id": "case-uuid",
    "lawyer_id": "lawyer-uuid", "owner_id": "owner-uuid",
    "classification": "authority_rejected", "estimated_refund": 25000,
    "case_status": "claimed", "city": "תל אביב", "address_text": "הרצל 10",
    "lawyer_name": "עו״ד ישראל", "lawyer_email": "lawyer@example.com",
}


def _mock_execute(query, params=None):
    return [FAKE_PROPERTY]


def _mock_execute_one(query, params=None):
    return FAKE_PROPERTY


# --- Properties ---

@patch("rcf.db.repository.execute_one", _mock_execute_one)
@patch("rcf.db.repository.execute", _mock_execute)
def test_upsert_property():
    from rcf.db.repository import upsert_property
    result = upsert_property(PropertyCreate(address_text="הרצל 10", city="תל אביב"))
    assert result["id"] == "test-uuid"


@patch("rcf.db.repository.execute", _mock_execute)
def test_get_pending_properties_with_city():
    from rcf.db.repository import get_pending_properties
    rows = get_pending_properties(city="תל אביב", limit=10)
    assert len(rows) == 1


@patch("rcf.db.repository.execute", _mock_execute)
def test_get_pending_properties_no_city():
    from rcf.db.repository import get_pending_properties
    rows = get_pending_properties(limit=10)
    assert len(rows) == 1


@patch("rcf.db.repository.execute")
def test_update_property_cadastral(mock_exec):
    from rcf.db.repository import update_property_cadastral
    update_property_cadastral("id1", "6134", "78", "mun-1", 32.08, 34.78)
    mock_exec.assert_called_once()
    assert mock_exec.call_args[0][1]["block"] == "6134"
    assert mock_exec.call_args[0][1]["plot"] == "78"


@patch("rcf.db.repository.execute")
def test_mark_property_scanned(mock_exec):
    from rcf.db.repository import mark_property_scanned
    mark_property_scanned(uuid4())
    assert "scanned" in mock_exec.call_args[0][0]


@patch("rcf.db.repository.execute")
def test_mark_property_error(mock_exec):
    from rcf.db.repository import mark_property_error
    mark_property_error(uuid4())
    assert "error" in mock_exec.call_args[0][0]


# --- Permits ---

@patch("rcf.db.repository.execute_one", return_value=FAKE_PERMIT)
def test_insert_permit(mock_exec_one):
    from rcf.db.repository import insert_permit
    result = insert_permit(PermitCreate(property_id=uuid4(), permit_number="101-123", decision_type="rejected"))
    assert result["permit_number"] == "101-123"


@patch("rcf.db.repository.execute")
def test_update_permit_decision_text(mock_exec):
    from rcf.db.repository import update_permit_decision_text
    update_permit_decision_text("permit-uuid", "decision text")
    assert mock_exec.call_args[0][1]["text"] == "decision text"


@patch("rcf.db.repository.execute", return_value=[FAKE_PERMIT])
def test_get_permits_for_property(mock_exec):
    from rcf.db.repository import get_permits_for_property
    assert len(get_permits_for_property(uuid4())) == 1


# --- Refund Cases ---

@patch("rcf.db.repository.execute_one", return_value=FAKE_CASE)
def test_insert_refund_case(mock_exec_one):
    from rcf.db.repository import insert_refund_case
    result = insert_refund_case(RefundCaseCreate(
        permit_id=uuid4(), property_id=uuid4(),
        classification="authority_rejected", confidence_score=0.9,
        is_eligible=True, estimated_refund=25000,
    ))
    assert result["classification"] == "authority_rejected"


@patch("rcf.db.repository.execute")
def test_update_refund_case_status(mock_exec):
    from rcf.db.repository import update_refund_case_status
    update_refund_case_status(uuid4(), "claimed")
    assert mock_exec.call_args[0][1]["status"] == "claimed"


@patch("rcf.db.repository.execute", return_value=[FAKE_CASE])
def test_get_eligible_cases_no_filter(mock_exec):
    from rcf.db.repository import get_eligible_cases
    rows = get_eligible_cases()
    assert len(rows) == 1
    assert "rc.is_eligible = TRUE" in mock_exec.call_args[0][0]


@patch("rcf.db.repository.execute", return_value=[FAKE_CASE])
def test_get_eligible_cases_city_filter(mock_exec):
    from rcf.db.repository import get_eligible_cases
    get_eligible_cases(city="תל אביב")
    assert "p.city = %(city)s" in mock_exec.call_args[0][0]


@patch("rcf.db.repository.execute", return_value=[FAKE_CASE])
def test_get_eligible_cases_status_filter(mock_exec):
    from rcf.db.repository import get_eligible_cases
    get_eligible_cases(status="detected")
    assert "rc.status = %(status)s" in mock_exec.call_args[0][0]


@patch("rcf.db.repository.execute", return_value=[FAKE_CASE])
def test_get_eligible_cases_both_filters(mock_exec):
    from rcf.db.repository import get_eligible_cases
    get_eligible_cases(city="x", status="y")
    q = mock_exec.call_args[0][0]
    assert "p.city" in q and "rc.status" in q


@patch("rcf.db.repository.execute_one", return_value=FAKE_CASE)
def test_get_refund_case(mock_exec_one):
    from rcf.db.repository import get_refund_case
    assert get_refund_case(uuid4())["classification"] == "authority_rejected"


@patch("rcf.db.repository.execute_one", return_value=None)
def test_get_refund_case_not_found(mock_exec_one):
    from rcf.db.repository import get_refund_case
    assert get_refund_case(uuid4()) is None


# --- Lawyers ---

@patch("rcf.db.repository.execute_one", return_value=FAKE_LAWYER)
def test_insert_lawyer(mock_exec_one):
    from rcf.db.repository import insert_lawyer
    result = insert_lawyer(LawyerCreate(full_name="x", email="x@x.com", municipalities=[]))
    assert result["email"] == "lawyer@example.com"


@patch("rcf.db.repository.execute", return_value=[FAKE_LAWYER])
def test_get_lawyers_for_municipality(mock_exec):
    from rcf.db.repository import get_lawyers_for_municipality
    assert len(get_lawyers_for_municipality("תל אביב")) == 1


@patch("rcf.db.repository.execute_one", return_value=FAKE_LAWYER)
def test_get_lawyer(mock_exec_one):
    from rcf.db.repository import get_lawyer
    assert get_lawyer(uuid4()) is not None


@patch("rcf.db.repository.execute_one", return_value=None)
def test_get_lawyer_not_found(mock_exec_one):
    from rcf.db.repository import get_lawyer
    assert get_lawyer(uuid4()) is None


# --- Owners ---

@patch("rcf.db.repository.execute_one", return_value=FAKE_OWNER)
def test_insert_owner(mock_exec_one):
    from rcf.db.repository import insert_owner
    result = insert_owner(OwnerCreate(full_name="x", email="x@x.com"))
    assert result["email"] == "owner@example.com"


@patch("rcf.db.repository.execute_one", return_value=FAKE_OWNER)
def test_get_owner(mock_exec_one):
    from rcf.db.repository import get_owner
    assert get_owner(uuid4()) is not None


@patch("rcf.db.repository.execute_one", return_value=None)
def test_get_owner_not_found(mock_exec_one):
    from rcf.db.repository import get_owner
    assert get_owner(uuid4()) is None


# --- Case Claims ---

@patch("rcf.db.repository.execute_one", return_value=FAKE_CLAIM)
def test_insert_case_claim(mock_exec_one):
    from rcf.db.repository import insert_case_claim
    result = insert_case_claim(CaseClaimCreate(refund_case_id=uuid4(), lawyer_id=uuid4(), owner_id=uuid4()))
    assert result["lawyer_id"] == "lawyer-uuid"


@patch("rcf.db.repository.execute", return_value=[FAKE_CLAIM])
def test_get_claims_for_lawyer(mock_exec):
    from rcf.db.repository import get_claims_for_lawyer
    assert len(get_claims_for_lawyer(uuid4())) == 1


@patch("rcf.db.repository.execute", return_value=[FAKE_CLAIM])
def test_get_claims_for_owner(mock_exec):
    from rcf.db.repository import get_claims_for_owner
    assert len(get_claims_for_owner(uuid4())) == 1
