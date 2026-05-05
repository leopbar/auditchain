"use client";

import { FileText } from "lucide-react";

interface ExecutiveSummaryProps {
  summary: string;
}

export function ExecutiveSummary({ summary }: ExecutiveSummaryProps) {
  // Split into paragraphs based on single or double newlines
  const paragraphs = summary
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
  
  return (
    <section className="bg-white border border-neutral-200 rounded-2xl p-8 shadow-sm">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-neutral-50 border border-neutral-100 flex items-center justify-center shadow-inner">
          <FileText className="w-5 h-5 text-neutral-600" />
        </div>
        <h2 className="text-xl font-black text-neutral-900 tracking-tight">Executive Summary</h2>
      </div>
      
      <div className="max-w-none">
        {paragraphs.map((paragraph, idx) => (
          <p
            key={idx}
            className="text-neutral-700 leading-relaxed mb-6 last:mb-0 text-lg"
            style={{ 
              fontFamily: "var(--font-serif, Georgia, 'Times New Roman', serif)",
              letterSpacing: "-0.011em" 
            }}
          >
            {paragraph}
          </p>
        ))}
      </div>
    </section>
  );
}
