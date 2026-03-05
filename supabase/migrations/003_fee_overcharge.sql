-- Fee overcharge detection: store extracted document data and comparison results.

CREATE TABLE fee_analyses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id             UUID NOT NULL REFERENCES properties(id),
    permit_id               UUID REFERENCES permits(id),

    -- From fee invoice (דף חישוב האגרות)
    invoice_total           INTEGER,        -- total charged by municipality (ILS agorot)
    invoice_paving_sqm      REAL,           -- sqm charged for paving
    invoice_drainage_sqm    REAL,           -- sqm charged for drainage / sewage
    invoice_rate_per_sqm    REAL,           -- rate the municipality used (NIS)

    -- From permit area table (גרמושקה)
    permit_residential_sqm  REAL,           -- main residential / commercial area
    permit_service_sqm      REAL,           -- service areas (storage, parking, basements)
    permit_total_sqm        REAL,           -- total from permit

    -- Computed comparison
    correct_fee             INTEGER,        -- what should have been charged (ILS agorot)
    overcharge_amount       INTEGER,        -- invoice_total − correct_fee (ILS agorot)
    fee_year                INTEGER,        -- year for rate lookup
    rate_used               REAL,           -- legal rate applied (NIS / sqm)

    -- Document references
    invoice_pdf_url         TEXT,
    permit_pdf_url          TEXT,
    extraction_raw          JSONB,          -- raw AI extraction output

    created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_fee_analyses_property ON fee_analyses(property_id);

-- Add case type to distinguish refund detection methods.
ALTER TABLE refund_cases ADD COLUMN case_type TEXT DEFAULT 'plan_rejected';
-- Values: 'plan_rejected' (existing), 'fee_overcharge' (new)
