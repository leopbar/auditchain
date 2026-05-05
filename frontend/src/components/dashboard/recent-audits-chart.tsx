"use client";

import { AuditSummary } from "@/types/audit";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  Cell,
  CartesianGrid
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface RecentAuditsChartProps {
  audits: AuditSummary[];
}

export function RecentAuditsChart({ audits }: RecentAuditsChartProps) {
  const seenCiks = new Set<string>();
  const uniqueAudits = [];

  // Audits are pre-sorted desc by date in metrics
  for (const audit of audits) {
    if (audit.risk_score !== null && !seenCiks.has(audit.company_cik)) {
      seenCiks.add(audit.company_cik);
      uniqueAudits.push(audit);
    }
  }

  const data = uniqueAudits
    .slice(0, 5) // Limit to top 5 unique companies
    .map(a => ({
      name: a.company_name.length > 20 ? `${a.company_name.substring(0, 20)}...` : a.company_name,
      ticker: a.company_ticker,
      score: a.risk_score || 0,
      conclusion: a.conclusion,
      fullName: a.company_name,
      date: new Date(a.started_at).toLocaleDateString()
    }))
    .reverse();

  const getBarColor = (score: number) => {
    if (score < 25) return "#10b981"; // emerald-500
    if (score < 50) return "#f59e0b"; // amber-500
    if (score < 75) return "#f97316"; // orange-500
    return "#f43f5e"; // rose-500
  };

  if (data.length === 0) {
    return (
      <Card className="flex flex-col h-[400px]">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Risk Analysis by Company</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center flex-1 text-muted-foreground">
          No audit data available yet
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col h-[400px] border-none bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Risk Analysis by Company</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
            barSize={20}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="hsl(var(--muted))" opacity={0.3} />
            <XAxis 
              type="number" 
              domain={[0, 100]} 
              stroke="hsl(var(--muted-foreground))" 
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              dataKey="name" 
              type="category" 
              width={100}
              stroke="hsl(var(--muted-foreground))" 
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: "hsl(var(--muted))", opacity: 0.1 }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  return (
                    <div className="p-3 border rounded-lg shadow-xl bg-background/90 backdrop-blur-md border-border">
                      <p className="text-sm font-bold">{data.fullName}</p>
                      <p className="text-xs text-muted-foreground">Ticker: {data.ticker || "N/A"}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-xs font-medium uppercase">Risk Score:</span>
                        <span className="text-sm font-bold" style={{ color: getBarColor(data.score) }}>
                          {data.score}
                        </span>
                      </div>
                      <p className="mt-1 text-xs uppercase">
                        Conclusion: <span className="font-semibold">{data.conclusion || "Pending"}</span>
                      </p>
                      <p className="mt-1 text-[10px] text-muted-foreground uppercase">{data.date}</p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
