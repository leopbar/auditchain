"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, CheckCircle2, XCircle, Coins, Zap, Flag } from "lucide-react";
import { formatDuration, formatCost, formatTokens } from "@/lib/utils";
import type { PhaseState, AuditPhase } from "@/types/audit";

interface CompletedPhasesProps {
  phases: Record<AuditPhase, PhaseState>;
  title?: string;
}

const PHASE_ORDER: AuditPhase[] = [
  "collector",
  "reconciler",
  "quant_analyst",
  "investigator",
  "supervisor",
];

export function CompletedPhases({ phases, title = "Audit History" }: CompletedPhasesProps) {
  const completed = PHASE_ORDER
    .map((p) => phases[p])
    .filter((p) => p.status === "completed" || p.status === "failed");
  
  if (completed.length === 0) return null;
  
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
          {title} ({completed.length})
        </h2>
      </div>
      
      <div className="space-y-2">
        {completed.map((phase) => (
          <PhaseAccordion key={phase.phase} phase={phase} />
        ))}
      </div>
    </div>
  );
}

function PhaseAccordion({ phase }: { phase: PhaseState }) {
  const [expanded, setExpanded] = useState(false);
  const isFailed = phase.status === "failed";
  
  return (
    <div className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden transition-all">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center gap-4 hover:bg-neutral-50 transition-colors text-left"
      >
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isFailed ? "bg-red-50 text-red-500" : "bg-emerald-50 text-emerald-600"}`}>
          {isFailed ? (
            <XCircle className="w-5 h-5" />
          ) : (
            <CheckCircle2 className="w-5 h-5" />
          )}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-neutral-900 text-sm">{phase.agentName}</span>
            {phase.duration !== null && (
              <span className="text-[10px] font-bold text-neutral-400">
                {formatDuration(phase.duration)}
              </span>
            )}
          </div>
          <PhaseSummaryLine phase={phase} />
        </div>
        
        <div className="flex items-center gap-4 shrink-0">
          {phase.redFlagsAdded > 0 && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-100">
              <Flag className="w-3 h-3" />
              <span className="text-[10px] font-bold">{phase.redFlagsAdded}</span>
            </div>
          )}
          <ChevronDown
            className={`w-4 h-4 text-neutral-300 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>
      
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-neutral-100"
          >
            <div className="p-6 space-y-6 bg-neutral-50/30">
              {/* Metrics Grid */}
              <div className="grid grid-cols-3 gap-6">
                <MetricItem label="Tokens" value={formatTokens(phase.tokensUsed)} icon={<Zap className="w-3 h-3" />} />
                <MetricItem label="Cost" value={formatCost(phase.costUsd)} icon={<Coins className="w-3 h-3" />} />
                <MetricItem label="Findings" value={phase.redFlagsAdded.toString()} icon={<Flag className="w-3 h-3" />} />
              </div>
              
              {/* Findings Summary */}
              {phase.summary && Object.keys(phase.summary).length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
                    Phase Execution Summary
                  </h4>
                  <div className="bg-white border border-neutral-200 rounded-lg p-4 space-y-3">
                    {Object.entries(phase.summary).map(([key, value]) => (
                      <div key={key} className="flex items-start gap-3 text-sm">
                        <span className="text-neutral-400 shrink-0 capitalize font-medium min-w-[120px]">
                          {key.replaceAll("_", " ")}
                        </span>
                        <span className="text-neutral-800 font-mono text-xs leading-relaxed">
                          {formatSummaryValue(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Internal Logs / Tool Executions */}
              {phase.toolCalls.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
                    Forensic Trace ({phase.toolCalls.length})
                  </h4>
                  <div className="space-y-1.5">
                    {phase.toolCalls.map((tool, idx) => (
                      <div
                        key={`${tool.toolName}-${idx}`}
                        className="flex items-center justify-between text-xs py-2 px-3 bg-white border border-neutral-100 rounded-md shadow-sm"
                      >
                        <div className="flex items-center gap-3">
                          {tool.success ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5 text-red-500" />
                          )}
                          <span className="font-mono text-neutral-600">
                            {tool.toolName}
                          </span>
                        </div>
                        {tool.durationMs !== null && (
                          <span className="text-neutral-400 font-bold tabular-nums">
                            {tool.durationMs}ms
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Error Detail */}
              {phase.errorMessage && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="text-[10px] font-bold text-red-700 uppercase tracking-widest mb-2">Failure Trace</div>
                  <div className="text-xs text-red-900 font-mono leading-relaxed bg-white/50 p-2 rounded border border-red-100">
                    {phase.errorMessage}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MetricItem({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
        {icon} {label}
      </div>
      <div className="font-mono text-sm font-semibold text-neutral-900">
        {value}
      </div>
    </div>
  );
}

function PhaseSummaryLine({ phase }: { phase: PhaseState }) {
  if (!phase.summary) return null;
  const s = phase.summary as Record<string, unknown>;
  
  let line = "";
  switch (phase.phase) {
    case "collector":
      if (s.company_name && s.filings_count) {
        line = `${s.company_name} · ${s.filings_count} reports found`;
      }
      break;
    case "reconciler":
      if (typeof s.passed === "boolean") {
        line = s.passed
          ? `${s.checks_count || "?"} accounting checks verified`
          : `Mathematical inconsistencies detected`;
      }
      break;
    case "quant_analyst":
      if (s.beneish_mscore !== undefined && s.altman_zscore !== undefined) {
        line = `M-Score: ${(s.beneish_mscore as number).toFixed(2)} · Z-Score: ${(s.altman_zscore as number).toFixed(2)}`;
      }
      break;
    case "investigator":
      const evasive = s.evasive_language ? "Evasive language detected" : "No linguistic anomalies";
      line = evasive;
      break;
    case "supervisor":
      if (s.conclusion && s.risk_score !== undefined) {
        line = `${(s.conclusion as string).toUpperCase()} verdict · ${(s.risk_score as number).toFixed(0)}% risk`;
      }
      break;
  }
  
  if (!line) return null;
  return <div className="text-xs text-neutral-500 mt-1 font-medium truncate opacity-70">{line}</div>;
}

function formatSummaryValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Verified" : "Unverified";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(4);
  }
  if (typeof value === "string") return value.length > 200 ? value.slice(0, 200) + "..." : value;
  if (Array.isArray(value)) return `${value.length} items detected`;
  return JSON.stringify(value);
}
