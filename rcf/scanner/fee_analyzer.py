"""Fee overcharge analyzer — compare municipality invoice vs. correct legal fees."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rcf.scanner.fee_rates import compute_correct_fee, get_rate

logger = logging.getLogger(__name__)


@dataclass
class FeeComparisonResult:
    """Output of the fee comparison."""
    invoice_total: int          # what municipality charged (agorot)
    correct_fee: int            # what should have been charged (agorot)
    overcharge_amount: int      # invoice_total - correct_fee (agorot)
    is_overcharged: bool
    rate_used: float            # legal rate applied (NIS/sqm)
    breakdown: dict             # detailed breakdown for evidence


def analyze_fees(
    *,
    invoice_total_agorot: int,
    invoice_paving_sqm: float | None = None,
    invoice_drainage_sqm: float | None = None,
    invoice_rate_per_sqm: float | None = None,
    permit_residential_sqm: float,
    permit_service_sqm: float,
    fee_year: int,
    previously_paid_sqm: float = 0.0,
    residential_type: str = "residential",
) -> FeeComparisonResult:
    """Run the fee comparison formula.

    Steps (from business requirements):
    1. Take charged area and subtract already-paid area
    2. Check if classification (residential/storage) matches permit
    3. Multiply by legal rate for that year
    4. Compare: if correct_fee < invoice_total → overcharge
    """
    # Step 1: net area (subtract previously paid)
    net_residential = max(0.0, permit_residential_sqm - previously_paid_sqm)
    net_service = permit_service_sqm

    # Step 3: compute correct fee using legal rates
    correct = compute_correct_fee(
        residential_sqm=net_residential,
        service_sqm=net_service,
        year=fee_year,
        residential_type=residential_type,
    )

    overcharge = invoice_total_agorot - correct
    legal_rate = get_rate(fee_year, residential_type)

    # Step 2: flag classification mismatch
    classification_note = None
    if invoice_rate_per_sqm and abs(invoice_rate_per_sqm - legal_rate) > 1.0:
        classification_note = (
            f"Municipality used {invoice_rate_per_sqm:.2f} NIS/sqm, "
            f"legal rate is {legal_rate:.2f} NIS/sqm"
        )

    breakdown = {
        "net_residential_sqm": net_residential,
        "net_service_sqm": net_service,
        "previously_paid_sqm": previously_paid_sqm,
        "residential_rate": legal_rate,
        "service_rate": get_rate(fee_year, "service"),
        "fee_year": fee_year,
    }
    if invoice_paving_sqm is not None:
        breakdown["invoice_paving_sqm"] = invoice_paving_sqm
    if invoice_drainage_sqm is not None:
        breakdown["invoice_drainage_sqm"] = invoice_drainage_sqm
    if classification_note:
        breakdown["classification_mismatch"] = classification_note

    result = FeeComparisonResult(
        invoice_total=invoice_total_agorot,
        correct_fee=correct,
        overcharge_amount=max(0, overcharge),
        is_overcharged=overcharge > 0,
        rate_used=legal_rate,
        breakdown=breakdown,
    )

    if result.is_overcharged:
        logger.info(
            "Overcharge detected: invoiced ₪%s, correct ₪%s, overcharge ₪%s",
            invoice_total_agorot / 100,
            correct / 100,
            overcharge / 100,
        )

    return result
