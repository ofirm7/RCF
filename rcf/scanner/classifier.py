"""NLP classifier — determines if a permit rejection is refund-eligible.

Uses Claude API to classify Hebrew committee decision text per the 2024
Supreme Court ruling:
  - authority_rejected  → refund owed (committee rejected on planning grounds)
  - applicant_abandoned → no refund (applicant withdrew / failed to meet conditions)
  - unclear             → needs human review
"""

from __future__ import annotations

import json
import logging

import anthropic

from rcf.config import get_config
from rcf.db.models import ClassificationResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a legal document analyst specializing in Israeli planning law.

Your task: classify a building permit committee decision to determine
whether the applicant is entitled to a refund of building fees (אגרות בנייה).

Per the 2024 Supreme Court ruling:
- REFUND OWED when the planning authority actively rejects the application
  on planning/zoning grounds (the committee decided against it).
- NO REFUND when the applicant abandoned the project, failed to submit
  required documents, or did not meet conditions set by the committee.

Respond with a JSON object:
{
  "classification": "authority_rejected" | "applicant_abandoned" | "unclear",
  "confidence": 0.0 to 1.0,
  "evidence_excerpt": "key sentence(s) from the text supporting your classification"
}

Only output the JSON object, nothing else.
"""


async def classify(decision_text: str) -> ClassificationResult:
    """Classify *decision_text* and return a structured result."""
    cfg = get_config()
    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)

    # Truncate very long texts to stay within token limits
    truncated = decision_text[:8000] if len(decision_text) > 8000 else decision_text

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "הנה החלטת ועדת תכנון. סווג את ההחלטה:\n\n"
                    f"{truncated}"
                ),
            }
        ],
    )

    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Classifier returned non-JSON: %s", raw[:200])
        return ClassificationResult(
            classification="unclear",
            confidence=0.0,
            evidence_excerpt=None,
        )

    return ClassificationResult(
        classification=parsed.get("classification", "unclear"),
        confidence=float(parsed.get("confidence", 0.0)),
        evidence_excerpt=parsed.get("evidence_excerpt"),
    )
