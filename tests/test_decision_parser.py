"""Tests for the decision parser module (PDF/HTML text extraction)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcf.scanner.decision_parser import _extract_html_text, _extract_pdf_text


# --- _extract_html_text ---

def test_extract_html_simple():
    html = "<html><body><p>הוועדה החליטה לדחות את הבקשה</p></body></html>"
    result = _extract_html_text(html)
    assert result is not None
    assert "הוועדה" in result


def test_extract_html_strips_scripts():
    html = "<html><body><script>var x=1;</script><p>content here</p></body></html>"
    result = _extract_html_text(html)
    assert result is not None
    assert "var x" not in result
    assert "content here" in result


def test_extract_html_strips_nav_footer():
    html = "<html><body><nav>nav stuff</nav><main>main content</main><footer>footer</footer></body></html>"
    result = _extract_html_text(html)
    assert result is not None
    assert "nav stuff" not in result
    assert "main content" in result
    assert "footer" not in result


def test_extract_html_prefers_main():
    html = "<html><body><div>outside</div><main>inside main</main></body></html>"
    result = _extract_html_text(html)
    assert "inside main" in result


def test_extract_html_prefers_article():
    html = "<html><body><div>outside</div><article>article text</article></body></html>"
    result = _extract_html_text(html)
    assert "article text" in result


def test_extract_html_empty():
    result = _extract_html_text("<html><body></body></html>")
    assert result is None


def test_extract_html_invalid():
    result = _extract_html_text("")
    assert result is None


# --- _extract_pdf_text ---

def test_extract_pdf_invalid_bytes():
    result = _extract_pdf_text(b"not a pdf")
    assert result is None


def test_extract_pdf_empty_bytes():
    result = _extract_pdf_text(b"")
    assert result is None


# --- extract_decision_text ---

@pytest.mark.asyncio
async def test_extract_decision_text_none_url():
    from rcf.scanner.decision_parser import extract_decision_text
    result = await extract_decision_text(None)
    assert result is None


@pytest.mark.asyncio
async def test_extract_decision_text_empty_url():
    from rcf.scanner.decision_parser import extract_decision_text
    result = await extract_decision_text("")
    assert result is None


@pytest.mark.asyncio
async def test_extract_decision_text_html():
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.text = "<html><body><p>החלטת ועדה: הבקשה נדחתה</p></body></html>"
    mock_resp.content = b""
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rcf.scanner.decision_parser.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.decision_parser import extract_decision_text
        result = await extract_decision_text("https://example.com/decision")

    assert result is not None
    assert "נדחתה" in result


@pytest.mark.asyncio
async def test_extract_decision_text_pdf_url():
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/octet-stream"}
    mock_resp.content = b"not-a-real-pdf"
    mock_resp.text = ""
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rcf.scanner.decision_parser.httpx.AsyncClient", return_value=mock_client):
        from rcf.scanner.decision_parser import extract_decision_text
        # URL ends with .pdf so it goes through PDF path
        result = await extract_decision_text("https://example.com/decision.pdf")

    # Invalid PDF returns None
    assert result is None
