"""Routes for refund cases — browse, detail, claim."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from rcf.db import repository
from rcf.db.models import CaseClaimCreate

router = APIRouter()


@router.get("")
async def list_cases(
    city: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List eligible refund cases, filterable by city and status."""
    return repository.get_eligible_cases(
        city=city, status=status, limit=limit, offset=offset
    )


@router.get("/{case_id}")
async def get_case(case_id: UUID) -> dict:
    """Get full details for a single refund case."""
    row = repository.get_refund_case(case_id)
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


@router.post("/{case_id}/claim")
async def claim_case(case_id: UUID, lawyer_id: UUID, owner_id: UUID | None = None) -> dict:
    """A lawyer claims a refund case to begin the recovery process."""
    case = repository.get_refund_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.get("status") not in ("detected", "verified"):
        raise HTTPException(status_code=400, detail="Case is not claimable")

    claim = repository.insert_case_claim(
        CaseClaimCreate(
            refund_case_id=case_id, lawyer_id=lawyer_id, owner_id=owner_id
        )
    )

    repository.update_refund_case_status(case_id, "claimed")
    return claim
