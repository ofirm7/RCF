"""Download and extract committee decision text from source URLs (PDF / HTML)."""

from __future__ import annotations

import io
import logging
import ssl

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def extract_decision_text(source_url: str) -> str | None:
    """Fetch the resource at *source_url* and return its text content.

    Supports:
    - HTML pages (committee protocol pages on MAVAT / municipal sites)
    - PDF documents (uploaded protocol files)

    Returns ``None`` if extraction fails.
    """
    if not source_url:
        return None

    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=ctx) as client:
        resp = await client.get(source_url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")

    if "pdf" in content_type or source_url.lower().endswith(".pdf"):
        return _extract_pdf_text(resp.content)
    else:
        return _extract_html_text(resp.text)


def _extract_pdf_text(raw_bytes: bytes) -> str | None:
    """Extract all text from a PDF byte stream."""
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n".join(pages_text).strip()
        return full_text if full_text else None
    except Exception:
        logger.exception("Failed to parse PDF")
        return None


def _extract_html_text(html: str) -> str | None:
    """Extract readable text from an HTML page, stripping boilerplate."""
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts, styles, navs
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        # Try to find the main content area
        main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
        target = main if main else soup.body or soup

        text = target.get_text(separator="\n", strip=True)
        return text if text else None
    except Exception:
        logger.exception("Failed to parse HTML")
        return None
