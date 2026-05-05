-- AuditChain initial schema
-- Designed for US GAAP financial statements from SEC EDGAR filings
-- Includes tables for fraud detection ground truth and audit trail

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =====================================================================
-- COMPANIES AND FILINGS
-- =====================================================================

CREATE TABLE companies (
    id              BIGSERIAL PRIMARY KEY,
    cik             VARCHAR(10) UNIQUE NOT NULL,         -- SEC Central Index Key
    ticker          VARCHAR(10),
    name            TEXT NOT NULL,
    sic_code        VARCHAR(4),                          -- Standard Industrial Classification
    industry        TEXT,
    fiscal_year_end VARCHAR(4),                          -- e.g. "1231"
    is_known_fraud  BOOLEAN DEFAULT FALSE,               -- ground truth flag
    fraud_notes     TEXT,                                -- e.g. "AAER 3001, Enron-style revenue recognition"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_companies_cik ON companies(cik);
CREATE INDEX idx_companies_ticker ON companies(ticker);

CREATE TYPE filing_type AS ENUM ('10-K', '10-Q', '8-K', '20-F', '40-F', '10-K/A', '10-Q/A', '8-K/A', '20-F/A', '40-F/A');

CREATE TABLE filings (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    filing_type     filing_type NOT NULL,
    accession_number VARCHAR(20) UNIQUE NOT NULL,        -- SEC unique ID
    filing_date     DATE NOT NULL,
    period_of_report DATE NOT NULL,                      -- fiscal period covered
    fiscal_year     INTEGER NOT NULL,
    fiscal_period   VARCHAR(2) NOT NULL,                 -- FY, Q1, Q2, Q3
    raw_url         TEXT,
    is_synthetic    BOOLEAN DEFAULT FALSE,
    fraud_injected  JSONB,                               -- {"type": "channel_stuffing", "magnitude": 0.15}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_filings_company_period ON filings(company_id, period_of_report DESC);
CREATE INDEX idx_filings_type_date ON filings(filing_type, filing_date DESC);

-- =====================================================================
-- FINANCIAL STATEMENTS (normalized US GAAP line items)
-- =====================================================================

CREATE TYPE statement_type AS ENUM ('income_statement', 'balance_sheet', 'cash_flow');

CREATE TABLE financial_line_items (
    id              BIGSERIAL PRIMARY KEY,
    filing_id       BIGINT NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    statement       statement_type NOT NULL,
    concept         VARCHAR(100) NOT NULL,               -- e.g. "Revenues", "NetIncomeLoss"
    label           TEXT,                                -- human-readable label from XBRL
    value           NUMERIC(20, 2),
    currency        VARCHAR(3) DEFAULT 'USD',
    unit            VARCHAR(20) DEFAULT 'USD',
    decimals        INTEGER,
    period_start    DATE,
    period_end      DATE NOT NULL,
    UNIQUE(filing_id, statement, concept, period_end)
);

CREATE INDEX idx_line_items_filing ON financial_line_items(filing_id);
CREATE INDEX idx_line_items_concept ON financial_line_items(concept);

-- =====================================================================
-- TEXTUAL DISCLOSURES (for RAG)
-- =====================================================================

CREATE TYPE disclosure_section AS ENUM (
    'mdna',                          -- Management Discussion & Analysis
    'risk_factors',
    'notes_to_financials',
    'auditors_report',
    'controls_procedures',
    'business',
    'legal_proceedings'
);

CREATE TABLE disclosures (
    id              BIGSERIAL PRIMARY KEY,
    filing_id       BIGINT NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    section         disclosure_section NOT NULL,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    embedding       vector(1536),                        -- text-embedding-3-small
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_disclosures_filing_section ON disclosures(filing_id, section);
CREATE INDEX idx_disclosures_embedding ON disclosures
    USING hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- AUDIT RUNS AND AGENT OUTPUTS
-- =====================================================================

CREATE TYPE audit_status AS ENUM ('pending', 'running', 'completed', 'failed', 'requires_human');

CREATE TABLE audit_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id       BIGINT NOT NULL REFERENCES filings(id),
    status          audit_status NOT NULL DEFAULT 'pending',
    risk_score      NUMERIC(5, 2),                       -- 0 to 100
    risk_level      VARCHAR(10),                         -- LOW, MEDIUM, HIGH, CRITICAL
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    total_tokens    INTEGER,
    total_cost_usd  NUMERIC(10, 4),
    langgraph_thread_id TEXT,                            -- LangGraph checkpoint thread
    final_report    JSONB
);

CREATE INDEX idx_audit_runs_filing ON audit_runs(filing_id, started_at DESC);
CREATE INDEX idx_audit_runs_status ON audit_runs(status);

CREATE TABLE agent_steps (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    agent_name      VARCHAR(50) NOT NULL,
    step_index      INTEGER NOT NULL,
    input           JSONB,
    output          JSONB,
    tool_calls      JSONB,
    latency_ms      INTEGER,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    cost_usd        NUMERIC(10, 6),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_steps_run ON agent_steps(run_id, step_index);

CREATE TYPE flag_severity AS ENUM ('info', 'low', 'medium', 'high', 'critical');

CREATE TABLE red_flags (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    detected_by     VARCHAR(50) NOT NULL,                -- which agent
    category        VARCHAR(50) NOT NULL,                -- e.g. "revenue_recognition", "expense_capitalization"
    severity        flag_severity NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    evidence        JSONB,                               -- supporting data points
    rationale       TEXT,                                -- LLM explanation
    confidence      NUMERIC(3, 2),                       -- 0 to 1
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_red_flags_run_severity ON red_flags(run_id, severity);

-- =====================================================================
-- TRIGGERS
-- =====================================================================

CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();
