"use client";

import { motion } from "framer-motion";
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ShieldAlert, Clock, Coins, CreditCard } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FinalReport } from "@/types/audit";
import { cn, formatDuration, formatCost, formatTokens } from "@/lib/utils";

interface ReportHeroProps {
  report: FinalReport;
  durationSeconds: number;
  totalTokens: number;
  totalCost: number;
  needsHumanReview: boolean;
}

export function ReportHero({ 
  report, 
  durationSeconds, 
  totalTokens, 
  totalCost, 
  needsHumanReview 
}: ReportHeroProps) {
  const { audit_conclusion, risk_score, risk_level, company_data } = report;

  const conclusionConfig = {
    clean: {
      label: "Unqualified (Clean)",
      color: "bg-green-500/10 text-green-500 border-green-500/20",
      icon: CheckCircle2,
    },
    qualified: {
      label: "Qualified Opinion",
      color: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
      icon: AlertTriangle,
    },
    adverse: {
      label: "Adverse Opinion",
      color: "bg-red-500/10 text-red-500 border-red-500/20",
      icon: XCircle,
    },
    disclaimer: {
      label: "Disclaimer of Opinion",
      color: "bg-slate-500/10 text-slate-500 border-slate-500/20",
      icon: HelpCircle,
    },
  };

  const config = conclusionConfig[audit_conclusion] || conclusionConfig.disclaimer;
  const ConclusionIcon = config.icon;

  const riskColors = {
    low: "bg-green-500",
    medium: "bg-yellow-500",
    high: "bg-orange-500",
    critical: "bg-red-500",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card className="overflow-hidden border-2 border-primary/10 shadow-xl bg-gradient-to-br from-background to-muted/30">
        <CardContent className="p-8">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-4xl font-bold tracking-tight">{company_data.name}</h1>
                {company_data.ticker && (
                  <span className="text-2xl text-muted-foreground font-mono">({company_data.ticker})</span>
                )}
              </div>
              <p className="text-muted-foreground mb-6">SEC CIK: {company_data.cik}</p>
              
              <div className="flex flex-wrap gap-3">
                <Badge className={cn("px-4 py-1.5 text-lg font-semibold border-2", config.color)} variant="outline">
                  <ConclusionIcon className="w-5 h-5 mr-2" />
                  {config.label}
                </Badge>
                
                {needsHumanReview && (
                  <Badge variant="destructive" className="px-4 py-1.5 text-lg font-semibold animate-pulse">
                    <ShieldAlert className="w-5 h-5 mr-2" />
                    Requires Human Review
                  </Badge>
                )}
              </div>
            </div>

            <div className="flex flex-col items-center md:items-end gap-2">
              <div className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Risk Score</div>
              <div className="flex items-baseline gap-2">
                <span className={cn("text-6xl font-black", 
                  risk_score < 30 ? "text-green-500" : 
                  risk_score < 60 ? "text-yellow-500" : 
                  "text-red-500"
                )}>
                  {risk_score}
                </span>
                <span className="text-2xl text-muted-foreground font-bold">/100</span>
              </div>
              <div className="flex gap-1 mt-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className={cn(
                      "w-8 h-2 rounded-full transition-colors",
                      i <= (risk_score / 20) ? riskColors[risk_level] : "bg-muted"
                    )}
                  />
                ))}
              </div>
              <div className="text-sm font-bold uppercase mt-1 tracking-widest" style={{ color: riskColors[risk_level].replace('bg-', '') }}>
                {risk_level} risk
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12 pt-8 border-t border-border/50">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10 text-blue-500">
                <Clock className="w-6 h-6" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Audit Duration</div>
                <div className="text-xl font-bold">{formatDuration(durationSeconds)}</div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-purple-500/10 text-purple-500">
                <Coins className="w-6 h-6" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Tokens Processed</div>
                <div className="text-xl font-bold">{formatTokens(totalTokens)}</div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-green-500/10 text-green-500">
                <CreditCard className="w-6 h-6" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Estimated Cost</div>
                <div className="text-xl font-bold">{formatCost(totalCost)}</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
