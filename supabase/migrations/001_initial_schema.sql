-- RCF Initial Schema
-- Run against your Supabase project via the SQL editor or CLI.

-- ============================================================
-- Properties — scanned addresses with cadastral mapping
-- ============================================================
CREATE TABLE properties (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address_text    TEXT NOT NULL,
    city            TEXT NOT NULL,
    block           TEXT,                    -- cadastral block (גוש)
    plot            TEXT,                    -- cadastral plot (חלקה)
    municipality_id TEXT,
    geo_lat         DOUBLE PRECISION,
    geo_lng         DOUBLE PRECISION,
    scan_status     TEXT DEFAULT 'pending',  -- pending | scanned | error
    scanned_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (address_text, city)
);

-- ============================================================
-- Permits — building permits found per property
-- ============================================================
CREATE TABLE permits (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id      UUID NOT NULL REFERENCES properties(id),
    permit_number    TEXT,
    application_date DATE,
    decision_date    DATE,
    decision_type    TEXT,        -- approved | rejected | withdrawn | abandoned
    committee_name   TEXT,
    source_url       TEXT,        -- link to MAVAT / municipal record
    raw_decision     TEXT,        -- full committee decision text
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Refund Cases — eligibility analysis per permit
-- ============================================================
CREATE TABLE refund_cases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permit_id           UUID NOT NULL REFERENCES permits(id),
    property_id         UUID NOT NULL REFERENCES properties(id),
    classification      TEXT NOT NULL,    -- authority_rejected | applicant_abandoned | unclear
    confidence_score    REAL,             -- 0.0–1.0 from NLP classifier
    is_eligible         BOOLEAN,          -- true = refund owed
    estimated_refund    INTEGER,          -- amount in ILS agorot (1 ILS = 100 agorot)
    statute_expires_at  DATE,             -- decision_date + 7 years
    evidence_summary    TEXT,             -- key excerpts from decision
    human_verified      BOOLEAN DEFAULT FALSE,
    status              TEXT DEFAULT 'detected',
        -- detected | verified | claimed | recovered | expired
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Lawyers — registered on the marketplace
-- ============================================================
CREATE TABLE lawyers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID,                   -- Supabase Auth user id
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    phone           TEXT,
    bar_number      TEXT,
    specializations TEXT[],
    municipalities  TEXT[],                 -- cities they cover
    is_verified     BOOLEAN DEFAULT FALSE,
    subscription    TEXT DEFAULT 'free',    -- free | premium
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Owners — property owners who register on the platform
-- ============================================================
CREATE TABLE owners (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID,                       -- Supabase Auth user id
    full_name  TEXT,
    email      TEXT,
    phone      TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Case Claims — lawyer takes on a refund case for an owner
-- ============================================================
CREATE TABLE case_claims (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    refund_case_id   UUID NOT NULL REFERENCES refund_cases(id),
    lawyer_id        UUID NOT NULL REFERENCES lawyers(id),
    owner_id         UUID REFERENCES owners(id),
    status           TEXT DEFAULT 'pending',
        -- pending | active | filed | recovered | closed
    recovered_amount INTEGER,
    lawyer_fee       INTEGER,
    rcf_fee          INTEGER,
    claimed_at       TIMESTAMPTZ DEFAULT now(),
    recovered_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_properties_city ON properties(city);
CREATE INDEX idx_properties_block_plot ON properties(block, plot);
CREATE INDEX idx_properties_scan_status ON properties(scan_status);
CREATE INDEX idx_permits_property ON permits(property_id);
CREATE INDEX idx_permits_decision_type ON permits(decision_type);
CREATE INDEX idx_refund_cases_eligible ON refund_cases(is_eligible) WHERE is_eligible = TRUE;
CREATE INDEX idx_refund_cases_status ON refund_cases(status);
CREATE INDEX idx_refund_cases_property ON refund_cases(property_id);
CREATE INDEX idx_lawyers_municipalities ON lawyers USING GIN(municipalities);
CREATE INDEX idx_case_claims_lawyer ON case_claims(lawyer_id);
CREATE INDEX idx_case_claims_status ON case_claims(status);
