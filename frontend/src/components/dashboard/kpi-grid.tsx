"use client";

import { Activity, AlertTriangle, TrendingUp, Clock } from "lucide-react";
import { KPICard } from "./kpi-card";
import { DashboardMetrics } from "@/lib/dashboard-metrics";
import { formatDuration } from "@/lib/utils";

interface KPIGridProps {
  metrics: DashboardMetrics;
}

export function KPIGrid({ metrics }: KPIGridProps) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:gap-6">
      <KPICard
        label="Total Audits"
        value={metrics.totalAudits}
        icon={Activity}
        subLabel="All-time processed"
        delay={0.1}
      />
      <KPICard
        label="Fraud Detection Rate"
        value={`${(metrics.fraudDetectionRate * 100).toFixed(1)}%`}
        icon={AlertTriangle}
        subLabel={`${metrics.fraudDetected} of ${metrics.totalAudits} audits`}
        variant={metrics.fraudDetectionRate > 0.3 ? "danger" : metrics.fraudDetectionRate > 0.1 ? "warning" : "success"}
        delay={0.2}
      />
      <KPICard
        label="Average Risk Score"
        value={metrics.averageRiskScore?.toFixed(1) ?? "—"}
        icon={TrendingUp}
        subLabel="0-100 scale"
        variant={(metrics.averageRiskScore ?? 0) > 60 ? "danger" : (metrics.averageRiskScore ?? 0) > 30 ? "warning" : "success"}
        delay={0.3}
      />
      <KPICard
        label="Average Duration"
        value={metrics.averageDuration ? formatDuration(metrics.averageDuration) : "—"}
        icon={Clock}
        subLabel="Processing time"
        delay={0.4}
      />
    </div>
  );
}
