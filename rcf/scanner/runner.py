"""Batch orchestrator — iterate addresses, detect refund eligibility, write to DB."""

from __future__ import annotations

import asyncio
import logging

from tqdm import tqdm

from rcf.config import get_config
from rcf.db import repository
from rcf.db.models import ClassificationResult, PermitCreate, PropertyCreate, RefundCaseCreate
from rcf.scanner import (
    address_resolver,
    classifier,
    decision_parser,
    limitations,
    permit_fetcher,
    plan_discovery,
    refund_estimator,
)

logger = logging.getLogger(__name__)


async def scan_address(address: str, city: str) -> dict | None:
    """Full pipeline for a single address. Returns the property dict or None."""

    # 1. Upsert property row
    prop = repository.upsert_property(PropertyCreate(address_text=address, city=city))
    property_id = prop["id"]

    try:
        # 2. Resolve address → coordinates
        geo = await address_resolver.resolve(f"{address}, {city}")
        if geo is None or geo.lat is None or geo.lng is None:
            logger.warning("Could not resolve %s, %s — skipping", address, city)
            repository.mark_property_error(property_id)
            return None

        # Update property with geo info
        repository.update_property_cadastral(
            property_id=property_id,
            block=geo.block or "",
            plot=geo.plot or "",
            municipality_id=geo.municipality_id,
            geo_lat=geo.lat,
            geo_lng=geo.lng,
        )

        # 3. Fetch plans/permits at this location via iPlan spatial query
        permits = await permit_fetcher.fetch_permits(
            geo.lat, geo.lng, property_id
        )
        if not permits:
            repository.mark_property_scanned(property_id)
            return prop

        # 4. Process each rejected/withdrawn permit
        for permit_data in permits:
            await _process_permit(permit_data, property_id)

        repository.mark_property_scanned(property_id)
        return prop

    except Exception:
        logger.exception("Error scanning %s, %s", address, city)
        repository.mark_property_error(property_id)
        return None


async def _process_permit(permit_data: PermitCreate, property_id: str) -> None:
    """Analyse a single permit and create a refund case if eligible."""

    # Check statute of limitations first (cheap)
    if not limitations.is_within_window(permit_data.decision_date):
        logger.debug(
            "Permit %s expired — skipping", permit_data.permit_number
        )
        return

    # Insert permit row
    permit_row = repository.insert_permit(permit_data)
    permit_id = permit_row["id"]

    # Extract decision text
    decision_text = await decision_parser.extract_decision_text(
        permit_data.source_url
    )
    # Filter out SPA placeholder text
    if decision_text and len(decision_text.strip()) < 50:
        decision_text = None
    if decision_text:
        repository.update_permit_decision_text(permit_id, decision_text)

    # Try NLP classification if we have text and API key
    cfg = get_config()
    result = None
    if decision_text and cfg.anthropic_api_key:
        try:
            result = await classifier.classify(decision_text)
        except Exception:
            logger.warning("NLP classification failed for permit %s — using status-based classification",
                          permit_data.permit_number)

    # Fall back to status-based classification if NLP unavailable
    if result is None:
        # Use the decision_type from the permit data (set by iPlan status)
        if permit_data.decision_type == "rejected":
            result = ClassificationResult(
                classification="authority_rejected",
                confidence=0.7,  # moderate confidence from status alone
                evidence_excerpt=f"iPlan status: plan rejected ({permit_data.decision_type})",
            )
        elif permit_data.decision_type == "withdrawn":
            result = ClassificationResult(
                classification="applicant_abandoned",
                confidence=0.6,
                evidence_excerpt=f"iPlan status: plan withdrawn ({permit_data.decision_type})",
            )
        else:
            result = ClassificationResult(
                classification="unclear",
                confidence=0.0,
                evidence_excerpt=None,
            )

    cfg = get_config()
    is_eligible = (
        result.classification == "authority_rejected"
        and result.confidence >= cfg.classifier_confidence_threshold
    )

    estimated = (
        refund_estimator.estimate(
            permit_type=None,
            building_area_sqm=None,
            decision_date=permit_data.decision_date,
        )
        if is_eligible
        else None
    )

    repository.insert_refund_case(
        RefundCaseCreate(
            permit_id=permit_id,
            property_id=property_id,
            classification=result.classification,
            confidence_score=result.confidence,
            is_eligible=is_eligible,
            estimated_refund=estimated,
            statute_expires_at=limitations.expiry_date(permit_data.decision_date)
            if permit_data.decision_date
            else None,
            evidence_summary=result.evidence_excerpt,
        )
    )

    if is_eligible:
        logger.info(
            "✓ Eligible refund found — permit %s, est. ₪%s",
            permit_data.permit_number,
            f"{estimated:,}" if estimated else "?",
        )


