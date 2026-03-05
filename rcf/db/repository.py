"""CRUD helpers using direct PostgreSQL queries via psycopg."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from rcf.db.client import execute, execute_one
from rcf.db.models import (
    CaseClaimCreate,
    FeeAnalysisCreate,
    LawyerCreate,
    OwnerCreate,
    PermitCreate,
    PropertyCreate,
    RefundCaseCreate,
)


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------

def upsert_property(data: PropertyCreate) -> dict:
    """Insert or update a property row (unique on address_text + city)."""
    return execute_one(
        """
        INSERT INTO properties (address_text, city, block, plot, municipality_id, geo_lat, geo_lng)
        VALUES (%(address_text)s, %(city)s, %(block)s, %(plot)s, %(municipality_id)s, %(geo_lat)s, %(geo_lng)s)
        ON CONFLICT (address_text, city) DO UPDATE SET
            block = COALESCE(EXCLUDED.block, properties.block),
            plot = COALESCE(EXCLUDED.plot, properties.plot)
        RETURNING *
        """,
        data.model_dump(),
    )


def update_property_cadastral(
    property_id: str,
    block: str,
    plot: str,
    municipality_id: str | None,
    geo_lat: float | None,
    geo_lng: float | None,
) -> None:
    execute(
        """
        UPDATE properties
        SET block = %(block)s, plot = %(plot)s, municipality_id = %(municipality_id)s,
            geo_lat = %(geo_lat)s, geo_lng = %(geo_lng)s
        WHERE id = %(id)s
        """,
        {"id": property_id, "block": block, "plot": plot,
         "municipality_id": municipality_id, "geo_lat": geo_lat, "geo_lng": geo_lng},
    )


def mark_property_scanned(property_id: UUID) -> None:
    execute(
        "UPDATE properties SET scan_status = 'scanned', scanned_at = %(now)s WHERE id = %(id)s",
        {"id": str(property_id), "now": datetime.utcnow()},
    )


def mark_property_error(property_id: UUID, error: str | None = None) -> None:
    execute(
        "UPDATE properties SET scan_status = 'error' WHERE id = %(id)s",
        {"id": str(property_id)},
    )


def get_pending_properties(city: str | None = None, limit: int = 100) -> list[dict]:
    if city:
        return execute(
            "SELECT * FROM properties WHERE scan_status = 'pending' AND city ILIKE %(city)s LIMIT %(limit)s",
            {"city": f"%{city}%", "limit": limit},
        )
    return execute(
        "SELECT * FROM properties WHERE scan_status = 'pending' LIMIT %(limit)s",
        {"limit": limit},
    )


# ------------------------------------------------------------------
# Permits
# ------------------------------------------------------------------

def insert_permit(data: PermitCreate) -> dict:
    """Insert or update a permit (unique on property_id + permit_number)."""
    return execute_one(
        """
        INSERT INTO permits (property_id, permit_number, application_date, decision_date,
                             decision_type, committee_name, source_url, raw_decision)
        VALUES (%(property_id)s, %(permit_number)s, %(application_date)s, %(decision_date)s,
                %(decision_type)s, %(committee_name)s, %(source_url)s, %(raw_decision)s)
        ON CONFLICT (property_id, permit_number) DO UPDATE SET
            decision_date = COALESCE(EXCLUDED.decision_date, permits.decision_date),
            decision_type = COALESCE(EXCLUDED.decision_type, permits.decision_type),
            source_url = COALESCE(EXCLUDED.source_url, permits.source_url)
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def update_permit_decision_text(permit_id: str, raw_decision: str) -> None:
    execute(
        "UPDATE permits SET raw_decision = %(text)s WHERE id = %(id)s",
        {"id": permit_id, "text": raw_decision},
    )


def get_permits_for_property(property_id: UUID) -> list[dict]:
    return execute(
        "SELECT * FROM permits WHERE property_id = %(pid)s",
        {"pid": str(property_id)},
    )


# ------------------------------------------------------------------
# Refund Cases
# ------------------------------------------------------------------

