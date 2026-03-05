"""Tests for the NLP classifier module (mocked — no real API calls)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from rcf.db.models import ClassificationResult


@pytest.mark.asyncio
async def test_classify_authority_rejected():
    """Classifier returns authority_rejected when Claude says so."""
    mock_response = AsyncMock()
    mock_response.content = [
        AsyncMock(
            text=json.dumps(
                {
                    "classification": "authority_rejected",
                    "confidence": 0.92,
                    "evidence_excerpt": "הוועדה החליטה לדחות את הבקשה",
                }
            )
        )
    ]

    with patch("rcf.scanner.classifier.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        from rcf.scanner.classifier import classify

        result = await classify("הוועדה החליטה לדחות את הבקשה מנימוקים תכנוניים")

    assert isinstance(result, ClassificationResult)
    assert result.classification == "authority_rejected"
    assert result.confidence == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_classify_handles_bad_json():
    """Classifier returns 'unclear' when Claude returns non-JSON."""
    mock_response = AsyncMock()
    mock_response.content = [AsyncMock(text="I'm not sure about this one.")]

    with patch("rcf.scanner.classifier.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        from rcf.scanner.classifier import classify

        result = await classify("some text")

    assert result.classification == "unclear"
    assert result.confidence == 0.0
