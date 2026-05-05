export type AuditPhase = "collector" | "reconciler" | "quant_analyst" | "investigator" | "supervisor";

export type PhaseStatus = "pending" | "running" | "completed" | "failed";

export type AuditConclusion = "clean" | "qualified" | "adverse" | "disclaimer";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface ToolCallState {
  toolName: string;
  startedAt: number;
  completedAt: number | null;
  durationMs: number | null;
  success: boolean | null;
  input: Record<string, unknown> | null;
}

export interface PhaseState {
  phase: AuditPhase;
  agentName: string;
  status: PhaseStatus;
  startedAt: number | null;
  completedAt: number | null;
  duration: number | null;
  tokensUsed: number;
  costUsd: number;
  summary: Record<string, unknown> | null;
  redFlagsAdded: number;
  errorMessage: string | null;
  toolCalls: ToolCallState[];
}

export interface Company {
  cik: string;
  ticker: string | null;
  name: string;
  is_known_fraud: boolean;
  fraud_notes: string | null;
  filings_count: number;
  has_text_indexed: boolean;
}

export interface CompanyListResponse {
  companies: Company[];
  total: number;
}

export interface AuditSummary {
  run_id: string;
  company_cik: string;
  company_name: string;
  company_ticker: string | null;
  status: string;
  conclusion: AuditConclusion | null;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  red_flags_count: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface AuditListResponse {
  audits: AuditSummary[];
  total: number;
}

export interface RedFlag {
  detected_by: string;
  category: string;
  severity: Severity;
  title: string;
  description: string;
  confidence: number;
}

export interface AgentStep {
  agent_name: string;
  step_index: number;
  latency_ms: number | null;
  tokens_input: number | null;
  tokens_output: number | null;
  cost_usd: number | null;
}

export interface AuditDetail {
  run_id: string;
  company_cik: string;
  company_name: string;
  company_ticker: string | null;
  status: string;
  conclusion: AuditConclusion | null;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  needs_human_review: boolean;
  started_at: string;
  completed_at: string | null;
  total_tokens: number | null;
  total_cost_usd: number | null;
  final_report: Record<string, unknown> | null;
  red_flags: RedFlag[];
  agent_steps: AgentStep[];
}

export interface CreateAuditRequest {
  cik: string;
  model?: string;
}

export interface CreateAuditResponse {
  run_id: string;
  status: string;
  message: string;
  stream_url: string;
}

// Eventos SSE
export type EventType =
  | "stream_opened"
  | "audit_started"
  | "phase_started"
  | "tool_called"
  | "tool_completed"
  | "phase_completed"
  | "phase_failed"
  | "audit_completed"
  | "audit_failed"
  | "stream_closed";

export interface AuditEventBase {
  event_type: EventType;
  run_id: string;
  timestamp: string;
  elapsed_seconds: number;
}

export interface AuditStartedEvent extends AuditEventBase {
  event_type: "audit_started";
  company_cik: string;
  company_name: string;
  company_ticker: string | null;
  model: string;
}

export interface PhaseStartedEvent extends AuditEventBase {
  event_type: "phase_started";
  phase: AuditPhase;
  agent_name: string;
}

export interface ToolCalledEvent extends AuditEventBase {
  event_type: "tool_called";
  phase: AuditPhase;
  tool_name: string;
  tool_input: Record<string, unknown> | null;
}

export interface ToolCompletedEvent extends AuditEventBase {
  event_type: "tool_completed";
  phase: AuditPhase;
  tool_name: string;
  duration_ms: number;
  success: boolean;
}

export interface PhaseCompletedEvent extends AuditEventBase {
  event_type: "phase_completed";
  phase: AuditPhase;
  agent_name: string;
  duration_seconds: number;
  tokens_used: number;
  cost_usd: number;
  summary: Record<string, unknown>;
  red_flags_added: number;
}

export interface PhaseFailedEvent extends AuditEventBase {
  event_type: "phase_failed";
  phase: AuditPhase;
  error_message: string;
}

export interface FinancialPeriod {
  filing_id: number | null;
  fiscal_year: number | null;
  period_end: string | null;
  revenue: number | null;
  net_income: number | null;
  total_assets: number | null;
  total_liabilities: number | null;
  stockholders_equity: number | null;
  cash: number | null;
  cash_from_operations: number | null;
  cost_of_revenue: number | null;
  gross_profit: number | null;
  operating_expenses: number | null;
  operating_income: number | null;
  current_assets: number | null;
  accounts_receivable: number | null;
  inventory: number | null;
  current_liabilities: number | null;
  cash_from_investing: number | null;
  cash_from_financing: number | null;
}

export interface CompanyData {
  name: string;
  ticker: string | null;
  cik: string;
  current_period: FinancialPeriod | null;
  historical_periods: FinancialPeriod[];
  is_known_fraud: boolean;
}

export interface ReconciliationCheck {
  name: string;
  result: string;
  details: string;
  tolerance: string;
  passed: boolean;
}

export interface ReconciliationAnalysis {
  passed: boolean;
  summary: string;
  checks: ReconciliationCheck[];
  red_flags: RedFlag[];
}

export interface QuantAnalysis {
  beneish_mscore: number | null;
  beneish_interpretation: string | null;
  altman_zscore: number | null;
  altman_interpretation: string | null;
  accruals_ratio: number | null;
  summary: string;
}

export interface Evidence {
  quote: string;
  context: string;
  page?: number;
}

export interface InvestigationAnalysis {
  summary: string;
  evasive_language_detected: boolean;
  related_parties_detected: string[];
  mdna_findings: string | null;
  risk_factors_summary: string | null;
  key_quotes: Evidence[];
  red_flags: RedFlag[];
}

export interface FinalReport {
  executive_summary: string;
  recommendations: string[];
  consolidated_red_flags: RedFlag[];
  audit_conclusion: AuditConclusion;
  risk_score: number;
  risk_level: RiskLevel;
  reconciliation: ReconciliationAnalysis;
  quant_analysis: QuantAnalysis;
  investigation: InvestigationAnalysis;
  company_data: CompanyData;
}

export interface AuditCompletedEvent extends AuditEventBase {
  event_type: "audit_completed";
  final_report: FinalReport;
  risk_score: number;
  risk_level: RiskLevel;
  conclusion: AuditConclusion;
  total_tokens: number;
  total_cost_usd: number;
  total_duration_seconds: number;
  needs_human_review: boolean;
}

export interface AuditFailedEvent extends AuditEventBase {
  event_type: "audit_failed";
  failed_phase: AuditPhase;
  error_message: string;
}

export type AuditEvent =
  | AuditStartedEvent
  | PhaseStartedEvent
  | ToolCalledEvent
  | ToolCompletedEvent
  | PhaseCompletedEvent
  | PhaseFailedEvent
  | AuditCompletedEvent
  | AuditFailedEvent;
