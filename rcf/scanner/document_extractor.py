"""AI-powered document extraction for fee invoices and building permits.

Uses Claude to parse Hebrew PDF content and extract structured data.
"""

from __future__ import annotations

import base64
import json
import logging

import anthropic

from rcf.config import get_config

logger = logging.getLogger(__name__)

_INVOICE_PROMPT = """\
You are an expert in Israeli building fee invoices (דף חישוב אגרות בנייה).

Extract the following fields from this fee calculation document:
1. total_charged_nis: The total fee amount in NIS (the bottom-line number)
2. paving_sqm: Square meters charged for paving/roads (סלילה/כבישים)
3. drainage_sqm: Square meters charged for drainage/sewage (תיעול/ביוב)
4. rate_per_sqm: The rate per square meter used (NIS/sqm)
5. fee_year: The year the fee was calculated for
6. municipality: The municipality name

If a field is not found, use null.

Respond ONLY with a JSON object:
{
  "total_charged_nis": 15000,
  "paving_sqm": 120.5,
  "drainage_sqm": 120.5,
  "rate_per_sqm": 35.0,
  "fee_year": 2024,
  "municipality": "תל אביב"
}
"""

_PERMIT_PROMPT = """\
You are an expert in Israeli building permits (היתר בנייה / גרמושקה).

Extract the area table (טבלת שטחים) from this building permit document:
1. residential_sqm: Total main area for residential/commercial use (שטח עיקרי למגורים/מסחר)
2. service_sqm: Total service/auxiliary area including storage, parking, basements \
(שטחי שירות - מחסנים, חניות, מרתפים)
3. total_sqm: Grand total area from the permit
4. building_type: "residential", "commercial", or "mixed"
5. floors: Number of floors
6. units: Number of residential units (if applicable)

If a field is not found, use null.

Respond ONLY with a JSON object:
{
  "residential_sqm": 150.0,
  "service_sqm": 45.0,
  "total_sqm": 195.0,
  "building_type": "residential",
  "floors": 2,
  "units": 1
}
"""


async def extract_fee_invoice(pdf_bytes: bytes) -> dict | None:
    """Extract fee invoice data from a PDF using Claude vision."""
    return await _extract_document(pdf_bytes, _INVOICE_PROMPT, "fee invoice")


async def extract_permit_areas(pdf_bytes: bytes) -> dict | None:
    """Extract permit area table from a PDF using Claude vision."""
    return await _extract_document(pdf_bytes, _PERMIT_PROMPT, "permit")


async def _extract_document(
    pdf_bytes: bytes,
    system_prompt: str,
    doc_type: str,
) -> dict | None:
    """Send a PDF to Claude for structured data extraction."""
    cfg = get_config()
    if not cfg.anthropic_api_key:
        logger.warning("No Anthropic API key — cannot extract %s", doc_type)
        return None

    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract the data from this document.",
                    },
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    logger.debug("Claude extraction raw (%s): %s", doc_type, raw[:300])

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Claude %s extraction: %s", doc_type, raw[:200])
        return None
