"""Tests for the scanner runner module (orchestration logic)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rcf.db.models import CadastralInfo, ClassificationResult, PermitCreate

_PROP_UUID = uuid4()
_PROP_ID = str(_PROP_UUID)


# --- scan_address ---

@pytest.mark.asyncio
async def test_scan_address_no_geo():
    """scan_address marks error when geocoding fails."""
    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.address_resolver") as mock_resolver:
        mock_repo.upsert_property.return_value = {"id": _PROP_ID}
        mock_resolver.resolve = AsyncMock(return_value=None)

        from rcf.scanner.runner import scan_address
        result = await scan_address("nonexistent", "city")

    assert result is None
    mock_repo.mark_property_error.assert_called_once()


@pytest.mark.asyncio
async def test_scan_address_no_permits():
    """scan_address marks scanned when no permits found."""
    geo = CadastralInfo(block="", plot="", lat=32.08, lng=34.78)

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.address_resolver") as mock_resolver, \
         patch("rcf.scanner.runner.permit_fetcher") as mock_pf:
        mock_repo.upsert_property.return_value = {"id": _PROP_ID}
        mock_resolver.resolve = AsyncMock(return_value=geo)
        mock_pf.fetch_permits = AsyncMock(return_value=[])

        from rcf.scanner.runner import scan_address
        result = await scan_address("הרצל 10", "תל אביב")

    assert result is not None
    mock_repo.mark_property_scanned.assert_called_once()


@pytest.mark.asyncio
async def test_scan_address_with_permits():
    """scan_address processes permits when found."""
    geo = CadastralInfo(block="", plot="", lat=32.08, lng=34.78)
    permit = PermitCreate(
        property_id=_PROP_UUID, permit_number="101-999",
        decision_date=date.today() - timedelta(days=365),
        decision_type="rejected",
    )

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.address_resolver") as mock_resolver, \
         patch("rcf.scanner.runner.permit_fetcher") as mock_pf, \
         patch("rcf.scanner.runner.decision_parser") as mock_dp, \
         patch("rcf.scanner.runner.classifier") as mock_cls:
        mock_repo.upsert_property.return_value = {"id": _PROP_ID}
        mock_repo.insert_permit.return_value = {"id": str(uuid4())}
        mock_resolver.resolve = AsyncMock(return_value=geo)
        mock_pf.fetch_permits = AsyncMock(return_value=[permit])
        mock_dp.extract_decision_text = AsyncMock(return_value=None)

        from rcf.scanner.runner import scan_address
        result = await scan_address("הרצל 10", "תל אביב")

    assert result is not None
    mock_repo.insert_refund_case.assert_called_once()


@pytest.mark.asyncio
async def test_scan_address_exception_marks_error():
    """scan_address marks error on unexpected exception."""
    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.address_resolver") as mock_resolver:
        mock_repo.upsert_property.return_value = {"id": _PROP_ID}
        mock_resolver.resolve = AsyncMock(side_effect=RuntimeError("boom"))

        from rcf.scanner.runner import scan_address
        result = await scan_address("bad", "city")

    assert result is None
    mock_repo.mark_property_error.assert_called_once()


# --- _process_permit ---

@pytest.mark.asyncio
async def test_process_permit_expired():
    """_process_permit skips permits outside statute window."""
    old_date = date.today() - timedelta(days=365 * 10)
    permit = PermitCreate(
        property_id=_PROP_UUID, permit_number="101-old",
        decision_date=old_date, decision_type="rejected",
    )

    with patch("rcf.scanner.runner.repository") as mock_repo:
        from rcf.scanner.runner import _process_permit
        await _process_permit(permit, _PROP_ID)

    mock_repo.insert_permit.assert_not_called()


@pytest.mark.asyncio
async def test_process_permit_eligible_fallback():
    """_process_permit uses status fallback when no decision text."""
    recent_date = date.today() - timedelta(days=365)
    permit = PermitCreate(
        property_id=_PROP_UUID, permit_number="101-new",
        decision_date=recent_date, decision_type="rejected",
    )

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.decision_parser") as mock_dp:
        mock_repo.insert_permit.return_value = {"id": str(uuid4())}
        mock_dp.extract_decision_text = AsyncMock(return_value=None)

        from rcf.scanner.runner import _process_permit
        await _process_permit(permit, _PROP_ID)

    mock_repo.insert_refund_case.assert_called_once()
    call_args = mock_repo.insert_refund_case.call_args[0][0]
    assert call_args.classification == "authority_rejected"
    assert call_args.confidence_score == 0.7
    assert call_args.is_eligible is True


@pytest.mark.asyncio
async def test_process_permit_withdrawn_not_eligible():
    """_process_permit marks withdrawn permits as not eligible."""
    recent_date = date.today() - timedelta(days=365)
    permit = PermitCreate(
        property_id=_PROP_UUID, permit_number="101-wd",
        decision_date=recent_date, decision_type="withdrawn",
    )

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.decision_parser") as mock_dp:
        mock_repo.insert_permit.return_value = {"id": str(uuid4())}
        mock_dp.extract_decision_text = AsyncMock(return_value=None)

        from rcf.scanner.runner import _process_permit
        await _process_permit(permit, _PROP_ID)

    call_args = mock_repo.insert_refund_case.call_args[0][0]
    assert call_args.classification == "applicant_abandoned"
    assert call_args.is_eligible is False


@pytest.mark.asyncio
async def test_process_permit_short_text_filtered():
    """Decision text shorter than 50 chars is treated as SPA placeholder."""
    recent_date = date.today() - timedelta(days=365)
    permit = PermitCreate(
        property_id=_PROP_UUID, permit_number="101-spa",
        decision_date=recent_date, decision_type="rejected",
    )

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.decision_parser") as mock_dp:
        mock_repo.insert_permit.return_value = {"id": str(uuid4())}
        mock_dp.extract_decision_text = AsyncMock(return_value="Loading...")

        from rcf.scanner.runner import _process_permit
        await _process_permit(permit, _PROP_ID)

    # Should fall back to status-based, not try NLP
    call_args = mock_repo.insert_refund_case.call_args[0][0]
    assert call_args.classification == "authority_rejected"


# --- _handle_rejected_plan ---

@pytest.mark.asyncio
async def test_handle_rejected_plan_success():
    plan = {
        "pl_number": "101-plan",
        "pl_name": "test plan name",
        "city": "ירושלים",
        "lat": 31.77, "lng": 35.23,
        "decision_date": date.today() - timedelta(days=365),
        "application_date": date(2024, 1, 1),
        "committee_name": "ועדה",
        "source_url": "https://example.com",
    }

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.decision_parser") as mock_dp:
        mock_repo.upsert_property.return_value = {"id": _PROP_ID}
        mock_repo.insert_permit.return_value = {"id": str(uuid4())}
        mock_dp.extract_decision_text = AsyncMock(return_value=None)

        from rcf.scanner.runner import _handle_rejected_plan
        result = await _handle_rejected_plan(plan)

    assert result is not None
    mock_repo.mark_property_scanned.assert_called_once()


@pytest.mark.asyncio
async def test_handle_rejected_plan_exception():
    plan = {
        "pl_number": "101-fail",
        "pl_name": "failing plan",
        "city": "חיפה",
        "lat": None, "lng": None,
        "decision_date": date.today() - timedelta(days=365),
        "application_date": None,
        "committee_name": None,
        "source_url": None,
    }

    with patch("rcf.scanner.runner.repository") as mock_repo, \
         patch("rcf.scanner.runner.decision_parser") as mock_dp:
        mock_repo.upsert_property.return_value = {"id": _PROP_ID}
        mock_repo.insert_permit.side_effect = RuntimeError("DB error")

        from rcf.scanner.runner import _handle_rejected_plan
        result = await _handle_rejected_plan(plan)

    assert result is None
    mock_repo.mark_property_error.assert_called_once()
