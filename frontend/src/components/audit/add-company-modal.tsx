"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Building2,
  FileText,
  AlertCircle,
  Database,
  ArrowRight,
  Loader2,
  X,
  CheckCircle2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  startIngestion,
  checkCompanyExists,
  listCompanies,
  CompanyExistsError,
  type CheckCompanyResult,
} from "@/lib/api/client";
import { fetchSecCompanies, type SecCompany } from "@/lib/sec-companies";
import { cn } from "@/lib/utils";

interface AddCompanyModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddCompanyModal({ open, onOpenChange }: AddCompanyModalProps) {
  const router = useRouter();

  // Data states
  const [secCompanies, setSecCompanies] = useState<SecCompany[]>([]);
  const [existingCiks, setExistingCiks] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  // Search & Selection states
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<SecCompany | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-ingestion confirmation states
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [existingInfo, setExistingInfo] = useState<CheckCompanyResult | null>(null);

  // Load data when modal opens
  useEffect(() => {
    if (!open) return;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [sec, db] = await Promise.all([
          fetchSecCompanies(),
          listCompanies(),
        ]);
        setSecCompanies(sec);
        setExistingCiks(new Set(db.companies.map((c) => c.cik)));
      } catch (err) {
        console.error("Failed to initialize add company modal:", err);
        setError("Failed to load company directory. Please try again.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [open]);

  // Filtered suggestions
  const suggestions = useMemo(() => {
    if (search.length < 2) return [];
    
    const query = search.toLowerCase();
    return secCompanies
      .filter(
        (c) =>
          c.name.toLowerCase().includes(query) ||
          c.ticker.toLowerCase().includes(query) ||
          c.cik.includes(query)
      )
      .slice(0, 50);
  }, [search, secCompanies]);

  // Reset state when closing
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setSearch("");
      setSelected(null);
      setError(null);
      setShowConfirmDialog(false);
      setExistingInfo(null);
    }
    onOpenChange(newOpen);
  };

  const handleSelect = (company: SecCompany) => {
    setSelected(company);
    setSearch("");
    setError(null);
  };

  const handleStartIngestion = async (force: boolean = false) => {
    if (!selected) return;

    setStarting(true);
    setError(null);

    try {
      // 1. Check if exists (if not forced)
      if (!force) {
        const check = await checkCompanyExists(selected.cik);
        if (check.exists) {
          setExistingInfo(check);
          setShowConfirmDialog(true);
          setStarting(false);
          return;
        }
      }

      // 2. Start ingestion
      const res = await startIngestion({
        cik: selected.cik,
        force_update: force,
      });

      // 3. Redirect
      handleOpenChange(false);
      router.push(`/companies/add/${res.ingestion_id}`);
    } catch (err) {
      console.error("Ingestion start failed:", err);
      if (err instanceof CompanyExistsError) {
        // This shouldn't normally happen because we checked before, 
        // but handling for robustness.
        setShowConfirmDialog(true);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
      setStarting(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden bg-white border-none shadow-2xl">
          <DialogHeader className="p-6 pb-0">
            <DialogTitle className="text-2xl font-bold tracking-tight text-neutral-900">
              Add Company
            </DialogTitle>
            <DialogDescription className="text-neutral-500 mt-2">
              Audit any of the ~10,000 SEC-registered companies. We will download and index the most recent 10-K filings.
            </DialogDescription>
          </DialogHeader>

          <div className="p-6 space-y-6">
            {/* Search Input */}
            <div className="relative group">
              <div className={cn(
                "flex items-center px-4 rounded-2xl border-2 transition-all duration-300",
                search.length >= 2 ? "border-neutral-900 ring-4 ring-neutral-50" : "border-neutral-100 bg-neutral-50/50"
              )}>
                <Search className={cn(
                  "w-5 h-5 mr-3 transition-colors duration-300",
                  search.length >= 2 ? "text-neutral-900" : "text-neutral-400"
                )} />
                <Input
                  placeholder="Search by name, ticker, or CIK..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="border-none bg-transparent focus-visible:ring-0 px-0 h-14 text-lg placeholder:text-neutral-400"
                  autoFocus
                />
                {search && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => setSearch("")}
                    className="h-8 w-8 hover:bg-neutral-200 rounded-full"
                  >
                    <X className="h-4 w-4 text-neutral-500" />
                  </Button>
                )}
              </div>

              {/* Suggestions dropdown */}
              {search.length >= 2 && suggestions.length > 0 && !selected && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-neutral-100 rounded-2xl shadow-xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                  <div className="p-2 max-h-[300px] overflow-y-auto overscroll-contain">
                    {suggestions.map((c) => (
                      <button
                        key={`${c.cik}-${c.ticker}`}
                        onClick={() => handleSelect(c)}
                        className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-neutral-50 transition-colors text-left group/item"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center text-neutral-500 group-hover/item:bg-neutral-900 group-hover/item:text-white transition-colors">
                            <Building2 className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="font-semibold text-neutral-900 leading-none mb-1">
                              {c.name}
                            </div>
                            <div className="text-xs text-neutral-500 font-medium">
                              {c.ticker} • CIK {c.cik}
                            </div>
                          </div>
                        </div>
                        {existingCiks.has(c.cik) && (
                          <Badge variant="outline" className="bg-neutral-50 text-neutral-400 border-neutral-200 text-[10px] uppercase tracking-wider">
                            In Database
                          </Badge>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {search.length >= 2 && suggestions.length === 0 && !loading && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-neutral-100 rounded-2xl p-6 text-center text-neutral-400 z-50 shadow-xl">
                  No matching companies found.
                </div>
              )}
            </div>

            {/* Selected Company Preview */}
            {selected && (
              <div className="rounded-3xl border border-neutral-200 p-6 bg-neutral-50/50 space-y-4 animate-in zoom-in-95 duration-200">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xl font-bold text-neutral-900">{selected.name}</h4>
                      <Badge className="bg-neutral-900 text-white hover:bg-neutral-900 border-none rounded-md px-1.5 py-0">
                        {selected.ticker}
                      </Badge>
                    </div>
                    <p className="text-sm text-neutral-500 font-medium">CIK: {selected.cik}</p>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => setSelected(null)}
                    className="h-8 w-8 hover:bg-neutral-200 rounded-full"
                  >
                    <X className="h-4 w-4 text-neutral-400" />
                  </Button>
                </div>

                <Separator className="bg-neutral-200" />

                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center gap-3 text-sm text-neutral-600 font-medium">
                    <FileText className="w-4 h-4 text-neutral-400" />
                    Latest 10-K Filings
                  </div>
                  <div className="flex items-center gap-3 text-sm text-neutral-600 font-medium">
                    <Database className="w-4 h-4 text-neutral-400" />
                    Full XBRL Dataset
                  </div>
                </div>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-2xl bg-red-50 border border-red-100 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
                <p className="text-sm text-red-700 font-medium leading-relaxed">{error}</p>
              </div>
            )}
          </div>

          <DialogFooter className="p-6 bg-neutral-50/50 border-t border-neutral-100">
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              className="rounded-2xl h-12 px-6 font-semibold"
              disabled={starting}
            >
              Cancel
            </Button>
            <Button
              onClick={() => handleStartIngestion(false)}
              disabled={!selected || starting || loading}
              className="rounded-2xl h-12 px-8 font-bold bg-neutral-900 hover:bg-neutral-800 text-white shadow-lg shadow-neutral-200 transition-all active:scale-95 disabled:opacity-50"
            >
              {starting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  Add Company
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirmation Dialog for Re-ingestion */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent className="sm:max-w-[425px] p-8 rounded-[32px] border-none shadow-2xl">
          <div className="flex flex-col items-center text-center space-y-6">
            <div className="w-20 h-20 rounded-full bg-amber-50 flex items-center justify-center">
              <AlertCircle className="w-10 h-10 text-amber-500" />
            </div>
            
            <div className="space-y-2">
              <DialogTitle className="text-2xl font-bold text-neutral-900">
                Company already exists
              </DialogTitle>
              <DialogDescription className="text-neutral-500 text-base leading-relaxed">
                <span className="font-bold text-neutral-900">{selected?.name}</span> is already in your database with <span className="font-bold text-neutral-900">{existingInfo?.filings_count} filings</span> and <span className="font-bold text-neutral-900">{existingInfo?.audit_runs_count} audits</span>.
                <br /><br />
                Re-ingesting will <span className="text-red-500 font-bold uppercase">delete everything</span> related to this company. Continue?
              </DialogDescription>
            </div>

            <div className="grid grid-cols-2 gap-4 w-full pt-4">
              <Button
                variant="outline"
                onClick={() => setShowConfirmDialog(false)}
                className="rounded-2xl h-14 font-bold border-2 border-neutral-100 hover:bg-neutral-50"
              >
                No, Keep it
              </Button>
              <Button
                onClick={() => handleStartIngestion(true)}
                disabled={starting}
                className="rounded-2xl h-14 font-bold bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-100 transition-all active:scale-95"
              >
                {starting ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  "Yes, Re-ingest"
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
