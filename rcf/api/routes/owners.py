"""Routes for property owner registration and case status."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from rcf.db import repository
from rcf.db.models import OwnerCreate

router = APIRouter()


@router.post("")
async def register_owner(data: OwnerCreate) -> dict:
    """Register a new property owner."""
    return repository.insert_owner(data)


@router.get("/{owner_id}")
async def get_owner(owner_id: UUID) -> dict:
    row = repository.get_owner(owner_id)
    if not row:
        raise HTTPException(status_code=404, detail="Owner not found")
    return row


@router.get("/{owner_id}/cases")
async def owner_cases(owner_id: UUID) -> list[dict]:
    """Refund cases linked to this owner via case claims."""
    return repository.get_claims_for_owner(owner_id)
