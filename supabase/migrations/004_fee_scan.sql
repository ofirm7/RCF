-- Extend fee_analyses for automatic scanning pipeline.

ALTER TABLE fee_analyses ADD COLUMN IF NOT EXISTS plan_number TEXT;
ALTER TABLE fee_analyses ADD COLUMN IF NOT EXISTS plan_url TEXT;
ALTER TABLE fee_analyses ADD COLUMN IF NOT EXISTS scan_source TEXT DEFAULT 'manual_upload';
ALTER TABLE fee_analyses ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'complete';

-- Allow upsert by permit_id (one fee analysis per permit)
ALTER TABLE fee_analyses
    ADD CONSTRAINT uq_fee_analyses_permit
    UNIQUE (permit_id);

CREATE INDEX IF NOT EXISTS idx_fee_analyses_status ON fee_analyses(status);
CREATE INDEX IF NOT EXISTS idx_fee_analyses_scan_source ON fee_analyses(scan_source);
