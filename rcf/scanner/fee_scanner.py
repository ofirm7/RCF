"""Automatic fee analysis pipeline — discovers plans and computes correct fees.

Queries iPlan ArcGIS for all plans in a city, extracts building-rights
area data from the quantity_delta_* fields, and computes the correct
fee using the legal rate table.  Results are stored as pre-computed
fee_analysis records that can later be compared against uploaded invoices.
"""

from __future__ import annotations

import logging
from datetime import date

from rcf.db import repository
from rcf.db.models import FeeAnalysisCreate, PermitCreate, PropertyCreate
from rcf.scanner.fee_analyzer import analyze_fees
from rcf.scanner.fee_rates import get_rate
from rcf.scanner.iplan_client import fetch_plans_for_city

logger = logging.getLogger(__name__)


def _map_iplan_areas(attrs: dict) -> tuple[float, float, str]:
    """Map iPlan quantity-delta fields to (residential_sqm, service_sqm, area_type).

    iPlan building-rights codes (observed from ArcGIS schema):
        105 — residential
        110 — commercial / offices
        120 — public / institutional
        125 — service areas (storage, parking, infrastructure)
         60 — open public space
         75 — roads / transportation
         80 — other

    Returns (residential_sqm, service_sqm, residential_type).
    """
    d105 = attrs.get("quantity_delta_105") or 0.0  # residential
    d110 = attrs.get("quantity_delta_110") or 0.0  # commercial
    d120 = attrs.get("quantity_delta_120") or 0.0  # public/institutional
    d125 = attrs.get("quantity_delta_125") or 0.0  # service areas

    # Also check authorised quantities as fallback
    pq105 = attrs.get("pq_authorised_quantity_105") or 0.0
    pq110 = attrs.get("pq_authorised_quantity_110") or 0.0

    # Determine primary area type
    residential_sqm = max(0.0, d105)
    commercial_sqm = max(0.0, d110)
    service_sqm = max(0.0, d125)

    # If delta fields are empty, try authorised quantities
    if residential_sqm == 0 and commercial_sqm == 0 and pq105 > 0:
        residential_sqm = pq105
    if commercial_sqm == 0 and pq110 > 0:
        commercial_sqm = pq110

    # Classify the primary type
    if commercial_sqm > residential_sqm:
        residential_type = "commercial"
        main_sqm = commercial_sqm
    else:
        residential_type = "residential"
        main_sqm = residential_sqm

    # If no specific area data, fall back to plan area in dunams
    if main_sqm == 0 and service_sqm == 0:
        area_dunam = attrs.get("pl_area_dunam") or 0.0
        if area_dunam > 0:
            # Use land-use string for hints
            landuse = (attrs.get("pl_landuse_string") or "").lower()
            if "מסחר" in landuse or "משרד" in landuse:
                residential_type = "commercial"
            main_sqm = area_dunam * 1000 * 0.5  # rough: 50% of plot is built area
            service_sqm = area_dunam * 1000 * 0.1

    return main_sqm, service_sqm, residential_type


def _estimate_fee_year(attrs: dict) -> int:
    """Estimate the fee year from plan dates."""
    from rcf.scanner.iplan_client import epoch_to_date

    for field in ("pl_date7", "receiving_date"):
        dt = epoch_to_date(attrs.get(field))
        if dt:
            return dt.year

    return date.today().year


async def scan_city_fees(city: str, *, max_results: int = 1000) -> dict:
    """Run the automatic fee analysis pipeline for a city.

    1. Query iPlan for all plans in the city
    2. Extract area data from ArcGIS quantity fields
    3. Compute correct fee for each plan
    4. Store pre-computed fee_analysis records

    Returns summary stats.
    """
    logger.info("Starting fee scan for city=%s", city)

    plans = await fetch_plans_for_city(city, max_results=max_results)
    logger.info("Found %d plans for %s", len(plans), city)

    processed = 0
    skipped = 0
    errors = 0

    for plan in plans:
        try:
            result = _process_plan_fees(plan, city)
            if result:
                processed += 1
            else:
                skipped += 1
        except Exception:
            logger.exception("Error processing plan %s", plan.get("pl_number"))
            errors += 1

    logger.info(
        "Fee scan for %s: %d processed, %d skipped, %d errors (of %d total)",
        city, processed, skipped, errors, len(plans),
    )
    return {
        "city": city,
        "total": len(plans),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }


def _process_plan_fees(plan: dict, city: str) -> bool:
    """Process a single plan for fee analysis. Returns True if a record was created."""

    pl_number = plan.get("pl_number")
    if not pl_number:
        return False

    # Extract area data from iPlan fields
    residential_sqm, service_sqm, residential_type = _map_iplan_areas(plan)

    # Skip plans with no usable area data
    if residential_sqm <= 0 and service_sqm <= 0:
        logger.debug("Plan %s has no area data — skipping", pl_number)
        return False

    fee_year = _estimate_fee_year(plan)

    # Compute correct fee (with dummy invoice_total=0 since we don't have the invoice)
    result = analyze_fees(
        invoice_total_agorot=0,
        permit_residential_sqm=residential_sqm,
        permit_service_sqm=service_sqm,
        fee_year=fee_year,
        residential_type=residential_type,
    )

    # Upsert property
    plan_name = plan.get("pl_name") or pl_number
    prop = repository.upsert_property(
        PropertyCreate(address_text=plan_name, city=city)
    )
    property_id = prop["id"]

    # Update geo if available
    if plan.get("lat") and plan.get("lng"):
        repository.update_property_cadastral(
            property_id=str(property_id),
            block="",
            plot="",
            municipality_id=None,
            geo_lat=plan["lat"],
            geo_lng=plan["lng"],
        )

    # Upsert permit
    permit_row = repository.insert_permit(
        PermitCreate(
            property_id=property_id,
            permit_number=pl_number,
            application_date=plan.get("application_date"),
            decision_date=plan.get("decision_date"),
            decision_type=plan.get("internet_short_status"),
            committee_name=plan.get("ja_concat"),
            source_url=plan.get("pl_url"),
        )
    )

    # Store pre-computed fee analysis
    repository.upsert_fee_analysis(
        FeeAnalysisCreate(
            property_id=property_id,
            permit_id=permit_row["id"],
            permit_residential_sqm=residential_sqm,
            permit_service_sqm=service_sqm,
            permit_total_sqm=residential_sqm + service_sqm,
            correct_fee=result.correct_fee,
            fee_year=fee_year,
            rate_used=get_rate(fee_year, residential_type),
            plan_number=pl_number,
            plan_url=plan.get("pl_url"),
            scan_source="iplan_auto",
            status="pre_computed",
        )
    )

    logger.debug(
        "Plan %s: %.0f sqm residential, %.0f sqm service → correct fee ₪%.0f",
        pl_number,
        residential_sqm,
        service_sqm,
        result.correct_fee / 100,
    )
    return True
