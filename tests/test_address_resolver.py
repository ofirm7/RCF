"""Tests for the address resolver module (mocked Nominatim API)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcf.db.models import CadastralInfo


def _make_mock_client(response_json):
    """Create a mock httpx.AsyncClient that returns the given JSON."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_json
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    return mock_client


@pytest.mark.asyncio
async def test_resolve_success():
    """resolve() returns CadastralInfo with lat/lng from Nominatim."""
    nominatim_json = [
        {"lat": "32.08", "lon": "34.78", "display_name": "הרצל 10, תל אביב"}
    ]
    mock_client = _make_mock_client(nominatim_json)

    with patch("rcf.scanner.address_resolver.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.address_resolver import resolve
        result = await resolve("הרצל 10, תל אביב")

    assert isinstance(result, CadastralInfo)
    assert result.lat == pytest.approx(32.08)
    assert result.lng == pytest.approx(34.78)
    assert result.block == ""


@pytest.mark.asyncio
async def test_resolve_no_results():
    """resolve() returns None when Nominatim returns empty."""
    mock_client = _make_mock_client([])

    with patch("rcf.scanner.address_resolver.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.address_resolver import resolve
        result = await resolve("nonexistent address")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_empty_address():
    """resolve() returns None for empty string."""
    from rcf.scanner.address_resolver import resolve
    result = await resolve("")
    assert result is None
