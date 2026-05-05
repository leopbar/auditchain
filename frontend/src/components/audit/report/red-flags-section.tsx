"use client";

import { useState } from "react";
import { ShieldAlert, AlertCircle, Info, Filter } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RedFlag, Severity } from "@/types/audit";
import { cn } from "@/lib/utils";

interface RedFlagsSectionProps {
  flags: RedFlag[];
}

export function RedFlagsSection({ flags }: RedFlagsSectionProps) {
  const [filter, setFilter] = useState<Severity | "all">("all");

  const severityOrder: Record<Severity, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
    info: 4,
  };

  const sortedFlags = [...flags].sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
  
  const filteredFlags = filter === "all" 
    ? sortedFlags 
    : sortedFlags.filter(f => f.severity === filter);

  const counts = flags.reduce((acc, flag) => {
    acc[flag.severity] = (acc[flag.severity] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const severityConfigs: Record<Severity, { label: string, bg: string, text: string, border: string, icon: any }> = {
    critical: { label: "Critical", bg: "bg-red-500/10", text: "text-red-500", border: "border-red-500/20", icon: ShieldAlert },
    high: { label: "High", bg: "bg-orange-500/10", text: "text-orange-500", border: "border-orange-500/20", icon: ShieldAlert },
    medium: { label: "Medium", bg: "bg-amber-500/10", text: "text-amber-500", border: "border-amber-500/20", icon: AlertCircle },
    low: { label: "Low", bg: "bg-blue-500/10", text: "text-blue-500", border: "border-blue-500/20", icon: Info },
    info: { label: "Info", bg: "bg-slate-500/10", text: "text-slate-500", border: "border-slate-500/20", icon: Info },
  };

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-6 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <ShieldAlert className="w-6 h-6 text-primary" />
          Red Flags ({flags.length})
        </CardTitle>
        
        <div className="flex gap-2">
          <Badge 
            variant={filter === "all" ? "default" : "outline"}
            className="cursor-pointer px-3"
            onClick={() => setFilter("all")}
          >
            All
          </Badge>
          {(Object.keys(severityOrder) as Severity[]).map(sev => (
            counts[sev] > 0 && (
              <Badge 
                key={sev}
                variant={filter === sev ? "default" : "outline"}
                className={cn("cursor-pointer px-3", filter === sev ? "" : severityConfigs[sev].text)}
                onClick={() => setFilter(sev)}
              >
                {severityConfigs[sev].label} ({counts[sev]})
              </Badge>
            )
          ))}
        </div>
      </CardHeader>
      
      <CardContent className="px-0">
        {flags.length === 0 ? (
          <div className="bg-green-500/5 border border-green-500/10 rounded-2xl p-12 text-center">
            <CheckSquare className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <p className="text-xl font-medium text-green-700">No red flags identified - financial statements appear sound.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredFlags.map((flag, i) => {
              const config = severityConfigs[flag.severity];
              const Icon = config.icon;
              return (
                <div 
                  key={i} 
                  className={cn("p-6 rounded-2xl border-2 transition-all hover:shadow-md", config.bg, config.border)}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <div className={cn("p-2 rounded-lg bg-white/50", config.text)}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <h3 className="text-xl font-bold">{flag.title}</h3>
                    </div>
                    <Badge variant="outline" className={cn("bg-white/50", config.text, config.border)}>
                      {config.label}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground text-lg mb-6 leading-relaxed">{flag.description}</p>
                  <div className="flex flex-wrap gap-4 pt-4 border-t border-black/5 items-center text-sm font-medium">
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground uppercase text-[10px] tracking-widest">Detected By:</span>
                      <Badge variant="secondary" className="font-bold">{flag.detected_by}</Badge>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground uppercase text-[10px] tracking-widest">Category:</span>
                      <span className="font-bold italic text-primary">{flag.category.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="ml-auto flex items-center gap-2">
                      <span className="text-muted-foreground uppercase text-[10px] tracking-widest">Confidence:</span>
                      <div className="w-24 h-1.5 bg-black/10 rounded-full overflow-hidden">
                        <div 
                          className={cn("h-full", config.text.replace('text-', 'bg-'))}
                          style={{ width: `${flag.confidence * 100}%` }}
                        />
                      </div>
                      <span className="font-mono font-bold">{(flag.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Helper to avoid build error
import { CheckSquare } from "lucide-react";
