-- Migration to allow AuditRuns to exist before a filing is identified
-- and to link directly to companies for easier tracking of running audits.

ALTER TABLE audit_runs ALTER COLUMN filing_id DROP NOT NULL;

-- Add company_id to audit_runs to track the company even if filing isn't selected yet
ALTER TABLE audit_runs ADD COLUMN company_id BIGINT REFERENCES companies(id);

-- Update existing records if possible (optional but good practice)
UPDATE audit_runs SET company_id = (SELECT company_id FROM filings WHERE filings.id = audit_runs.filing_id)
WHERE filing_id IS NOT NULL;

-- Now make it NOT NULL for future runs (once backfilled)
-- Actually, let's keep it nullable for a moment to avoid migration issues with existing data if filing_id link is broken
ALTER TABLE audit_runs ALTER COLUMN company_id SET NOT NULL;

CREATE INDEX idx_audit_runs_company ON audit_runs(company_id);
