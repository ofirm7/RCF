"""Pydantic models mirroring the Supabase schema."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------
class PropertyBase(BaseModel):
    address_text: str
    city: str
    block: str | None = None
    plot: str | None = None
    municipality_id: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None


class PropertyCreate(PropertyBase):
    pass


class Property(PropertyBase):
    id: UUID
    scan_status: str = "pending"
    scanned_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Permits
# ------------------------------------------------------------------
class PermitBase(BaseModel):
    property_id: UUID
    permit_number: str | None = None
    application_date: date | None = None
    decision_date: date | None = None
    decision_type: str | None = None
    committee_name: str | None = None
    source_url: str | None = None
    raw_decision: str | None = None


class PermitCreate(PermitBase):
    pass


class Permit(PermitBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Refund Cases
# ------------------------------------------------------------------
class RefundCaseBase(BaseModel):
    permit_id: UUID
    property_id: UUID
    classification: str  # authority_rejected | applicant_abandoned | unclear
    confidence_score: float | None = None
    is_eligible: bool | None = None
    estimated_refund: int | None = None  # ILS agorot
    statute_expires_at: date | None = None
    evidence_summary: str | None = None


class RefundCaseCreate(RefundCaseBase):
    pass


class RefundCase(RefundCaseBase):
    id: UUID
    human_verified: bool = False
    status: str = "detected"
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Lawyers
# ------------------------------------------------------------------
class LawyerBase(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    bar_number: str | None = None
    specializations: list[str] = Field(default_factory=list)
    municipalities: list[str] = Field(default_factory=list)


class LawyerCreate(LawyerBase):
    user_id: UUID | None = None


class Lawyer(LawyerBase):
    id: UUID
    user_id: UUID | None = None
    is_verified: bool = False
    subscription: str = "free"
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Owners
# ------------------------------------------------------------------
class OwnerBase(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class OwnerCreate(OwnerBase):
    user_id: UUID | None = None


class Owner(OwnerBase):
    id: UUID
    user_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Case Claims
# ------------------------------------------------------------------
class CaseClaimBase(BaseModel):
    refund_case_id: UUID
    lawyer_id: UUID
    owner_id: UUID | None = None


class CaseClaimCreate(CaseClaimBase):
    pass


class CaseClaim(CaseClaimBase):
    id: UUID
    status: str = "pending"
    recovered_amount: int | None = None
    lawyer_fee: int | None = None
    rcf_fee: int | None = None
    claimed_at: datetime
    recovered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Lightweight DTOs used by the scanner
# ------------------------------------------------------------------
class CadastralInfo(BaseModel):
    """Result of resolving an address to cadastral identifiers."""

    block: str
    plot: str
    municipality_id: str | None = None
    lat: float | None = None
    lng: float | None = None


class ClassificationResult(BaseModel):
    """Output of the NLP rejection classifier."""

    classification: str  # authority_rejected | applicant_abandoned | unclear
    confidence: float  # 0.0–1.0
    evidence_excerpt: str | None = None
