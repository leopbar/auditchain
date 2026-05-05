"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type {
  AuditEvent,
  AuditPhase,
  PhaseStatus,
  AuditCompletedEvent,
  AuditFailedEvent,
  PhaseState,
  ToolCallState,
} from "@/types/audit";
import { AuditStreamClient } from "@/lib/sse/audit-stream";

export interface AuditStreamState {
  connected: boolean;
  events: AuditEvent[];
  phases: Record<AuditPhase, PhaseState>;
  currentPhase: AuditPhase | null;
  finalReport: AuditCompletedEvent | null;
  failure: AuditFailedEvent | null;
  totalTokens: number;
  totalCost: number;
  elapsedSeconds: number;
}

const PHASE_ORDER: AuditPhase[] = [
  "collector",
  "reconciler",
  "quant_analyst",
  "investigator",
  "supervisor",
];

const AGENT_NAMES: Record<AuditPhase, string> = {
  collector: "Collector Agent",
  reconciler: "Reconciler Agent",
  quant_analyst: "Quantitative Analyst",
  investigator: "Investigator Agent",
  supervisor: "Supervisor Agent",
};

function createInitialPhases(): Record<AuditPhase, PhaseState> {
  const phases = {} as Record<AuditPhase, PhaseState>;
  for (const phase of PHASE_ORDER) {
    phases[phase] = {
      phase,
      agentName: AGENT_NAMES[phase],
      status: "pending",
      startedAt: null,
      completedAt: null,
      duration: null,
      tokensUsed: 0,
      costUsd: 0,
      summary: null,
      redFlagsAdded: 0,
      errorMessage: null,
      toolCalls: [],
    };
  }
  return phases;
}

export function useAuditStream(runId: string | null, enabled: boolean = true) {
  const [state, setState] = useState<AuditStreamState>({
    connected: false,
    events: [],
    phases: createInitialPhases(),
    currentPhase: null,
    finalReport: null,
    failure: null,
    totalTokens: 0,
    totalCost: 0,
    elapsedSeconds: 0,
  });
  
  const clientRef = useRef<AuditStreamClient | null>(null);
  
  const handleEvent = useCallback((event: AuditEvent) => {
    setState((prev) => {
      const newEvents = [...prev.events, event];
      const newPhases = { ...prev.phases };
      let newCurrentPhase = prev.currentPhase;
      let newFinalReport = prev.finalReport;
      let newFailure = prev.failure;
      let newTotalTokens = prev.totalTokens;
      let newTotalCost = prev.totalCost;
      
      let newElapsedSeconds = event.elapsed_seconds ?? prev.elapsedSeconds;
      
      switch (event.event_type) {
        case "phase_started":
          newPhases[event.phase] = {
            ...newPhases[event.phase],
            status: "running",
            startedAt: event.elapsed_seconds,
            agentName: event.agent_name,
          };
          newCurrentPhase = event.phase;
          break;
        
        case "tool_called":
          newPhases[event.phase] = {
            ...newPhases[event.phase],
            toolCalls: [
              ...newPhases[event.phase].toolCalls,
              {
                toolName: event.tool_name,
                startedAt: event.elapsed_seconds,
                completedAt: null,
                durationMs: null,
                success: null,
                input: event.tool_input,
              },
            ],
          };
          break;
        
        case "tool_completed": {
          const toolCalls = [...newPhases[event.phase].toolCalls];
          // Update most recent tool call for this phase/tool
          for (let i = toolCalls.length - 1; i >= 0; i--) {
            if (
              toolCalls[i].toolName === event.tool_name &&
              toolCalls[i].completedAt === null
            ) {
              toolCalls[i] = {
                ...toolCalls[i],
                completedAt: event.elapsed_seconds,
                durationMs: event.duration_ms,
                success: event.success,
              };
              break;
            }
          }
          newPhases[event.phase] = {
            ...newPhases[event.phase],
            toolCalls,
          };
          break;
        }
        
        case "phase_completed":
          newPhases[event.phase] = {
            ...newPhases[event.phase],
            status: "completed",
            completedAt: event.elapsed_seconds,
            duration: event.duration_seconds,
            tokensUsed: event.tokens_used,
            costUsd: event.cost_usd,
            summary: event.summary,
            redFlagsAdded: event.red_flags_added,
          };
          newTotalTokens = event.tokens_used;
          newTotalCost = event.cost_usd;
          break;
        
        case "phase_failed":
          newPhases[event.phase] = {
            ...newPhases[event.phase],
            status: "failed",
            errorMessage: event.error_message,
          };
          break;
        
        case "audit_completed":
          newFinalReport = event;
          newTotalTokens = event.total_tokens;
          newTotalCost = event.total_cost_usd;
          newCurrentPhase = null;
          newElapsedSeconds = event.total_duration_seconds;
          break;
        
        case "audit_failed":
          newFailure = event;
          newCurrentPhase = null;
          break;
      }
      
      return {
        ...prev,
        events: newEvents,
        phases: newPhases,
        currentPhase: newCurrentPhase,
        finalReport: newFinalReport,
        failure: newFailure,
        totalTokens: newTotalTokens,
        totalCost: newTotalCost,
        elapsedSeconds: newElapsedSeconds,
      };
    });
  }, []);
  
  useEffect(() => {
    if (!runId || !enabled) return;
    
    const client = new AuditStreamClient(runId, {
      onOpen: () => {
        setState((prev) => ({ ...prev, connected: true }));
      },
      onEvent: handleEvent,
      onError: (err) => {
        console.error("SSE error", err);
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
  }, [runId, handleEvent]);
  
  const isComplete = state.finalReport !== null || state.failure !== null;
  
  return {
    ...state,
    isComplete,
  };
}
