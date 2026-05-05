"use client";

import Link from "next/link";
import { ArrowLeft, Clock, Coins, Zap } from "lucide-react";
import { formatDuration, formatCost, formatTokens } from "@/lib/utils";
import type { AuditDetail } from "@/types/audit";

interface AuditHeaderProps {
  companyName: string;
  companyTicker: string | null;
  status: "running" | "completed" | "failed";
  elapsedSeconds: number;
  totalTokens: number;
  totalCost: number;
  initialDetail?: AuditDetail | null;
}

export function AuditHeader({
  companyName,
  companyTicker,
  status,
  elapsedSeconds,
  totalTokens,
  totalCost,
}: AuditHeaderProps) {
  const statusConfig = {
    running: { label: "Running", color: "bg-blue-500" },
    completed: { label: "Completed", color: "bg-emerald-500" },
    failed: { label: "Failed", color: "bg-red-500" },
  }[status];
  
  return (
    <header className="border-b border-neutral-200 bg-white sticky top-0 z-10">
      <div className="container mx-auto px-6 py-4 max-w-6xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 min-w-0">
            <Link
              href="/"
              className="text-neutral-500 hover:text-neutral-900 transition-colors shrink-0"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base font-semibold text-neutral-900 truncate">
                  {companyName}
                </h1>
                {companyTicker && (
                  <span className="text-sm text-neutral-500">({companyTicker})</span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`w-1.5 h-1.5 rounded-full ${statusConfig.color} ${status === "running" ? "animate-pulse" : ""}`} />
                <span className="text-xs text-neutral-500">{statusConfig.label}</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-1.5 text-neutral-600">
              <Clock className="w-4 h-4" />
              <span className="tabular-nums">{formatDuration(elapsedSeconds)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-neutral-600">
              <Zap className="w-4 h-4" />
              <span className="tabular-nums">{formatTokens(totalTokens)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-neutral-600">
              <Coins className="w-4 h-4" />
              <span className="tabular-nums">{formatCost(totalCost)}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
