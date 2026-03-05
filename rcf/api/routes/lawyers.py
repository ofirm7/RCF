"""Routes for lawyer registration and case management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from rcf.db import repository
from rcf.db.models import LawyerCreate

router = APIRouter()


@router.post("")
async def register_lawyer(data: LawyerCreate) -> dict:
    """Register a new lawyer on the marketplace."""
    return repository.insert_lawyer(data)


@router.get("/{lawyer_id}")
async def get_lawyer(lawyer_id: UUID) -> dict:
    row = repository.get_lawyer(lawyer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lawyer not found")
    return row


@router.get("/{lawyer_id}/cases")
async def lawyer_cases(lawyer_id: UUID) -> list[dict]:
    """Cases claimed by this lawyer."""
    return repository.get_claims_for_lawyer(lawyer_id)
