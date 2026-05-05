import { AuditDetail, AuditPhase, PhaseState, PhaseStatus } from "@/types/audit";

/**
 * Builds a Record of PhaseState objects from an AuditDetail fetched from the database.
 * This allows reusing UI components that expect the real-time phase structure.
 */
export function buildPhasesFromAuditDetail(detail: AuditDetail): Record<AuditPhase, PhaseState> {
  const phases: Record<AuditPhase, PhaseState> = {
    collector: createDefaultPhase("collector", "Data Collector"),
    reconciler: createDefaultPhase("reconciler", "Financial Reconciler"),
    quant_analyst: createDefaultPhase("quant_analyst", "Quant Analyst"),
    investigator: createDefaultPhase("investigator", "Fraud Investigator"),
    supervisor: createDefaultPhase("supervisor", "Audit Supervisor"),
  };

  // Populate from agent_steps
  detail.agent_steps.forEach((step) => {
    const phaseKey = step.agent_name as AuditPhase;
    if (phases[phaseKey]) {
      const tokens = (step.tokens_input || 0) + (step.tokens_output || 0);
      
      phases[phaseKey].status = detail.status === "completed" ? "completed" : 
                                detail.status === "failed" ? "failed" : "completed";
      phases[phaseKey].tokensUsed = tokens;
      phases[phaseKey].costUsd = step.cost_usd || 0;
      phases[phaseKey].duration = step.latency_ms ? step.latency_ms / 1000 : null;
    }
  });

  // If the audit is completed, ensure all relevant phases are marked as completed
  if (detail.status === "completed") {
    Object.keys(phases).forEach((k) => {
      const key = k as AuditPhase;
      // We assume if it's in historical mode and status is completed, the phases we have steps for are done.
      // If we don't have a step for a phase but the audit is completed, it might have been skipped or it's the supervisor.
      if (phases[key].tokensUsed > 0 || key === "supervisor") {
        phases[key].status = "completed";
      }
    });
  }

  return phases;
}

function createDefaultPhase(phase: AuditPhase, agentName: string): PhaseState {
  return {
    phase,
    agentName,
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
