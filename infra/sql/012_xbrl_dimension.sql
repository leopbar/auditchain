-- Migration 012: persist XBRL frame field on financial_line_items
--
-- The SEC company_facts.json includes a `frame` field on each fact value.
-- Consolidated annual values carry a frame like 'CY2023'; segment or
-- non-calendar-FY values have no frame (stored here as empty string).
-- Persisting this field lets queries prefer the consolidated figure and
-- prevents segment revenues from silently overwriting the company total.

ALTER TABLE financial_line_items
    ADD COLUMN frame VARCHAR(20) NOT NULL DEFAULT '';

ALTER TABLE financial_line_items
    DROP CONSTRAINT financial_line_items_filing_id_statement_concept_period_end_key;

ALTER TABLE financial_line_items
    ADD CONSTRAINT financial_line_items_filing_id_statement_concept_period_end_frame_key
    UNIQUE (filing_id, statement, concept, period_end, frame);