async def run_batch(
    addresses: list[tuple[str, str]],
    concurrency: int | None = None,
) -> dict:
    """Run the scanner over a list of ``(address, city)`` tuples.

    Returns a summary dict with counts.
    """
    cfg = get_config()
    sem = asyncio.Semaphore(concurrency or cfg.scanner_concurrency)

    total = len(addresses)
    scanned = 0
    errors = 0

    async def _bounded(addr: str, city: str) -> None:
        nonlocal scanned, errors
        async with sem:
            result = await scan_address(addr, city)
            if result is None:
                errors += 1
            else:
                scanned += 1

    tasks = [_bounded(addr, city) for addr, city in addresses]

    # tqdm progress bar
    for coro in tqdm(
        asyncio.as_completed(tasks), total=total, desc="Scanning addresses"
    ):
        await coro

    return {"total": total, "scanned": scanned, "errors": errors}


async def scan_rejected_plans(
    city_filter: str | None = None,
    concurrency: int | None = None,
) -> dict:
    """Discover rejected plans directly from iPlan and process them.

    This is more efficient than scanning individual addresses because it
    goes straight to where the rejected plans are (only ~115 across Israel).
    """
    cfg = get_config()
    sem = asyncio.Semaphore(concurrency or cfg.scanner_concurrency)

    # 1. Fetch all rejected plans from iPlan
    plans = await plan_discovery.fetch_rejected_plans(city_filter=city_filter)
    logger.info("Discovered %d rejected plans to process", len(plans))

    total = len(plans)
    scanned = 0
    errors = 0

    async def _process_plan(plan: dict) -> None:
        nonlocal scanned, errors
        async with sem:
            try:
                result = await _handle_rejected_plan(plan)
                if result:
                    scanned += 1
                else:
                    errors += 1
            except Exception:
                logger.exception("Error processing plan %s", plan.get("pl_number"))
                errors += 1

    tasks = [_process_plan(p) for p in plans]
    for coro in tqdm(
        asyncio.as_completed(tasks), total=total, desc="Processing rejected plans"
    ):
        await coro

    return {"total": total, "scanned": scanned, "errors": errors}


async def _handle_rejected_plan(plan: dict) -> dict | None:
    """Process a single rejected plan discovered from iPlan."""

    city = plan["city"]
    plan_name = plan.get("pl_name") or plan.get("pl_number") or "unknown"

    # Create a property entry for this plan's location
    prop = repository.upsert_property(
        PropertyCreate(address_text=plan_name, city=city)
    )
    property_id = prop["id"]

    try:
        # Update with geo info if available
        if plan.get("lat") and plan.get("lng"):
            repository.update_property_cadastral(
                property_id=property_id,
                block="",
                plot="",
                municipality_id=None,
                geo_lat=plan["lat"],
                geo_lng=plan["lng"],
            )

        # Create permit from plan data
        permit_data = PermitCreate(
            property_id=property_id,
            permit_number=plan.get("pl_number"),
            application_date=plan.get("application_date"),
            decision_date=plan.get("decision_date"),
            decision_type="rejected",
            committee_name=plan.get("committee_name"),
            source_url=plan.get("source_url"),
            raw_decision=None,
        )

        await _process_permit(permit_data, property_id)
        repository.mark_property_scanned(property_id)
        return prop

    except Exception:
        logger.exception("Error processing plan %s in %s", plan_name, city)
        repository.mark_property_error(property_id)
        return None
