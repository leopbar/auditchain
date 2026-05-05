"use client";

import { Search, Quote, Users, FileText, AlertCircle, CheckCircle2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { InvestigationAnalysis } from "@/types/audit";
import { cn } from "@/lib/utils";

interface InvestigationSectionProps {
  investigation: InvestigationAnalysis;
}

export function InvestigationSection({ investigation }: InvestigationSectionProps) {
  const { summary, evasive_language_detected, related_parties_detected, mdna_findings, risk_factors_summary, key_quotes } = investigation;

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <Search className="w-6 h-6 text-primary" />
          Qualitative Investigation
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0 space-y-8">
        {summary && (
          <p className="text-xl leading-relaxed text-muted-foreground">{summary}</p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Indicators Grid */}
          <Card className="p-6 border-2">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-lg">
                  <FileText className="w-5 h-5 text-primary" />
                  Evasive Language
                </div>
                <Badge 
                  className={cn("px-3 py-1", 
                    evasive_language_detected ? "bg-red-500 hover:bg-red-600" : "bg-green-500 hover:bg-green-600"
                  )}
                >
                  {evasive_language_detected ? "YES DETECTED" : "NO SIGNS FOUND"}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-lg">
                  <Users className="w-5 h-5 text-primary" />
                  Related Parties
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-black text-2xl">{related_parties_detected.length}</span>
                  <span className="text-sm text-muted-foreground">Detected</span>
                </div>
              </div>
              
              {related_parties_detected.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {related_parties_detected.map((party, i) => (
                    <Badge key={i} variant="outline" className="bg-muted/50">{party}</Badge>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <div className="space-y-4">
             <div className="p-5 rounded-2xl bg-muted/30 border border-border/50">
                <h4 className="flex items-center gap-2 font-bold mb-2">
                  <AlertCircle className="w-4 h-4 text-primary" />
                  MD&A Findings
                </h4>
                <p className="text-sm text-muted-foreground line-clamp-4">
                  {mdna_findings || "No specific findings or boilerplate language identified in Management's Discussion and Analysis."}
                </p>
             </div>
             <div className="p-5 rounded-2xl bg-muted/30 border border-border/50">
                <h4 className="flex items-center gap-2 font-bold mb-2">
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  Risk Factors Summary
                </h4>
                <p className="text-sm text-muted-foreground line-clamp-4">
                  {risk_factors_summary || "Disclosure follows standard industry risk profile."}
                </p>
             </div>
          </div>
        </div>

        {key_quotes.length > 0 && (
          <div className="space-y-4 mt-8">
            <h4 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4">Critical Disclosure Excerpts</h4>
            <div className="grid gap-6">
              {key_quotes.map((quote, i) => (
                <div key={i} className="relative p-8 bg-muted/20 rounded-3xl border-l-8 border-primary/30 italic">
                  <Quote className="absolute top-4 left-4 w-12 h-12 text-primary/5 -z-10" />
                  <p className="text-lg leading-relaxed mb-4">"{quote.quote}"</p>
                  <div className="flex items-center gap-2 not-italic text-sm font-bold text-primary">
                    <span className="uppercase tracking-tighter">Context:</span>
                    <span className="text-muted-foreground font-medium">{quote.context}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

import { ShieldCheck } from "lucide-react";
