"use client";

import { CheckSquare } from "lucide-react";

interface RecommendationsProps {
  recommendations: string[];
}

export function Recommendations({ recommendations }: RecommendationsProps) {
  if (!recommendations || recommendations.length === 0) {
    return null;
  }
  
  return (
    <section className="bg-white border border-neutral-200 rounded-2xl p-8 shadow-sm">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center shadow-inner">
          <CheckSquare className="w-5 h-5 text-blue-600" />
        </div>
        <h2 className="text-xl font-black text-neutral-900 tracking-tight">Strategic Recommendations</h2>
      </div>
      
      <div className="grid gap-4">
        {recommendations.map((rec, idx) => (
          <div key={idx} className="flex gap-5 p-5 rounded-2xl bg-neutral-50 border border-neutral-100 group hover:border-blue-200 hover:bg-blue-50/30 transition-all duration-300">
            <div className="shrink-0 w-8 h-8 rounded-full bg-white border border-neutral-200 text-neutral-400 group-hover:border-blue-500 group-hover:text-blue-600 flex items-center justify-center font-bold text-xs tabular-nums transition-colors shadow-sm">
              {idx + 1}
            </div>
            <p className="text-neutral-700 leading-relaxed font-medium pt-1">
              {rec}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
