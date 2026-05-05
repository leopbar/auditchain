"use client";

import { FileText } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface ExecutiveSummarySectionProps {
  summary: string;
}

export function ExecutiveSummarySection({ summary }: ExecutiveSummarySectionProps) {
  if (!summary) return null;

  // Split by double newline to handle paragraphs
  const paragraphs = summary.split("\n\n").filter(p => p.trim().length > 0);

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <FileText className="w-6 h-6 text-primary" />
          Executive Summary
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        <div className="space-y-6">
          {paragraphs.map((para, i) => (
            <p 
              key={i} 
              className="text-xl leading-relaxed text-foreground/90 font-serif antialiased"
              style={{ fontFamily: 'Georgia, serif' }}
            >
              {para}
            </p>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
