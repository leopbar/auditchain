import { AuditSummary, AuditConclusion } from "@/types/audit";

export interface DashboardMetrics {
  totalAudits: number;
  fraudDetected: number;
  fraudDetectionRate: number;
  averageRiskScore: number | null;
  averageDuration: number | null;
  conclusionDistribution: Record<AuditConclusion, number>;
  recentAudits: AuditSummary[];
}

export function calculateDashboardMetrics(audits: AuditSummary[]): DashboardMetrics {
  const totalAudits = audits.length;
  
  if (totalAudits === 0) {
    return {
      totalAudits: 0,
      fraudDetected: 0,
      fraudDetectionRate: 0,
      averageRiskScore: null,
      averageDuration: null,
      conclusionDistribution: {
        clean: 0,
        qualified: 0,
        adverse: 0,
        disclaimer: 0,
      },
      recentAudits: [],
    };
  }

  // Filter for completed audits with scores
  const scoredAudits = audits.filter(a => a.risk_score !== null);
  const averageRiskScore = scoredAudits.length > 0
    ? scoredAudits.reduce((sum, a) => sum + (a.risk_score || 0), 0) / scoredAudits.length
    : null;

  // Filter for audits with duration
  const durationAudits = audits.filter(a => a.duration_seconds !== null);
  const averageDuration = durationAudits.length > 0
    ? durationAudits.reduce((sum, a) => sum + (a.duration_seconds || 0), 0) / durationAudits.length
    : null;

  // Count fraud detected
  const fraudDetected = audits.filter(a => 
    a.conclusion === "adverse" || 
    (a.conclusion === "qualified" && (a.risk_score || 0) > 50)
  ).length;

  const fraudDetectionRate = fraudDetected / totalAudits;

  // Conclusion distribution
  const conclusionDistribution: Record<AuditConclusion, number> = {
    clean: 0,
    qualified: 0,
    adverse: 0,
    disclaimer: 0,
  };

  audits.forEach(a => {
    if (a.conclusion) {
      conclusionDistribution[a.conclusion]++;
    }
  });

  // Recent audits sorted by started_at desc
  const recentAudits = [...audits]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 10);

  return {
    totalAudits,
    fraudDetected,
    fraudDetectionRate,
    averageRiskScore,
    averageDuration,
    conclusionDistribution,
    recentAudits,
  };
}
