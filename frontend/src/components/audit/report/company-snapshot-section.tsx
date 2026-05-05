"use client";

import { Building2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { CompanyData, FinancialPeriod } from "@/types/audit";
import { formatCurrency, cn } from "@/lib/utils";

interface CompanySnapshotSectionProps {
  companyData: CompanyData;
}

export function CompanySnapshotSection({ companyData }: CompanySnapshotSectionProps) {
  const current = companyData.current_period;
  const historical = companyData.historical_periods || [];
  
  if (!current) return null;

  // Find the year before current for YoY comparison
  const priorYear = current.fiscal_year ? current.fiscal_year - 1 : null;
  const prior = priorYear ? historical.find(h => h.fiscal_year === priorYear) : null;

  const metrics = [
    { label: "Total Revenue", value: current.revenue, key: "revenue" },
    { label: "Net Income", value: current.net_income, key: "net_income" },
    { label: "Total Assets", value: current.total_assets, key: "total_assets" },
    { label: "Total Liabilities", value: current.total_liabilities, key: "total_liabilities" },
    { label: "Stockholders Equity", value: current.stockholders_equity, key: "stockholders_equity" },
    { label: "Cash & Equivalents", value: current.cash, key: "cash" },
  ];

  function getYoY(key: string) {
    if (!prior) return null;
    const currentVal = current?.[key as keyof FinancialPeriod] as number | null;
    const priorVal = prior?.[key as keyof FinancialPeriod] as number | null;
    
    if (currentVal === null || priorVal === null || priorVal === 0 || isNaN(currentVal) || isNaN(priorVal)) return null;
    
    const change = ((currentVal - priorVal) / Math.abs(priorVal)) * 100;
    return change;
  }

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <Building2 className="w-6 h-6 text-primary" />
          Company Snapshot
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {metrics.map((metric) => {
            const yoy = getYoY(metric.key);
            const isNegative = yoy !== null && yoy < 0;
            const isPositive = yoy !== null && yoy > 0;
            
            // Special logic for Liabilities: negative YoY is good (green)
            const isGood = metric.key === "total_liabilities" ? isNegative : isPositive;
            const isBad = metric.key === "total_liabilities" ? isPositive : isNegative;

            return (
              <Card key={metric.key} className="p-6 border-2 hover:border-primary/30 transition-colors shadow-sm">
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">{metric.label}</div>
                <div className="text-2xl font-black mb-3">{formatCurrency(metric.value as number)}</div>
                
                {yoy !== null ? (
                  <div className={cn("flex items-center gap-1.5 text-sm font-bold", 
                    isGood ? "text-green-500" : isBad ? "text-red-500" : "text-muted-foreground"
                  )}>
                    {isPositive ? <TrendingUp className="w-4 h-4" /> : isNegative ? <TrendingDown className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
                    {Math.abs(yoy).toFixed(1)}% YoY
                  </div>
                ) : (
                  <div className="text-xs text-muted-foreground font-medium italic">No prior data</div>
                )}
              </Card>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
