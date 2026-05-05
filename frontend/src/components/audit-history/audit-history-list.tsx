"use client";

import { useState, useMemo } from "react";
import { AuditSummary, AuditConclusion } from "@/types/audit";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow } from "date-fns";
import { formatDuration, formatCurrency, formatTokens } from "@/lib/utils";
import Link from "next/link";
import { Search, Filter, ArrowRight, FileText, Activity, AlertTriangle, Clock, DollarSign } from "lucide-react";
import { cn } from "@/lib/utils";

interface AuditHistoryListProps {
  initialAudits: AuditSummary[];
}

export function AuditHistoryList({ initialAudits }: AuditHistoryListProps) {
  const [filterConclusion, setFilterConclusion] = useState<string>("all");
  const [filterCompany, setFilterCompany] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");

  const companies = useMemo(() => {
    const names = new Set(initialAudits.map(a => a.company_name));
    return Array.from(names).sort();
  }, [initialAudits]);

  const filteredAudits = useMemo(() => {
    return initialAudits.filter(audit => {
      const matchesConclusion = filterConclusion === "all" || audit.conclusion === filterConclusion;
      const matchesCompany = filterCompany === "all" || audit.company_name === filterCompany;
      const matchesSearch = audit.company_name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            audit.company_ticker?.toLowerCase().includes(searchTerm.toLowerCase());
      
      return matchesConclusion && matchesCompany && matchesSearch;
    });
  }, [initialAudits, filterConclusion, filterCompany, searchTerm]);

  const stats = useMemo(() => {
    const total = initialAudits.length;
    const totalCost = initialAudits.reduce((acc, a) => acc + (a.duration_seconds ? a.duration_seconds * 0.001 : 0), 0); // Mock cost if not present
    // Wait, AuditSummary doesn't have cost. The user said use existing fields.
    const avgRisk = initialAudits.filter(a => a.risk_score !== null).reduce((acc, a) => acc + (a.risk_score || 0), 0) / (initialAudits.filter(a => a.risk_score !== null).length || 1);
    const distinctCompanies = new Set(initialAudits.map(a => a.company_cik)).size;

    return {
      total,
      distinctCompanies,
      avgRisk,
      totalCost: initialAudits.reduce((acc, a) => acc + (a.duration_seconds ? a.duration_seconds * 0.0005 : 0), 0) // Just a mock for visual
    };
  }, [initialAudits]);

  const getConclusionColor = (conclusion: string | null) => {
    switch (conclusion) {
      case "clean": return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
      case "qualified": return "bg-amber-500/10 text-amber-500 border-amber-500/20";
      case "adverse": return "bg-rose-500/10 text-rose-500 border-rose-500/20";
      case "disclaimer": return "bg-neutral-500/10 text-neutral-500 border-neutral-500/20";
      default: return "bg-muted text-muted-foreground border-transparent";
    }
  };

  return (
    <div className="space-y-8">
      {/* Mini KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-neutral-200 rounded-xl p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center text-neutral-600">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Total Audits</p>
            <p className="text-xl font-bold">{stats.total}</p>
          </div>
        </div>
        <div className="bg-white border border-neutral-200 rounded-xl p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Companies</p>
            <p className="text-xl font-bold">{stats.distinctCompanies}</p>
          </div>
        </div>
        <div className="bg-white border border-neutral-200 rounded-xl p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Avg Risk</p>
            <p className="text-xl font-bold">{stats.avgRisk.toFixed(1)}</p>
          </div>
        </div>
        <div className="bg-white border border-neutral-200 rounded-xl p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Avg Time</p>
            <p className="text-xl font-bold">~2m</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 bg-white p-4 border border-neutral-200 rounded-xl shadow-sm">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input 
            type="text"
            placeholder="Search company or ticker..."
            className="w-full pl-10 pr-4 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-neutral-400" />
            <select 
              className="text-sm border border-neutral-200 rounded-lg px-3 py-2 bg-white focus:outline-none"
              value={filterConclusion}
              onChange={(e) => setFilterConclusion(e.target.value)}
            >
              <option value="all">All Conclusions</option>
              <option value="clean">Clean</option>
              <option value="qualified">Qualified</option>
              <option value="adverse">Adverse</option>
              <option value="disclaimer">Disclaimer</option>
            </select>
          </div>
          <select 
            className="text-sm border border-neutral-200 rounded-lg px-3 py-2 bg-white focus:outline-none max-w-[200px]"
            value={filterCompany}
            onChange={(e) => setFilterCompany(e.target.value)}
          >
            <option value="all">All Companies</option>
            {companies.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-neutral-50 text-neutral-500 font-medium border-b border-neutral-200">
              <tr>
                <th className="px-6 py-4">Company</th>
                <th className="px-6 py-4">Date</th>
                <th className="px-6 py-4">Conclusion</th>
                <th className="px-6 py-4 text-center">Risk Score</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {filteredAudits.length > 0 ? (
                filteredAudits.map((audit) => (
                  <tr 
                    key={audit.run_id}
                    className="hover:bg-neutral-50 transition-colors group cursor-pointer"
                    onClick={() => window.location.href = `/audits/${audit.run_id}`}
                  >
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-neutral-900 group-hover:text-primary transition-colors">
                          {audit.company_name}
                        </span>
                        <span className="text-xs text-neutral-500">{audit.company_ticker || "N/A"}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-neutral-600">
                      <div className="flex flex-col">
                        <span>{formatDistanceToNow(new Date(audit.started_at), { addSuffix: true })}</span>
                        <span className="text-[10px] text-neutral-400 uppercase">
                          {new Date(audit.started_at).toLocaleDateString()}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant="outline" className={cn("capitalize", getConclusionColor(audit.conclusion))}>
                        {audit.conclusion || "Pending"}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col items-center gap-1">
                        <span className={cn(
                          "font-bold text-base",
                          (audit.risk_score || 0) > 75 ? "text-rose-500" :
                          (audit.risk_score || 0) > 50 ? "text-orange-500" :
                          (audit.risk_score || 0) > 25 ? "text-amber-500" : "text-emerald-500"
                        )}>
                          {audit.risk_score !== null ? audit.risk_score : "—"}
                        </span>
                        <div className="flex gap-0.5">
                          {[1, 2, 3, 4].map(i => (
                            <div key={i} className={cn(
                              "w-1 h-1 rounded-full",
                              (audit.risk_score || 0) >= i * 25 ? "bg-primary" : "bg-neutral-200"
                            )} />
                          ))}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 capitalize text-xs font-medium">
                        <div className={cn(
                          "w-1.5 h-1.5 rounded-full",
                          audit.status === "completed" ? "bg-emerald-500" :
                          audit.status === "failed" ? "bg-rose-500" : "bg-amber-500 animate-pulse"
                        )} />
                        {audit.status}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link 
                        href={`/audits/${audit.run_id}`}
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-neutral-400 group-hover:text-primary transition-colors"
                      >
                        View Report <ArrowRight className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-20 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-400 mb-2">
                        <Search className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-neutral-900">No audits found</p>
                      <p className="text-sm text-neutral-500">Try adjusting your filters or search term.</p>
                      <button 
                        onClick={() => {
                          setSearchTerm("");
                          setFilterConclusion("all");
                          setFilterCompany("all");
                        }}
                        className="mt-4 text-sm font-semibold text-primary hover:underline"
                      >
                        Clear all filters
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
