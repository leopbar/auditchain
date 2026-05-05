"use client";

import { FinalReport, PhaseState } from "@/types/audit";
import { ReportHero } from "./report-hero";
import { ExecutiveSummarySection } from "./executive-summary-section";
import { RecommendationsSection } from "./recommendations-section";
import { RedFlagsSection } from "./red-flags-section";
import { QuantAnalysisSection } from "./quant-analysis-section";
import { InvestigationSection } from "./investigation-section";
import { ReconciliationSection } from "./reconciliation-section";
import { CompanySnapshotSection } from "./company-snapshot-section";
import { AgentPerformanceSection } from "./agent-performance-section";
import { Separator } from "@/components/ui/separator";

interface AuditReportProps {
  report: FinalReport;
  durationSeconds: number;
  totalTokens: number;
  totalCost: number;
  needsHumanReview: boolean;
  phases: Record<string, PhaseState>;
}

export function AuditReport({ 
  report, 
  durationSeconds, 
  totalTokens, 
  totalCost, 
  needsHumanReview,
  phases 
}: AuditReportProps) {

  return (
    <div className="max-w-5xl mx-auto space-y-12 pb-20">
      {/* Hero Section */}
      <ReportHero 
        report={report}
        durationSeconds={durationSeconds}
        totalTokens={totalTokens}
        totalCost={totalCost}
        needsHumanReview={needsHumanReview}
      />

      <div className="space-y-16 px-4 md:px-0">
        {/* Executive Summary */}
        <ExecutiveSummarySection summary={report.executive_summary} />
        
        <Separator className="opacity-50" />

        {/* Recommendations */}
        <RecommendationsSection recommendations={report.recommendations} />

        {/* Company Snapshot */}
        <CompanySnapshotSection companyData={report.company_data} />

        <Separator className="opacity-50" />

        {/* Red Flags */}
        <RedFlagsSection flags={report.consolidated_red_flags} />

        <Separator className="opacity-50" />

        {/* Technical Analysis Grid */}
        <div className="space-y-16">
          <ReconciliationSection reconciliation={report.reconciliation} />
          <QuantAnalysisSection analysis={report.quant_analysis} />
          <InvestigationSection investigation={report.investigation} />
        </div>

        <Separator className="opacity-50" />

        {/* Performance & Meta */}
        <AgentPerformanceSection 
          phases={phases} 
        />
      </div>
    </div>
  );
}
