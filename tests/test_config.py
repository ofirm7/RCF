"""Tests for configuration, Pydantic models, auth, and marketplace modules."""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rcf.config import Config, get_config
from rcf.db.models import (
    CadastralInfo,
    CaseClaimCreate,
    ClassificationResult,
    LawyerCreate,
    OwnerCreate,
    PermitCreate,
    PropertyCreate,
    RefundCaseCreate,
)


# --- Config ---

def test_config_defaults():
    cfg = get_config()
    assert cfg.scanner_concurrency == 5
    assert cfg.classifier_confidence_threshold == 0.7
    assert cfg.ingestion_max_house_number == 100
    assert cfg.ingestion_batch_size == 500
    assert cfg.ckan_page_size == 1000


def test_config_is_frozen():
    cfg = Config()
    with pytest.raises(AttributeError):
        cfg.scanner_concurrency = 99


# --- Pydantic Models ---

def test_property_create_minimal():
    p = PropertyCreate(address_text="הרצל 10", city="תל אביב")
    assert p.address_text == "הרצל 10"
    assert p.block is None
    assert p.geo_lat is None


def test_property_create_full():
    p = PropertyCreate(
        address_text="הרצל 10", city="תל אביב",
        block="6134", plot="78", geo_lat=32.08, geo_lng=34.78,
    )
    assert p.block == "6134"
    assert p.geo_lat == 32.08


def test_property_create_missing_required():
    with pytest.raises(ValidationError):
        PropertyCreate(address_text="x")  # missing city


def test_permit_create():
    p = PermitCreate(
        property_id=uuid4(), permit_number="101-123",
        decision_type="rejected", decision_date=date(2025, 1, 1),
    )
    assert p.decision_type == "rejected"


def test_permit_create_minimal():
    p = PermitCreate(property_id=uuid4())
    assert p.permit_number is None
    assert p.decision_date is None


def test_refund_case_create():
    rc = RefundCaseCreate(
        permit_id=uuid4(), property_id=uuid4(),
        classification="authority_rejected",
        confidence_score=0.9, is_eligible=True, estimated_refund=25000,
    )
    assert rc.is_eligible is True


def test_lawyer_create():
    lc = LawyerCreate(
        full_name="עו״ד כהן", email="a@b.com",
        municipalities=["תל אביב", "חיפה"],
        specializations=["מקרקעין"],
    )
    assert len(lc.municipalities) == 2
    assert lc.bar_number is None


def test_owner_create_minimal():
    oc = OwnerCreate()
    assert oc.full_name is None
    assert oc.email is None


def test_case_claim_create():
    cc = CaseClaimCreate(
        refund_case_id=uuid4(), lawyer_id=uuid4(), owner_id=uuid4(),
    )
    assert cc.owner_id is not None


def test_case_claim_create_no_owner():
    cc = CaseClaimCreate(refund_case_id=uuid4(), lawyer_id=uuid4())
    assert cc.owner_id is None


def test_cadastral_info():
    ci = CadastralInfo(block="6134", plot="78", lat=32.08, lng=34.78)
    assert ci.municipality_id is None


def test_classification_result():
    cr = ClassificationResult(
        classification="authority_rejected", confidence=0.92,
        evidence_excerpt="הוועדה דחתה",
    )
    assert cr.confidence == 0.92
