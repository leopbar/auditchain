"use client";

import { use, useEffect, useState } from "react";
import { useAuditStream } from "@/hooks/use-audit-stream";
import { AuditHeader } from "@/components/audit/audit-header";
import { PipelineVisual } from "@/components/audit/pipeline-visual";
import { CurrentPhasePanel } from "@/components/audit/current-phase-panel";
import { CompletedPhases } from "@/components/audit/completed-phases";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, Loader2 } from "lucide-react";
import { AuditReport } from "@/components/audit/report/audit-report";
import { getAuditDetail, ApiError } from "@/lib/api/client";
import { AuditDetail, FinalReport } from "@/types/audit";
import { buildPhasesFromAuditDetail } from "@/lib/build-phases-from-detail";

interface PageProps {
  params: Promise<{ run_id: string }>;
}

export default function AuditPage({ params }: PageProps) {
  const { run_id } = use(params);
  
  const [historicalData, setHistoricalData] = useState<AuditDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDetail() {
      try {
        const detail = await getAuditDetail(run_id);
        setHistoricalData(detail);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setError("Audit not found");
        } else {
          setError("Failed to load audit details");
        }
      } finally {
        setIsLoading(false);
      }
    }
    fetchDetail();
  }, [run_id]);

  // Only enable stream if the audit is still running
  const isRunningHistorical = historicalData?.status === "running";
  const stream = useAuditStream(run_id, isRunningHistorical || isLoading);
  
  if (isLoading) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-primary animate-spin" />
          <p className="text-sm font-medium text-muted-foreground">Initializing audit view...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="bg-white border border-neutral-200 rounded-2xl p-8 max-w-md text-center shadow-sm">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold mb-2">{error}</h1>
          <p className="text-neutral-500 mb-6">The audit you are looking for might have been deleted or never existed.</p>
          <button 
            onClick={() => window.location.href = "/"}
            className="px-6 py-2 bg-neutral-900 text-white rounded-lg font-medium hover:bg-neutral-800 transition-colors"
          >
            Go back home
          </button>
        </div>
      </div>
    );
  }

  // Use historical data if completed, otherwise use stream data
  const isHistorical = historicalData?.status === "completed" && historicalData.final_report;
  
  // Build phases and other data based on mode
  const phases = isHistorical 
    ? buildPhasesFromAuditDetail(historicalData!) 
    : stream.phases;

  const totalTokens = isHistorical ? (historicalData?.total_tokens || 0) : stream.totalTokens;
  const totalCost = isHistorical ? (historicalData?.total_cost_usd || 0) : stream.totalCost;
  const elapsedSeconds = isHistorical 
    ? (historicalData?.completed_at && historicalData?.started_at 
        ? (new Date(historicalData.completed_at).getTime() - new Date(historicalData.started_at).getTime()) / 1000 
        : 0)
    : stream.elapsedSeconds;

  const finalReport = isHistorical 
    ? (historicalData?.final_report as unknown as FinalReport) 
    : stream.finalReport?.final_report;

  const failure = historicalData?.status === "failed" 
    ? { failed_phase: "unknown", error_message: "This audit failed during processing." } 
    : stream.failure;

  const companyName = historicalData?.company_name || "Audit Details";
  const companyTicker = historicalData?.company_ticker ?? null;

  let headerStatus: "running" | "completed" | "failed" = "running";
  if (isHistorical || stream.finalReport) headerStatus = "completed";
  else if (failure) headerStatus = "failed";

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col">
      <AuditHeader
        companyName={companyName}
        companyTicker={companyTicker}
        status={headerStatus}
        elapsedSeconds={elapsedSeconds}
        totalTokens={totalTokens}
        totalCost={totalCost}
      />
      
      <main className="container mx-auto px-6 py-12 max-w-5xl flex-1 space-y-10">
        <PipelineVisual phases={phases} />
        
        <div className="grid grid-cols-1 gap-10">
          <AnimatePresence mode="wait">
            {stream.currentPhase && stream.phases[stream.currentPhase].status === "running" && (
              <CurrentPhasePanel
                key={stream.currentPhase}
                phase={stream.phases[stream.currentPhase]}
              />
            )}
          </AnimatePresence>
          
          {failure && (
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="bg-red-50 border border-red-200 rounded-xl p-6 shadow-sm"
            >
              <div className="flex items-center gap-3 text-red-900 font-bold mb-2">
                <AlertCircle className="w-5 h-5" />
                Audit Execution Halted
              </div>
              <div className="text-sm text-red-700 font-medium">
                The investigation failed: {failure.error_message}
              </div>
            </motion.div>
          )}
          
          {finalReport && (
            <motion.div 
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 }}
            >
              <AuditReport 
                report={finalReport} 
                phases={phases}
                durationSeconds={elapsedSeconds}
                totalTokens={totalTokens}
                totalCost={totalCost}
                needsHumanReview={historicalData?.needs_human_review || stream.finalReport?.needs_human_review || false}
              />
            </motion.div>
          )}
          
          <CompletedPhases 
            phases={phases} 
            title={finalReport ? "Detailed Phase Logs" : "Audit History"} 
          />
        </div>
      </main>
      
      <footer className="border-t border-neutral-200 bg-white/50 backdrop-blur-sm py-4">
        <div className="container mx-auto px-6 max-w-5xl flex items-center justify-between">
          <div className="flex items-center gap-3 text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
            <span className={`w-2 h-2 rounded-full ${stream.connected ? "bg-emerald-500 animate-pulse" : "bg-neutral-300"}`} />
            {stream.connected ? "Real-time Node Connected" : (isHistorical ? "Viewing Historical Record" : "Stream Disconnected")}
          </div>
          <div className="flex items-center gap-4 text-[10px] font-bold text-neutral-500 tabular-nums uppercase">
             {isHistorical ? "ARCHIVED REPORT" : `${stream.events.length} TELEMETRY PACKETS RECEIVED`}
          </div>
        </div>
      </footer>
    </div>
  );
}
