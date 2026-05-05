"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type {
  IngestionEvent,
  IngestionStage,
  IngestionCompletedEvent,
  IngestionFailedEvent,
} from "@/types/ingestion";

export type {
  IngestionEvent,
  IngestionStage,
  IngestionCompletedEvent,
  IngestionFailedEvent,
};
import { IngestionStreamClient } from "@/lib/sse/ingestion-stream";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type StageStatus = "pending" | "running" | "completed" | "failed";

export interface StageProgress {
  current: number;
  total: number;
  message: string;
}

export interface StageState {
  stage: IngestionStage;
  label: string;
  status: StageStatus;
  startedAt: number | null;
  completedAt: number | null;
  duration: number | null;
  summary: Record<string, unknown> | null;
  progress: StageProgress | null;
  errorMessage: string | null;
}

export interface CompanyInfo {
  cik: string;
  name: string | null;
  ticker: string | null;
  isUpdate: boolean;
}

export interface IngestionStreamState {
  connected: boolean;
  stages: Record<IngestionStage, StageState>;
  currentStage: IngestionStage | null;
  companyInfo: CompanyInfo | null;
  result: IngestionCompletedEvent | null;
  failure: IngestionFailedEvent | null;
  events: IngestionEvent[];
  elapsedSeconds: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const STAGE_ORDER: IngestionStage[] = [
  "validate",
  "download_facts",
  "download_filings",
  "parse_xbrl",
  "embed_text",
];

const STAGE_LABELS: Record<IngestionStage, string> = {
  validate: "Validate CIK",
  download_facts: "Download Company Facts",
  download_filings: "Download Filings",
  parse_xbrl: "Parse Financial Data",
  embed_text: "Generate Embeddings",
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function createInitialStages(): Record<IngestionStage, StageState> {
  const stages = {} as Record<IngestionStage, StageState>;
  for (const stage of STAGE_ORDER) {
    stages[stage] = {
      stage,
      label: STAGE_LABELS[stage],
      status: "pending",
      startedAt: null,
      completedAt: null,
      duration: null,
      summary: null,
      progress: null,
      errorMessage: null,
    };
  }
  return stages;
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export function useIngestionStream(ingestionId: string | null) {
  const [state, setState] = useState<IngestionStreamState>({
    connected: false,
    stages: createInitialStages(),
    currentStage: null,
    companyInfo: null,
    result: null,
    failure: null,
    events: [],
    elapsedSeconds: 0,
  });

  const clientRef = useRef<IngestionStreamClient | null>(null);

  const handleEvent = useCallback((event: IngestionEvent) => {
    setState((prev) => {
      const newEvents = [...prev.events, event];
      const newStages = { ...prev.stages };
      let newCurrentStage = prev.currentStage;
      let newCompanyInfo = prev.companyInfo;
      let newResult = prev.result;
      let newFailure = prev.failure;
      let newElapsedSeconds = event.elapsed_seconds ?? prev.elapsedSeconds;

      switch (event.event_type) {
        case "ingestion_started":
          newCompanyInfo = {
            cik: event.cik,
            name: event.company_name,
            ticker: null,
            isUpdate: event.is_update,
          };
          break;

        case "stage_started": {
          const stageKey = event.stage;
          newStages[stageKey] = {
            ...newStages[stageKey],
            status: "running",
            startedAt: event.elapsed_seconds,
            progress: null,
          };
          newCurrentStage = stageKey;
          break;
        }

        case "stage_progress": {
          const progressStage = event.stage;
          newStages[progressStage] = {
            ...newStages[progressStage],
            progress: {
              current: event.current,
              total: event.total,
              message: event.message,
            },
          };
          break;
        }

        case "stage_completed": {
          const completedStage = event.stage;
          newStages[completedStage] = {
            ...newStages[completedStage],
            status: "completed",
            completedAt: event.elapsed_seconds,
            duration: event.duration_seconds,
            summary: event.summary,
          };

          // Advance currentStage to next pending stage
          const currentIdx = STAGE_ORDER.indexOf(completedStage);
          const nextIdx = currentIdx + 1;
          newCurrentStage =
            nextIdx < STAGE_ORDER.length ? STAGE_ORDER[nextIdx] : null;
          break;
        }

        case "ingestion_completed":
          newResult = event;
          newCurrentStage = null;
          newElapsedSeconds = event.total_duration_seconds;

          // Update company info with final data
          if (newCompanyInfo) {
            newCompanyInfo = {
              ...newCompanyInfo,
              name: event.company_name,
              ticker: event.ticker,
            };
          }

          // Mark any remaining stages as completed
          for (const stage of STAGE_ORDER) {
            if (newStages[stage].status !== "completed") {
              newStages[stage] = {
                ...newStages[stage],
                status: "completed",
              };
            }
          }
          break;

        case "ingestion_failed":
          newFailure = event;
          // Mark the failed stage
          if (newCurrentStage) {
            newStages[newCurrentStage] = {
              ...newStages[newCurrentStage],
              status: "failed",
              errorMessage: event.error_message,
            };
          }
          newCurrentStage = null;
          break;
      }

      return {
        ...prev,
        events: newEvents,
        stages: newStages,
        currentStage: newCurrentStage,
        companyInfo: newCompanyInfo,
        result: newResult,
        failure: newFailure,
        elapsedSeconds: newElapsedSeconds,
      };
    });
  }, []);

  useEffect(() => {
    if (!ingestionId) return;

    const client = new IngestionStreamClient(ingestionId, {
      onOpen: () => {
        setState((prev) => ({ ...prev, connected: true }));
      },
      onEvent: handleEvent,
      onError: (err) => {
        console.error("Ingestion SSE error", err);
      },
      onClose: () => {
        setState((prev) => ({ ...prev, connected: false }));
      },
    });

    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [ingestionId, handleEvent]);

  const isComplete = state.result !== null || state.failure !== null;

  return {
    ...state,
    isComplete,
  };
}

export { STAGE_ORDER, STAGE_LABELS };
