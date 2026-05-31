-- Migration 013: add quality_flag column to financial_line_items
--
-- NULL  = data passed all validation checks (clean).
-- Text  = description of the quality issue detected during ingestion
--         (e.g. "duration_mismatch", "yoy_3x_jump", "negative_value").
--
-- Flagged values are preserved for auditability but _get_value_for_concept
-- prefers NULL (clean) rows over flagged ones when both are available.

ALTER TABLE financial_line_items
    ADD COLUMN quality_flag VARCHAR(100) NULL;

-- Partial index so clean-value lookups skip flagged rows efficiently.
CREATE INDEX idx_line_items_quality
    ON financial_line_items (filing_id, concept, period_end)
    WHERE quality_flag IS NULL;
