"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Building2, AlertTriangle, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { startAudit } from "@/lib/api/client";
import type { Company } from "@/types/audit";

interface CompanyCardProps {
  company: Company;
}

export function CompanyCard({ company }: CompanyCardProps) {
  const router = useRouter();
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  async function handleStartAudit() {
    setIsStarting(true);
    setError(null);
    try {
      const response = await startAudit({ cik: company.cik, model: "gpt-4o-mini" });
      router.push(`/audits/${response.run_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start audit";
      setError(message);
      setIsStarting(false);
    }
  }
  
  return (
    <div className="h-full flex flex-col group relative bg-white border border-neutral-200 rounded-xl p-6 hover:border-neutral-300 hover:shadow-sm transition-all">
      {/* Header: name + ticker */}
      <div className="flex items-start justify-between gap-2 mb-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center shrink-0">
            <Building2 className="w-5 h-5 text-neutral-600" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-neutral-900 truncate">{company.name}</h3>
            {company.ticker && (
              <p className="text-sm text-neutral-500 mt-0.5 truncate">
                {company.ticker} <span className="text-neutral-300 mx-1">·</span> CIK {company.cik}
              </p>
            )}
          </div>
        </div>
        
        {company.is_known_fraud && (
          <Badge variant="destructive" className="shrink-0 whitespace-nowrap">
            <AlertTriangle className="w-3 h-3 mr-1" />
            Known Fraud
          </Badge>
        )}
      </div>
      
      {/* Stats */}
      <div className="flex items-center gap-4 text-sm text-neutral-600 mb-5">
        <div className="flex items-center gap-1.5">
          <FileText className="w-4 h-4" />
          <span>{company.filings_count} filings</span>
        </div>
        {company.has_text_indexed && (
          <div className="flex items-center gap-1.5 text-emerald-600">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>Text indexed</span>
          </div>
        )}
      </div>
      
      {/* Fraud notes (if known fraud) */}
      {company.is_known_fraud && company.fraud_notes && (
        <p className="text-xs text-neutral-500 mb-4 leading-relaxed line-clamp-2">
          {company.fraud_notes}
        </p>
      )}
      
      {/* Error message */}
      {error && (
        <p className="text-xs text-red-600 mb-3">{error}</p>
      )}
      
      {/* Action */}
      <div className="mt-auto pt-2">
        <Button
          onClick={handleStartAudit}
          disabled={isStarting}
          className="w-full"
        >
          {isStarting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Starting audit...
            </>
          ) : (
            "Start Audit"
          )}
        </Button>
      </div>
    </div>
  );
}
