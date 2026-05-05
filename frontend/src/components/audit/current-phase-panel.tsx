"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Loader2, CheckCircle2, XCircle, Wrench } from "lucide-react";
import type { PhaseState } from "@/types/audit";

interface CurrentPhasePanelProps {
  phase: PhaseState;
}

const PHASE_DESCRIPTIONS: Record<string, string> = {
  collector: "Gathering financial data from SEC EDGAR filings",
  reconciler: "Verifying mathematical consistency of accounting figures",
  quant_analyst: "Computing forensic models (Beneish M-Score, Altman Z-Score)",
  investigator: "Analyzing qualitative disclosures via semantic search",
  supervisor: "Consolidating findings and generating final audit report",
};

export function CurrentPhasePanel({ phase }: CurrentPhasePanelProps) {
  const description = PHASE_DESCRIPTIONS[phase.phase] || "Processing...";
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden"
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-100 p-6">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-blue-500 flex items-center justify-center shadow-md shrink-0">
            <Loader2 className="w-5 h-5 text-white animate-spin" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-neutral-900">{phase.agentName}</h3>
              <div className="px-2 py-0.5 rounded-full bg-blue-100 text-[10px] text-blue-700 font-bold uppercase tracking-wider animate-pulse">
                Running
              </div>
            </div>
            <p className="text-sm text-neutral-600 mt-1">{description}</p>
          </div>
        </div>
      </div>
      
      {/* Tool calls activity */}
      <div className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Wrench className="w-4 h-4 text-neutral-400" />
          <span className="text-xs font-bold text-neutral-500 uppercase tracking-widest">
            Agent Reasoning & Tools
          </span>
        </div>
        
        {phase.toolCalls.length === 0 ? (
          <div className="text-sm text-neutral-400 italic py-4 flex items-center gap-2">
            <motion.span
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              Agent is analyzing data...
            </motion.span>
          </div>
        ) : (
          <div className="space-y-2">
            <AnimatePresence initial={false}>
              {phase.toolCalls.slice(-5).map((tool, idx) => (
                <motion.div
                  key={`${tool.toolName}-${idx}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center justify-between text-sm py-2 px-3 rounded-lg bg-neutral-50 border border-neutral-100"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {tool.completedAt === null ? (
                      <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin shrink-0" />
                    ) : tool.success ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                    )}
                    <span className="font-mono text-xs text-neutral-700 truncate">
                      {tool.toolName}
                    </span>
                  </div>
                  
                  {tool.durationMs !== null && (
                    <span className="text-[10px] font-bold text-neutral-400 tabular-nums shrink-0 ml-2">
                      {tool.durationMs}ms
                    </span>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {phase.toolCalls.length > 5 && (
              <div className="text-[10px] text-neutral-400 text-center pt-1">
                + {phase.toolCalls.length - 5} more actions
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
