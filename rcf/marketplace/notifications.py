"""Notification stubs for lawyer/owner outreach.

In production, integrate with an email service (SendGrid, Resend) and/or
SMS gateway. For now, this module logs notifications.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_lawyer_new_case(
    lawyer_email: str,
    lawyer_name: str,
    city: str,
    estimated_refund: int | None,
    case_id: str,
) -> None:
    """Notify a lawyer about a new eligible refund case in their area."""
    amount_str = f"₪{estimated_refund:,}" if estimated_refund else "unknown"
    logger.info(
        "NOTIFY LAWYER %s (%s): New refund case in %s — estimated %s [case=%s]",
        lawyer_name,
        lawyer_email,
        city,
        amount_str,
        case_id,
    )
    # TODO: Send actual email via SendGrid/Resend


def notify_owner_refund_found(
    owner_email: str,
    owner_name: str | None,
    address: str,
    estimated_refund: int | None,
) -> None:
    """Notify a property owner that a refund opportunity was found."""
    amount_str = f"₪{estimated_refund:,}" if estimated_refund else "unknown amount"
    logger.info(
        "NOTIFY OWNER %s (%s): Refund opportunity at %s — estimated %s",
        owner_name or "Owner",
        owner_email,
        address,
        amount_str,
    )
    # TODO: Send actual email via SendGrid/Resend
