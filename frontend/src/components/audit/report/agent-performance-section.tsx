"use client";

import { Cpu, CheckCircle2, Clock, XCircle, Loader2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { AuditPhase, PhaseState } from "@/types/audit";
import { formatCost, formatTokens } from "@/lib/utils";

const PHASE_ORDER: AuditPhase[] = ["collector", "reconciler", "quant_analyst", "investigator", "supervisor"];

interface AgentPerformanceSectionProps {
  phases: Record<string, PhaseState>;
}

export function AgentPerformanceSection({ phases }: AgentPerformanceSectionProps) {
  const totalTokens = Object.values(phases).reduce((sum, phase) => sum + phase.tokensUsed, 0);
  const totalCost = Object.values(phases).reduce((sum, phase) => sum + phase.costUsd, 0);
  const totalDuration = Object.values(phases).reduce((sum, phase) => sum + (phase.duration || 0), 0);

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <Cpu className="w-6 h-6 text-primary" />
          Agent Performance
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        <div className="border rounded-2xl overflow-hidden bg-muted/10 shadow-sm">
          <table className="w-full text-left border-collapse">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-muted-foreground">Agent</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-muted-foreground text-center">Status</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-muted-foreground text-right">Tokens</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-muted-foreground text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {PHASE_ORDER.map((phaseKey) => {
                const phase = phases[phaseKey];
                if (!phase) return null;

                return (
                  <tr key={phaseKey} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-bold text-neutral-800">{phase.agentName}</div>
                      {phase.duration !== null && (
                        <div className="text-[10px] text-muted-foreground flex items-center gap-1 uppercase font-black tracking-tight">
                          <Clock className="w-2.5 h-2.5" />
                          {phase.duration.toFixed(1)}s latency
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-center">
                         {phase.status === "completed" && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                         {phase.status === "failed" && <XCircle className="w-5 h-5 text-rose-500" />}
                         {phase.status === "running" && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                         {phase.status === "pending" && <div className="w-5 h-5 rounded-full border-2 border-muted" />}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm text-neutral-700">
                      {formatTokens(phase.tokensUsed)}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm text-neutral-900 font-medium">
                      {formatCost(phase.costUsd)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-muted/30 border-t font-black">
              <tr className="text-neutral-900">
                <td className="px-6 py-5" colSpan={2}>
                  <div className="flex items-center gap-2">
                    Audit Performance Total
                    <span className="text-[10px] font-black bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                      {totalDuration.toFixed(1)}s
                    </span>
                  </div>
                </td>
                <td className="px-6 py-5 text-right font-mono text-lg">{formatTokens(totalTokens)}</td>
                <td className="px-6 py-5 text-right font-mono text-lg">{formatCost(totalCost)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
