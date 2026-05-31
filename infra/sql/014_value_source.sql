-- Migration 014: add value_source column to financial_line_items
--
-- Tracks how the stored value was obtained during ingestion:
--   annual_direct    = fp=FY fact with 300-400 day duration (ideal)
--   aggregated_4q    = sum of Q1+Q2+Q3+Q4 (no annual tag found)
--   duration_fallback= fp=FY but wrong duration (quality_flag set separately)
--   NULL             = legacy rows ingested before this migration

ALTER TABLE financial_line_items
    ADD COLUMN value_source VARCHAR(30) NULL;
