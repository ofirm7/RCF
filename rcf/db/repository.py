"""CRUD helpers using direct PostgreSQL queries via psycopg."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from rcf.db.client import execute, execute_one
from rcf.db.models import (
    CaseClaimCreate,
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
    return execute_one(
        """
        INSERT INTO permits (property_id, permit_number, application_date, decision_date,
                             decision_type, committee_name, source_url, raw_decision)
        VALUES (%(property_id)s, %(permit_number)s, %(application_date)s, %(decision_date)s,
                %(decision_type)s, %(committee_name)s, %(source_url)s, %(raw_decision)s)
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
    return execute_one(
        """
        INSERT INTO refund_cases (permit_id, property_id, classification, confidence_score,
                                  is_eligible, estimated_refund, statute_expires_at, evidence_summary)
        VALUES (%(permit_id)s, %(property_id)s, %(classification)s, %(confidence_score)s,
                %(is_eligible)s, %(estimated_refund)s, %(statute_expires_at)s, %(evidence_summary)s)
        RETURNING *
        """,
        data.model_dump(mode="json"),
    )


def update_refund_case_status(case_id: UUID, status: str) -> None:
    execute(
        "UPDATE refund_cases SET status = %(status)s WHERE id = %(id)s",
        {"id": str(case_id), "status": status},
    )


def get_eligible_cases(
    city: str | None = None,
    status: str | None = None,
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
