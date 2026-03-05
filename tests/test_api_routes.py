"""Tests for FastAPI API routes using TestClient."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from rcf.api.app import app

client = TestClient(app)

FAKE_CASE = {
    "id": str(uuid4()), "classification": "authority_rejected",
    "is_eligible": True, "estimated_refund": 25000, "city": "תל אביב",
    "address_text": "הרצל 10", "permit_number": "101-123",
    "source_url": "https://example.com", "created_at": "2026-01-01",
    "status": "detected",
}
FAKE_CASE_DETAIL = {
    **FAKE_CASE, "block": "6134", "plot": "78",
    "decision_date": "2025-01-01", "decision_type": "rejected",
}
FAKE_LAWYER = {
    "id": str(uuid4()), "full_name": "עו״ד כהן",
    "email": "lawyer@example.com", "phone": "050-1234567",
}
FAKE_OWNER = {
    "id": str(uuid4()), "full_name": "בעל נכס",
    "email": "owner@example.com",
}
FAKE_CLAIM = {
    "id": str(uuid4()), "refund_case_id": FAKE_CASE["id"],
    "lawyer_id": FAKE_LAWYER["id"], "owner_id": FAKE_OWNER["id"],
}
FAKE_PROPERTY_ROW = {
    "id": str(uuid4()), "address_text": "הרצל 10", "city": "תל אביב",
    "case_id": None, "classification": None,
    "is_eligible": None, "estimated_refund": None, "case_status": None,
    "confidence_score": None,
}


# --- Health ---

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Cases ---

@patch("rcf.api.routes.cases.repository")
def test_list_cases(mock_repo):
    mock_repo.get_eligible_cases.return_value = [FAKE_CASE]
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["classification"] == "authority_rejected"


@patch("rcf.api.routes.cases.repository")
def test_list_cases_with_filters(mock_repo):
    mock_repo.get_eligible_cases.return_value = []
    resp = client.get("/api/cases?city=תל אביב&status=detected&limit=10&offset=5")
    assert resp.status_code == 200
    mock_repo.get_eligible_cases.assert_called_once_with(
        city="תל אביב", status="detected", limit=10, offset=5
    )


@patch("rcf.api.routes.cases.repository")
def test_get_case_found(mock_repo):
    case_id = FAKE_CASE["id"]
    mock_repo.get_refund_case.return_value = FAKE_CASE_DETAIL
    resp = client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == case_id


@patch("rcf.api.routes.cases.repository")
def test_get_case_not_found(mock_repo):
    mock_repo.get_refund_case.return_value = None
    resp = client.get(f"/api/cases/{uuid4()}")
    assert resp.status_code == 404


@patch("rcf.api.routes.cases.repository")
def test_claim_case_success(mock_repo):
    case_id = FAKE_CASE["id"]
    lawyer_id = FAKE_LAWYER["id"]
    mock_repo.get_refund_case.return_value = {**FAKE_CASE_DETAIL, "status": "detected"}
    mock_repo.insert_case_claim.return_value = FAKE_CLAIM
    resp = client.post(f"/api/cases/{case_id}/claim?lawyer_id={lawyer_id}")
    assert resp.status_code == 200
    mock_repo.update_refund_case_status.assert_called_once()


@patch("rcf.api.routes.cases.repository")
def test_claim_case_not_found(mock_repo):
    mock_repo.get_refund_case.return_value = None
    resp = client.post(f"/api/cases/{uuid4()}/claim?lawyer_id={uuid4()}")
    assert resp.status_code == 404


@patch("rcf.api.routes.cases.repository")
def test_claim_case_not_claimable(mock_repo):
    case_id = FAKE_CASE["id"]
    mock_repo.get_refund_case.return_value = {**FAKE_CASE_DETAIL, "status": "claimed"}
    resp = client.post(f"/api/cases/{case_id}/claim?lawyer_id={uuid4()}")
    assert resp.status_code == 400


# --- Properties ---

@patch("rcf.api.routes.properties.execute", return_value=[FAKE_PROPERTY_ROW])
def test_check_property_found(mock_exec):
    resp = client.get("/api/properties/הרצל")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@patch("rcf.api.routes.properties.execute", return_value=[])
def test_check_property_not_found(mock_exec):
    resp = client.get("/api/properties/nonexistent")
    assert resp.status_code == 404


# --- Lawyers ---

@patch("rcf.api.routes.lawyers.repository")
def test_register_lawyer(mock_repo):
    mock_repo.insert_lawyer.return_value = FAKE_LAWYER
    resp = client.post("/api/lawyers", json={
        "full_name": "עו״ד כהן", "email": "lawyer@example.com",
        "municipalities": ["תל אביב"],
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "lawyer@example.com"


@patch("rcf.api.routes.lawyers.repository")
def test_get_lawyer_found(mock_repo):
    lawyer_id = FAKE_LAWYER["id"]
    mock_repo.get_lawyer.return_value = FAKE_LAWYER
    resp = client.get(f"/api/lawyers/{lawyer_id}")
    assert resp.status_code == 200


@patch("rcf.api.routes.lawyers.repository")
def test_get_lawyer_not_found(mock_repo):
    mock_repo.get_lawyer.return_value = None
    resp = client.get(f"/api/lawyers/{uuid4()}")
    assert resp.status_code == 404


@patch("rcf.api.routes.lawyers.repository")
def test_lawyer_cases(mock_repo):
    lawyer_id = FAKE_LAWYER["id"]
    mock_repo.get_claims_for_lawyer.return_value = [FAKE_CLAIM]
    resp = client.get(f"/api/lawyers/{lawyer_id}/cases")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# --- Owners ---

@patch("rcf.api.routes.owners.repository")
def test_register_owner(mock_repo):
    mock_repo.insert_owner.return_value = FAKE_OWNER
    resp = client.post("/api/owners", json={
        "full_name": "בעל נכס", "email": "owner@example.com",
    })
    assert resp.status_code == 200


@patch("rcf.api.routes.owners.repository")
def test_get_owner_found(mock_repo):
    owner_id = FAKE_OWNER["id"]
    mock_repo.get_owner.return_value = FAKE_OWNER
    resp = client.get(f"/api/owners/{owner_id}")
    assert resp.status_code == 200


@patch("rcf.api.routes.owners.repository")
def test_get_owner_not_found(mock_repo):
    mock_repo.get_owner.return_value = None
    resp = client.get(f"/api/owners/{uuid4()}")
    assert resp.status_code == 404


@patch("rcf.api.routes.owners.repository")
def test_owner_cases(mock_repo):
    owner_id = FAKE_OWNER["id"]
    mock_repo.get_claims_for_owner.return_value = []
    resp = client.get(f"/api/owners/{owner_id}/cases")
    assert resp.status_code == 200
    assert resp.json() == []
