"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AuditConclusion } from "@/types/audit";

interface ConclusionsDonutChartProps {
  distribution: Record<AuditConclusion, number>;
  total: number;
}

export function ConclusionsDonutChart({ distribution, total }: ConclusionsDonutChartProps) {
  const data = [
    { name: "Clean", value: distribution.clean, color: "#10b981", id: "clean" },
    { name: "Qualified", value: distribution.qualified, color: "#f59e0b", id: "qualified" },
    { name: "Adverse", value: distribution.adverse, color: "#f43f5e", id: "adverse" },
    { name: "Disclaimer", value: distribution.disclaimer, color: "#94a3b8", id: "disclaimer" },
  ].filter(d => d.value > 0);

  if (total === 0) {
    return (
      <Card className="flex flex-col h-[400px] border-none bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Audit Conclusions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center flex-1 text-muted-foreground">
          No audits processed yet
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col h-[400px] border-none bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Audit Conclusions</CardTitle>
      </CardHeader>
      <CardContent className="relative flex-1 pb-4">
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-3xl font-bold">{total}</span>
          <span className="text-xs text-muted-foreground uppercase tracking-wider">Total</span>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={80}
              outerRadius={110}
              paddingAngle={5}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
              ))}
            </Pie>
            <Tooltip 
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0];
                  const percent = ((Number(data.value) / total) * 100).toFixed(1);
                  return (
                    <div className="p-2 border rounded-md shadow-lg bg-background/90 backdrop-blur-md border-border">
                      <p className="text-xs font-bold uppercase" style={{ color: data.payload.color }}>
                        {data.name}
                      </p>
                      <p className="text-sm font-semibold mt-1">
                        {data.value} audits ({percent}%)
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend 
              verticalAlign="bottom" 
              align="center"
              iconType="circle"
              wrapperStyle={{ paddingTop: "20px" }}
              formatter={(value) => <span className="text-xs font-medium text-muted-foreground">{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
