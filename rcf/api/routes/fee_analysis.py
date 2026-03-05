"""Routes for fee overcharge analysis — upload documents, run comparison."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from rcf.db import repository
from rcf.db.models import FeeAnalysisCreate, PropertyCreate, RefundCaseCreate
from rcf.scanner import document_extractor, fee_analyzer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_fee_analyses(
    city: str | None = Query(None),
    status: str | None = Query(None),
    scan_source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List fee analyses with optional filters."""
    return repository.get_fee_analyses(
        city=city, status=status, scan_source=scan_source,
        limit=limit, offset=offset,
    )


@router.post("")
async def analyze_fees_upload(
    address: str = Form(...),
    city: str = Form(...),
    fee_year: int = Form(...),
    invoice_pdf: UploadFile = File(...),
    permit_pdf: UploadFile = File(...),
) -> dict:
    """Upload fee invoice + permit PDFs, extract data, compare, return result."""

    # 1. Upsert property
    prop = repository.upsert_property(PropertyCreate(address_text=address, city=city))
    property_id = prop["id"]

    # 2. Extract data from both PDFs using Claude
    invoice_bytes = await invoice_pdf.read()
    permit_bytes = await permit_pdf.read()

    invoice_data = await document_extractor.extract_fee_invoice(invoice_bytes)
    permit_data = await document_extractor.extract_permit_areas(permit_bytes)

    if not invoice_data:
        raise HTTPException(status_code=422, detail="Could not extract data from fee invoice PDF")
    if not permit_data:
        raise HTTPException(status_code=422, detail="Could not extract data from permit PDF")

    # 3. Run fee comparison
    invoice_total_agorot = int((invoice_data.get("total_charged_nis") or 0) * 100)
    residential_sqm = permit_data.get("residential_sqm") or 0.0
    service_sqm = permit_data.get("service_sqm") or 0.0

    result = fee_analyzer.analyze_fees(
        invoice_total_agorot=invoice_total_agorot,
        invoice_paving_sqm=invoice_data.get("paving_sqm"),
        invoice_drainage_sqm=invoice_data.get("drainage_sqm"),
        invoice_rate_per_sqm=invoice_data.get("rate_per_sqm"),
        permit_residential_sqm=residential_sqm,
        permit_service_sqm=service_sqm,
        fee_year=fee_year,
    )

    # 4. Store analysis
    analysis = repository.insert_fee_analysis(
        FeeAnalysisCreate(
            property_id=property_id,
            invoice_total=invoice_total_agorot,
            invoice_paving_sqm=invoice_data.get("paving_sqm"),
            invoice_drainage_sqm=invoice_data.get("drainage_sqm"),
            invoice_rate_per_sqm=invoice_data.get("rate_per_sqm"),
            permit_residential_sqm=residential_sqm,
            permit_service_sqm=service_sqm,
            permit_total_sqm=permit_data.get("total_sqm"),
            correct_fee=result.correct_fee,
            overcharge_amount=result.overcharge_amount,
            fee_year=fee_year,
            rate_used=result.rate_used,
            extraction_raw={"invoice": invoice_data, "permit": permit_data},
            scan_source="manual_upload",
            status="overcharge_detected" if result.is_overcharged else "complete",
        )
    )

    # 5. If overcharged, create a refund case
    refund_case = None
    if result.is_overcharged:
        refund_case = repository.insert_refund_case(
            RefundCaseCreate(
                permit_id=analysis.get("permit_id") or property_id,
                property_id=property_id,
                classification="fee_overcharge",
                confidence_score=0.9,
                is_eligible=True,
                estimated_refund=result.overcharge_amount,
                evidence_summary=(
                    f"Municipality charged ₪{invoice_total_agorot / 100:,.0f}, "
                    f"correct fee is ₪{result.correct_fee / 100:,.0f}. "
                    f"Overcharge: ₪{result.overcharge_amount / 100:,.0f}"
                ),
            )
        )

    return {
        "analysis_id": str(analysis["id"]),
        "is_overcharged": result.is_overcharged,
        "invoice_total_nis": invoice_total_agorot / 100,
        "correct_fee_nis": result.correct_fee / 100,
        "overcharge_nis": result.overcharge_amount / 100,
        "breakdown": result.breakdown,
        "extracted_invoice": invoice_data,
        "extracted_permit": permit_data,
        "refund_case_id": str(refund_case["id"]) if refund_case else None,
    }


