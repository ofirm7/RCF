"""Routes for property eligibility lookup."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from rcf.db.client import execute

router = APIRouter()


@router.get("/{address}")
async def check_property(address: str) -> list[dict]:
    """Look up refund eligibility for a specific address.

    Returns property records with any associated refund cases.
    """
    rows = execute(
        """
        SELECT p.*, rc.id AS case_id, rc.classification, rc.is_eligible,
               rc.estimated_refund, rc.status AS case_status, rc.confidence_score
        FROM properties p
        LEFT JOIN refund_cases rc ON rc.property_id = p.id
        WHERE p.address_text ILIKE %(pattern)s
        LIMIT 10
        """,
        {"pattern": f"%{address}%"},
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Address not found — it may not have been scanned yet.",
        )
    return rows
