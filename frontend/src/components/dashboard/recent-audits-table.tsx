"use client";

import { AuditSummary } from "@/types/audit";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow } from "date-fns";
import { formatDuration } from "@/lib/utils";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface RecentAuditsTableProps {
  audits: AuditSummary[];
}

export function RecentAuditsTable({ audits }: RecentAuditsTableProps) {
  const displayAudits = audits.slice(0, 5);

  const getConclusionColor = (conclusion: string | null) => {
    switch (conclusion) {
      case "clean": return "bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20";
      case "qualified": return "bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20";
      case "adverse": return "bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20";
      default: return "bg-muted text-muted-foreground border-transparent";
    }
  };

  const getScoreColor = (score: number | null) => {
    if (score === null) return "text-muted-foreground";
    if (score < 25) return "text-emerald-500";
    if (score < 50) return "text-amber-500";
    if (score < 75) return "text-orange-500";
    return "text-rose-500";
  };

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Latest Audit Reports</h3>
        <Link 
          href="/audits" 
          className="text-sm font-medium text-primary hover:underline flex items-center gap-1"
        >
          View all audits <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="overflow-hidden border rounded-xl bg-card/30 backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-muted/50 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Conclusion</th>
                <th className="px-4 py-3 font-medium text-center">Risk Score</th>
                <th className="px-4 py-3 font-medium text-right">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {displayAudits.length > 0 ? (
                displayAudits.map((audit) => (
                  <tr 
                    key={audit.run_id}
                    className="transition-colors hover:bg-muted/30 cursor-pointer group"
                    onClick={() => window.location.href = `/audits/${audit.run_id}`}
                  >
                    <td className="px-4 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold group-hover:text-primary transition-colors">
                          {audit.company_name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {audit.company_ticker || audit.company_cik}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-muted-foreground">
                      {formatDistanceToNow(new Date(audit.started_at), { addSuffix: true })}
                    </td>
                    <td className="px-4 py-4">
                      <Badge variant="outline" className={cn("capitalize", getConclusionColor(audit.conclusion))}>
                        {audit.conclusion || "In Progress"}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={cn("font-bold text-lg", getScoreColor(audit.risk_score))}>
                        {audit.risk_score ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right text-muted-foreground">
                      {formatDuration(audit.duration_seconds || 0)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-muted-foreground">
                    No audits found. Start an audit from the list below.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