@router.post("/{analysis_id}/invoice")
async def upload_invoice_for_analysis(
    analysis_id: UUID,
    invoice_pdf: UploadFile = File(...),
) -> dict:
    """Upload an invoice for a pre-computed fee analysis to complete overcharge detection."""

    existing = repository.get_fee_analysis(analysis_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Extract invoice data
    invoice_bytes = await invoice_pdf.read()
    invoice_data = await document_extractor.extract_fee_invoice(invoice_bytes)

    if not invoice_data:
        raise HTTPException(status_code=422, detail="Could not extract data from invoice PDF")

    invoice_total_agorot = int((invoice_data.get("total_charged_nis") or 0) * 100)

    # Re-run comparison with actual invoice data
    result = fee_analyzer.analyze_fees(
        invoice_total_agorot=invoice_total_agorot,
        invoice_paving_sqm=invoice_data.get("paving_sqm"),
        invoice_drainage_sqm=invoice_data.get("drainage_sqm"),
        invoice_rate_per_sqm=invoice_data.get("rate_per_sqm"),
        permit_residential_sqm=existing.get("permit_residential_sqm") or 0.0,
        permit_service_sqm=existing.get("permit_service_sqm") or 0.0,
        fee_year=existing.get("fee_year") or 2024,
    )

    # Update the analysis record
    new_status = "overcharge_detected" if result.is_overcharged else "complete"
    from rcf.db.client import execute
    execute(
        """
        UPDATE fee_analyses
        SET invoice_total = %(invoice_total)s,
            invoice_paving_sqm = %(paving_sqm)s,
            invoice_drainage_sqm = %(drainage_sqm)s,
            invoice_rate_per_sqm = %(rate_sqm)s,
            overcharge_amount = %(overcharge)s,
            extraction_raw = %(raw)s,
            status = %(status)s
        WHERE id = %(id)s
        """,
        {
            "id": str(analysis_id),
            "invoice_total": invoice_total_agorot,
            "paving_sqm": invoice_data.get("paving_sqm"),
            "drainage_sqm": invoice_data.get("drainage_sqm"),
            "rate_sqm": invoice_data.get("rate_per_sqm"),
            "overcharge": result.overcharge_amount,
            "raw": {"invoice": invoice_data},
            "status": new_status,
        },
    )

    # Create refund case if overcharged
    refund_case = None
    if result.is_overcharged:
        property_id = existing["property_id"]
        permit_id = existing.get("permit_id") or property_id
        refund_case = repository.insert_refund_case(
            RefundCaseCreate(
                permit_id=permit_id,
                property_id=property_id,
                classification="fee_overcharge",
                confidence_score=0.9,
                is_eligible=True,
                estimated_refund=result.overcharge_amount,
                evidence_summary=(
                    f"Municipality charged ₪{invoice_total_agorot / 100:,.0f}, "
                    f"correct fee is ₪{result.correct_fee / 100:,.0f}. "
                    f"Overcharge: ₪{result.overcharge_amount / 100:,.0f}"
                ),
            )
        )

    return {
        "analysis_id": str(analysis_id),
        "is_overcharged": result.is_overcharged,
        "invoice_total_nis": invoice_total_agorot / 100,
        "correct_fee_nis": result.correct_fee / 100,
        "overcharge_nis": result.overcharge_amount / 100,
        "breakdown": result.breakdown,
        "refund_case_id": str(refund_case["id"]) if refund_case else None,
    }


@router.post("/scan-city")
async def trigger_city_scan(city: str = Form(...)) -> dict:
    """Manually trigger a fee scan for a city."""
    from rcf.scanner.fee_scanner import scan_city_fees
    result = await scan_city_fees(city)
    return result


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: UUID) -> dict:
    """Get a fee analysis by ID."""
    row = repository.get_fee_analysis(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return row
