import { calculateDashboardMetrics } from "@/lib/dashboard-metrics";
import { KPIGrid } from "./kpi-grid";
import { RecentAuditsChart } from "./recent-audits-chart";
import { ConclusionsDonutChart } from "./conclusions-donut-chart";
import { RecentAuditsTable } from "./recent-audits-table";
import { Separator } from "@/components/ui/separator";
import { AuditSummary } from "@/types/audit";

interface DashboardSectionProps {
  audits: AuditSummary[];
}

export function DashboardSection({ audits }: DashboardSectionProps) {
  if (!audits || audits.length === 0) {
    return null;
  }

  const metrics = calculateDashboardMetrics(audits);

  return (
    <div className="space-y-12">
      <section className="space-y-6">
        <h2 className="text-sm font-bold tracking-widest text-muted-foreground uppercase">
          Executive Overview
        </h2>
        <KPIGrid metrics={metrics} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <RecentAuditsChart audits={metrics.recentAudits} />
        </div>
        <div className="min-w-0">
          <ConclusionsDonutChart distribution={metrics.conclusionDistribution} total={metrics.totalAudits} />
        </div>
      </div>

      <RecentAuditsTable audits={metrics.recentAudits} />
      
      <Separator className="my-12 opacity-50" />
    </div>
  );
}