def insert_refund_case(data: RefundCaseCreate) -> dict:
    """Insert or update a refund case (unique on permit_id).

    Only updates if the existing case is still in 'detected' status —
    never overwrites cases that are already verified/claimed/recovered.
    """
    return execute_one(
        """
        INSERT INTO refund_cases (permit_id, property_id, classification, confidence_score,
                                  is_eligible, estimated_refund, statute_expires_at, evidence_summary)
        VALUES (%(permit_id)s, %(property_id)s, %(classification)s, %(confidence_score)s,
                %(is_eligible)s, %(estimated_refund)s, %(statute_expires_at)s, %(evidence_summary)s)
        ON CONFLICT (permit_id) DO UPDATE SET
            classification = EXCLUDED.classification,
            confidence_score = EXCLUDED.confidence_score,
            is_eligible = EXCLUDED.is_eligible,
            estimated_refund = EXCLUDED.estimated_refund,
            evidence_summary = EXCLUDED.evidence_summary
        WHERE refund_cases.status = 'detected'
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def get_refund_case_by_permit(permit_id: str) -> dict | None:
    """Return the refund case for a permit, or None."""
    rows = execute(
        "SELECT * FROM refund_cases WHERE permit_id = %(pid)s",
        {"pid": permit_id},
    )
    return rows[0] if rows else None


def update_refund_case_status(case_id: UUID, status: str) -> None:
    execute(
        "UPDATE refund_cases SET status = %(status)s WHERE id = %(id)s",
        {"id": str(case_id), "status": status},
    )


def get_eligible_cases(
    city: str | None = None,
    status: str | None = None,
    case_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    clauses = ["rc.is_eligible = TRUE"]
    params: dict = {"limit": limit, "offset": offset}

    if city:
        clauses.append("p.city = %(city)s")
        params["city"] = city
    if status:
        clauses.append("rc.status = %(status)s")
        params["status"] = status
    if case_type:
        clauses.append("rc.case_type = %(case_type)s")
        params["case_type"] = case_type

    where = " AND ".join(clauses)
    return execute(
        f"""
        SELECT rc.*, p.city, p.address_text, pm.permit_number, pm.source_url AS permit_url
        FROM refund_cases rc
        JOIN properties p ON p.id = rc.property_id
        LEFT JOIN permits pm ON pm.id = rc.permit_id
        WHERE {where}
        ORDER BY rc.created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )


def get_refund_case(case_id: UUID) -> dict | None:
    return execute_one(
        """
        SELECT rc.*, p.city, p.address_text, p.block, p.plot,
               pm.permit_number, pm.decision_date, pm.decision_type, pm.source_url
        FROM refund_cases rc
        JOIN properties p ON p.id = rc.property_id
        JOIN permits pm ON pm.id = rc.permit_id
        WHERE rc.id = %(id)s
        """,
        {"id": str(case_id)},
    )


# ------------------------------------------------------------------
# Lawyers
# ------------------------------------------------------------------

