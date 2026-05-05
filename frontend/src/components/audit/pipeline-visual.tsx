"use client";

import { motion } from "framer-motion";
import { Check, X, Loader2 } from "lucide-react";
import type { PhaseState, AuditPhase } from "@/types/audit";

interface PipelineVisualProps {
  phases: Record<AuditPhase, PhaseState>;
}

const PHASE_ORDER: AuditPhase[] = [
  "collector",
  "reconciler",
  "quant_analyst",
  "investigator",
  "supervisor",
];

const PHASE_SHORT_NAMES: Record<AuditPhase, string> = {
  collector: "Collector",
  reconciler: "Reconciler",
  quant_analyst: "Quant",
  investigator: "Investigator",
  supervisor: "Supervisor",
};

export function PipelineVisual({ phases }: PipelineVisualProps) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-8 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        {PHASE_ORDER.map((phase, index) => {
          const phaseState = phases[phase];
          const isLast = index === PHASE_ORDER.length - 1;
          
          return (
            <div key={phase} className="flex items-center flex-1 last:flex-none">
              <PhaseNode phase={phase} state={phaseState} />
              {!isLast && <PhaseConnector status={phaseState.status} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PhaseNode({ phase, state }: { phase: AuditPhase; state: PhaseState }) {
  const { status } = state;
  
  return (
    <div className="flex flex-col items-center gap-3 shrink-0">
      <div className="relative">
        {/* Pulse animation for the active running phase */}
        {status === "running" && (
          <motion.div
            className="absolute inset-0 rounded-full bg-blue-500"
            animate={{
              scale: [1, 1.4, 1],
              opacity: [0.3, 0, 0.3],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        )}
        
        <div
          className={`
            relative w-12 h-12 rounded-full flex items-center justify-center
            transition-all duration-500 border-2
            ${status === "pending" ? "bg-white border-neutral-100 text-neutral-300" : ""}
            ${status === "running" ? "bg-blue-500 border-blue-500 text-white shadow-lg" : ""}
            ${status === "completed" ? "bg-emerald-500 border-emerald-500 text-white" : ""}
            ${status === "failed" ? "bg-red-500 border-red-500 text-white" : ""}
          `}
        >
          {status === "pending" && (
            <span className="text-xs font-bold">
              {PHASE_ORDER.indexOf(phase) + 1}
            </span>
          )}
          {status === "running" && <Loader2 className="w-5 h-5 animate-spin" />}
          {status === "completed" && <Check className="w-5 h-5" strokeWidth={3} />}
          {status === "failed" && <X className="w-5 h-5" strokeWidth={3} />}
        </div>
      </div>
      
      <div className="text-center">
        <div className={`text-sm font-semibold transition-colors duration-300 ${status === "pending" ? "text-neutral-300" : "text-neutral-900"}`}>
          {PHASE_SHORT_NAMES[phase]}
        </div>
        <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-400 mt-1 h-4">
          {status === "running" && (
            <span className="text-blue-500 animate-pulse">Running</span>
          )}
          {status === "completed" && state.duration && (
            <span className="text-emerald-600">{state.duration.toFixed(0)}s</span>
          )}
          {status === "failed" && (
            <span className="text-red-500">Failed</span>
          )}
        </div>
      </div>
    </div>
  );
}

function PhaseConnector({ status }: { status: PhaseState["status"] }) {
  return (
    <div className="flex-1 h-[2px] mx-4 relative top-[-22px]">
      <div className="w-full h-full bg-neutral-100" />
      {status === "completed" && (
        <motion.div
          className="absolute inset-0 bg-emerald-500"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          style={{ originX: 0 }}
          transition={{ duration: 0.6, ease: "circOut" }}
        />
      )}
    </div>
  );
}
