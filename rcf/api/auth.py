"""Supabase JWT authentication helpers for FastAPI."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request


async def get_current_user(request: Request) -> dict:
    """Extract and validate a Supabase JWT from the Authorization header.

    Returns a dict with at least ``{"sub": "<user-id>", "role": "..."}``.

    For the MVP this is a thin pass-through — in production, verify the JWT
    signature against the Supabase JWT secret.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    # TODO: Verify JWT signature with Supabase JWT secret.
    # For now, decode without verification (development only).
    import json, base64  # noqa: E401

    try:
        payload_b64 = token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token format")

    return payload


async def require_role(role: str, user: dict = Depends(get_current_user)) -> dict:
    """Dependency that checks the user has the required app_metadata role."""
    user_role = user.get("app_metadata", {}).get("role", "owner")
    if user_role != role and user_role != "admin":
        raise HTTPException(status_code=403, detail=f"Role '{role}' required")
    return user