def insert_lawyer(data: LawyerCreate) -> dict:
    return execute_one(
        """
        INSERT INTO lawyers (user_id, full_name, email, phone, bar_number, specializations, municipalities)
        VALUES (%(user_id)s, %(full_name)s, %(email)s, %(phone)s, %(bar_number)s,
                %(specializations)s, %(municipalities)s)
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def get_lawyers_for_municipality(municipality: str) -> list[dict]:
    return execute(
        "SELECT * FROM lawyers WHERE %(mun)s = ANY(municipalities)",
        {"mun": municipality},
    )


def get_lawyer(lawyer_id: UUID) -> dict | None:
    return execute_one(
        "SELECT * FROM lawyers WHERE id = %(id)s",
        {"id": str(lawyer_id)},
    )


# ------------------------------------------------------------------
# Owners
# ------------------------------------------------------------------

def insert_owner(data: OwnerCreate) -> dict:
    return execute_one(
        """
        INSERT INTO owners (user_id, full_name, email, phone)
        VALUES (%(user_id)s, %(full_name)s, %(email)s, %(phone)s)
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def get_owner(owner_id: UUID) -> dict | None:
    return execute_one(
        "SELECT * FROM owners WHERE id = %(id)s",
        {"id": str(owner_id)},
    )


# ------------------------------------------------------------------
# Case Claims
# ------------------------------------------------------------------

def insert_case_claim(data: CaseClaimCreate) -> dict:
    return execute_one(
        """
        INSERT INTO case_claims (refund_case_id, lawyer_id, owner_id)
        VALUES (%(refund_case_id)s, %(lawyer_id)s, %(owner_id)s)
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def get_claims_for_lawyer(lawyer_id: UUID) -> list[dict]:
    return execute(
        """
        SELECT cc.*, rc.classification, rc.estimated_refund, rc.status AS case_status,
               p.city, p.address_text
        FROM case_claims cc
        JOIN refund_cases rc ON rc.id = cc.refund_case_id
        JOIN properties p ON p.id = rc.property_id
        WHERE cc.lawyer_id = %(id)s
        """,
        {"id": str(lawyer_id)},
    )


def get_claims_for_owner(owner_id: UUID) -> list[dict]:
    return execute(
        """
        SELECT cc.*, rc.classification, rc.estimated_refund, rc.status AS case_status,
               p.city, p.address_text, l.full_name AS lawyer_name, l.email AS lawyer_email
        FROM case_claims cc
        JOIN refund_cases rc ON rc.id = cc.refund_case_id
        JOIN properties p ON p.id = rc.property_id
        JOIN lawyers l ON l.id = cc.lawyer_id
        WHERE cc.owner_id = %(id)s
        """,
        {"id": str(owner_id)},
    )


# ------------------------------------------------------------------
# Fee Analyses
# ------------------------------------------------------------------

def insert_fee_analysis(data: FeeAnalysisCreate) -> dict:
    return execute_one(
        """
        INSERT INTO fee_analyses (
            property_id, permit_id,
            invoice_total, invoice_paving_sqm, invoice_drainage_sqm, invoice_rate_per_sqm,
            permit_residential_sqm, permit_service_sqm, permit_total_sqm,
            correct_fee, overcharge_amount, fee_year, rate_used,
            invoice_pdf_url, permit_pdf_url, extraction_raw,
            plan_number, plan_url, scan_source, status
        ) VALUES (
            %(property_id)s, %(permit_id)s,
            %(invoice_total)s, %(invoice_paving_sqm)s, %(invoice_drainage_sqm)s, %(invoice_rate_per_sqm)s,
            %(permit_residential_sqm)s, %(permit_service_sqm)s, %(permit_total_sqm)s,
            %(correct_fee)s, %(overcharge_amount)s, %(fee_year)s, %(rate_used)s,
            %(invoice_pdf_url)s, %(permit_pdf_url)s, %(extraction_raw)s,
            %(plan_number)s, %(plan_url)s, %(scan_source)s, %(status)s
        ) RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def upsert_fee_analysis(data: FeeAnalysisCreate) -> dict:
    """Insert or update a fee analysis (unique on permit_id).

    Only updates if the existing record is still 'pre_computed' —
    never overwrites completed analyses with invoice data.
    """
    return execute_one(
        """
        INSERT INTO fee_analyses (
            property_id, permit_id,
            invoice_total, invoice_paving_sqm, invoice_drainage_sqm, invoice_rate_per_sqm,
            permit_residential_sqm, permit_service_sqm, permit_total_sqm,
            correct_fee, overcharge_amount, fee_year, rate_used,
            invoice_pdf_url, permit_pdf_url, extraction_raw,
            plan_number, plan_url, scan_source, status
        ) VALUES (
            %(property_id)s, %(permit_id)s,
            %(invoice_total)s, %(invoice_paving_sqm)s, %(invoice_drainage_sqm)s, %(invoice_rate_per_sqm)s,
            %(permit_residential_sqm)s, %(permit_service_sqm)s, %(permit_total_sqm)s,
            %(correct_fee)s, %(overcharge_amount)s, %(fee_year)s, %(rate_used)s,
            %(invoice_pdf_url)s, %(permit_pdf_url)s, %(extraction_raw)s,
            %(plan_number)s, %(plan_url)s, %(scan_source)s, %(status)s
        )
        ON CONFLICT (permit_id) DO UPDATE SET
            permit_residential_sqm = EXCLUDED.permit_residential_sqm,
            permit_service_sqm = EXCLUDED.permit_service_sqm,
            permit_total_sqm = EXCLUDED.permit_total_sqm,
            correct_fee = EXCLUDED.correct_fee,
            fee_year = EXCLUDED.fee_year,
            rate_used = EXCLUDED.rate_used,
            plan_number = EXCLUDED.plan_number,
            plan_url = EXCLUDED.plan_url
        WHERE fee_analyses.status = 'pre_computed'
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def get_fee_analysis(analysis_id: UUID) -> dict | None:
    rows = execute(
        """
        SELECT fa.*, p.city, p.address_text
        FROM fee_analyses fa
        JOIN properties p ON p.id = fa.property_id
        WHERE fa.id = %(id)s
        """,
        {"id": str(analysis_id)},
    )
    return rows[0] if rows else None


def get_fee_analysis_by_permit(permit_id: str) -> dict | None:
    """Return the fee analysis for a permit, or None."""
    rows = execute(
        """
        SELECT fa.*, p.city, p.address_text
        FROM fee_analyses fa
        JOIN properties p ON p.id = fa.property_id
        WHERE fa.permit_id = %(pid)s
        """,
        {"pid": permit_id},
    )
    return rows[0] if rows else None


def get_fee_analyses(
    city: str | None = None,
    status: str | None = None,
    scan_source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List fee analyses with optional filters."""
    clauses = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}

    if city:
        clauses.append("p.city ILIKE %(city)s")
        params["city"] = f"%{city}%"
    if status:
        clauses.append("fa.status = %(status)s")
        params["status"] = status
    if scan_source:
        clauses.append("fa.scan_source = %(scan_source)s")
        params["scan_source"] = scan_source

    where = " AND ".join(clauses)
    return execute(
        f"""
        SELECT fa.*, p.city, p.address_text, pm.permit_number
        FROM fee_analyses fa
        JOIN properties p ON p.id = fa.property_id
        LEFT JOIN permits pm ON pm.id = fa.permit_id
        WHERE {where}
        ORDER BY fa.created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )


def get_fee_analyses_for_property(property_id: UUID) -> list[dict]:
    return execute(
        "SELECT * FROM fee_analyses WHERE property_id = %(pid)s ORDER BY created_at DESC",
        {"pid": str(property_id)},
    )
