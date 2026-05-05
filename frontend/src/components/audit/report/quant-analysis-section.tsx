"use client";

import { Calculator, Gauge, ShieldCheck, ShieldAlert, Activity } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { QuantAnalysis } from "@/types/audit";
import { cn } from "@/lib/utils";

interface QuantAnalysisSectionProps {
  analysis: QuantAnalysis;
}

export function QuantAnalysisSection({ analysis }: QuantAnalysisSectionProps) {
  const { beneish_mscore, beneish_interpretation, altman_zscore, altman_interpretation, accruals_ratio, summary } = analysis;

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <Calculator className="w-6 h-6 text-primary" />
          Quantitative Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Beneish M-Score */}
          <Card className="border-2 shadow-sm overflow-hidden">
            <CardHeader className="bg-muted/30 pb-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Beneish M-Score</span>
                <Gauge className="w-5 h-5 text-primary" />
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="text-3xl font-black mb-2">
                {beneish_mscore !== null ? beneish_mscore.toFixed(4) : "N/A"}
              </div>
              <div className="text-sm font-medium text-muted-foreground mb-4">Threshold: -1.78</div>
              
              <div className="relative h-2 bg-muted rounded-full overflow-hidden mb-4">
                <div 
                  className={cn("absolute h-full transition-all", 
                    (beneish_mscore || 0) < -1.78 ? "bg-green-500" : "bg-red-500"
                  )}
                  style={{ 
                    left: 0, 
                    width: beneish_mscore === null ? "0%" : 
                           beneish_mscore < -4 ? "5%" : 
                           beneish_mscore > 0 ? "95%" : 
                           `${((beneish_mscore + 4) / 4) * 100}%` 
                  }}
                />
                <div className="absolute left-[55.5%] top-0 w-0.5 h-full bg-foreground z-10" /> {/* Threshold marker */}
              </div>

              <div className={cn("flex items-center gap-2 font-bold text-sm", 
                (beneish_mscore || 0) < -1.78 ? "text-green-600" : "text-red-600"
              )}>
                {(beneish_mscore || 0) < -1.78 ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                {beneish_interpretation || "Not analyzed"}
              </div>
            </CardContent>
          </Card>

          {/* Altman Z-Score */}
          <Card className="border-2 shadow-sm overflow-hidden">
            <CardHeader className="bg-muted/30 pb-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Altman Z-Score</span>
                <ShieldCheck className="w-5 h-5 text-primary" />
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="text-3xl font-black mb-2">
                {altman_zscore !== null ? altman_zscore.toFixed(4) : "N/A"}
              </div>
              <div className="text-sm font-medium text-muted-foreground mb-4">Zones: &gt;2.99 Safe | &lt;1.81 Distress</div>
              
              <div className="flex h-2 w-full rounded-full overflow-hidden mb-4">
                <div className="w-[30%] bg-red-500" />
                <div className="w-[20%] bg-yellow-500" />
                <div className="w-[50%] bg-green-500" />
              </div>

              <div className={cn("flex items-center gap-2 font-bold text-sm", 
                (altman_zscore || 0) > 2.99 ? "text-green-600" : 
                (altman_zscore || 0) > 1.81 ? "text-yellow-600" : "text-red-600"
              )}>
                {(altman_zscore || 0) > 2.99 ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                {altman_interpretation || "Not analyzed"}
              </div>
            </CardContent>
          </Card>

          {/* Accruals Ratio */}
          <Card className="border-2 shadow-sm overflow-hidden">
            <CardHeader className="bg-muted/30 pb-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Accruals Ratio</span>
                <Activity className="w-5 h-5 text-primary" />
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="text-3xl font-black mb-2">
                {accruals_ratio !== null ? `${(accruals_ratio * 100).toFixed(2)}%` : "N/A"}
              </div>
              <div className="text-sm font-medium text-muted-foreground mb-4">Threshold: ±10%</div>
              
              <div className="bg-muted h-2 rounded-full overflow-hidden mb-4 relative">
                 <div 
                  className={cn("absolute h-full transition-all", 
                    Math.abs(accruals_ratio || 0) < 0.1 ? "bg-green-500" : "bg-red-500"
                  )}
                  style={{ 
                    left: "50%", 
                    width: `${Math.min(Math.abs(accruals_ratio || 0) * 500, 50)}%`,
                    transform: (accruals_ratio || 0) < 0 ? "translateX(-100%)" : "none"
                  }}
                />
                <div className="absolute left-1/2 top-0 w-0.5 h-full bg-foreground z-10" />
              </div>

              <div className={cn("flex items-center gap-2 font-bold text-sm", 
                Math.abs(accruals_ratio || 0) < 0.1 ? "text-green-600" : "text-red-600"
              )}>
                {accruals_ratio === null ? <Activity className="w-4 h-4" /> : 
                 Math.abs(accruals_ratio) < 0.1 ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                {accruals_ratio === null ? "Not computed" : 
                 Math.abs(accruals_ratio) < 0.1 ? "Healthy accruals level" : "Excessive accruals detected"}
              </div>
            </CardContent>
          </Card>
        </div>

        {summary && (
          <div className="p-6 bg-muted/20 border-l-4 border-primary rounded-r-2xl">
            <p className="text-lg leading-relaxed italic text-muted-foreground">"{summary}"</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
