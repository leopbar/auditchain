// ───────────────────────────────────────────────────────────
// Ingestion Pipeline Types
// Mirrors Python schemas in:
//   src/auditchain/schemas/ingestion.py
//   src/auditchain/api/events/ingestion_schemas.py
// ───────────────────────────────────────────────────────────

export type IngestionStage =
  | "validate"
  | "download_facts"
  | "download_filings"
  | "parse_xbrl"
  | "embed_text";

export type IngestionStatus = "running" | "completed" | "failed";

export interface IngestionRun {
  id: string;
  cik: string;
  status: IngestionStatus;
  current_stage: IngestionStage | null;
  stages_completed: string[];
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  filings_count: number | null;
  chunks_generated: number | null;
  financial_items_extracted: number | null;
  is_update: boolean;
}

export interface CreateIngestionRequest {
  cik: string;
  force_update?: boolean;
}

export interface CreateIngestionResponse {
  ingestion_id: string;
  status: string;
  message: string;
  stream_url: string;
}

// ───────────────────────────────────────────────────────────
// SSE Events
// ───────────────────────────────────────────────────────────

export type IngestionEventType =
  | "ingestion_started"
  | "stage_started"
  | "stage_progress"
  | "stage_completed"
  | "ingestion_completed"
  | "ingestion_failed";

export interface IngestionEventBase {
  event_type: IngestionEventType;
  ingestion_id: string;
  timestamp: string;
  elapsed_seconds: number;
}

export interface IngestionStartedEvent extends IngestionEventBase {
  event_type: "ingestion_started";
  cik: string;
  company_name: string | null;
  is_update: boolean;
}

export interface StageStartedEvent extends IngestionEventBase {
  event_type: "stage_started";
  stage: IngestionStage;
  description: string;
}

export interface StageProgressEvent extends IngestionEventBase {
  event_type: "stage_progress";
  stage: IngestionStage;
  current: number;
  total: number;
  message: string;
}

export interface StageCompletedEvent extends IngestionEventBase {
  event_type: "stage_completed";
  stage: IngestionStage;
  duration_seconds: number;
  summary: Record<string, unknown>;
}

export interface IngestionCompletedEvent extends IngestionEventBase {
  event_type: "ingestion_completed";
  cik: string;
  company_name: string;
  ticker: string | null;
  filings_count: number;
  chunks_generated: number;
  financial_items_extracted: number;
  total_duration_seconds: number;
}

export interface IngestionFailedEvent extends IngestionEventBase {
  event_type: "ingestion_failed";
  failed_stage: string;
  error_message: string;
}

export type IngestionEvent =
  | IngestionStartedEvent
  | StageStartedEvent
  | StageProgressEvent
  | StageCompletedEvent
  | IngestionCompletedEvent
  | IngestionFailedEvent;
