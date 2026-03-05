"""Tests for authentication helpers."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi import HTTPException

from rcf.api.auth import get_current_user, require_role


def _make_jwt(payload: dict) -> str:
    """Create a fake JWT (header.payload.signature) for testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.fake-signature"


class FakeRequest:
    def __init__(self, auth_header: str | None = None):
        self.headers = {}
        if auth_header is not None:
            self.headers["Authorization"] = auth_header


@pytest.mark.asyncio
async def test_get_current_user_valid():
    token = _make_jwt({"sub": "user-123", "role": "owner"})
    request = FakeRequest(f"Bearer {token}")
    user = await get_current_user(request)
    assert user["sub"] == "user-123"


@pytest.mark.asyncio
async def test_get_current_user_missing_header():
    request = FakeRequest()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_no_bearer():
    request = FakeRequest("Basic abc123")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_empty_token():
    request = FakeRequest("Bearer ")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_format():
    request = FakeRequest("Bearer not.valid")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_matching():
    user = {"sub": "user-1", "app_metadata": {"role": "lawyer"}}
    result = await require_role("lawyer", user)
    assert result["sub"] == "user-1"


@pytest.mark.asyncio
async def test_require_role_admin_bypass():
    user = {"sub": "admin-1", "app_metadata": {"role": "admin"}}
    result = await require_role("lawyer", user)
    assert result["sub"] == "admin-1"


@pytest.mark.asyncio
async def test_require_role_forbidden():
    user = {"sub": "user-1", "app_metadata": {"role": "owner"}}
    with pytest.raises(HTTPException) as exc_info:
        await require_role("lawyer", user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_default_owner():
    """When no role in app_metadata, defaults to 'owner'."""
    user = {"sub": "user-1"}
    with pytest.raises(HTTPException) as exc_info:
        await require_role("lawyer", user)
    assert exc_info.value.status_code == 403
