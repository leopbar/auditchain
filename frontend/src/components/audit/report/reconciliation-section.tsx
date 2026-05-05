"use client";

import { Calculator, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ReconciliationAnalysis } from "@/types/audit";
import { cn } from "@/lib/utils";

interface ReconciliationSectionProps {
  reconciliation: ReconciliationAnalysis;
}

export function ReconciliationSection({ reconciliation }: ReconciliationSectionProps) {
  const { passed, summary, checks } = reconciliation;

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4 flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <Calculator className="w-6 h-6 text-primary" />
          Reconciliation Checks
        </CardTitle>
        <Badge 
          className={cn("text-lg px-4 py-1 font-black", 
            passed ? "bg-green-500 hover:bg-green-600" : "bg-red-500 hover:bg-red-600"
          )}
        >
          {passed ? "PASSED" : "FAILED"}
        </Badge>
      </CardHeader>
      <CardContent className="px-0 space-y-6">
        {summary && (
          <p className="text-xl leading-relaxed text-muted-foreground">{summary}</p>
        )}

        {checks.length > 0 ? (
          <div className="border rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Check Name</th>
                  <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Result</th>
                  <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Tolerance</th>
                  <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {checks.map((check, i) => (
                  <tr key={i} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4 font-bold">{check.name}</td>
                    <td className="px-6 py-4 font-mono text-sm">{check.result}</td>
                    <td className="px-6 py-4 text-muted-foreground text-sm">{check.tolerance}</td>
                    <td className="px-6 py-4">
                      {check.passed ? (
                        <div className="flex items-center gap-1.5 text-green-500 font-bold text-sm uppercase">
                          <CheckCircle2 className="w-4 h-4" />
                          Passed
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 text-red-500 font-bold text-sm uppercase">
                          <XCircle className="w-4 h-4" />
                          Failed
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 bg-muted/20 rounded-2xl text-center italic text-muted-foreground">
            No specific mathematical consistency checks were recorded for this period.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
