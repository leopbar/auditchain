"use client";

import { CheckSquare } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface RecommendationsSectionProps {
  recommendations: string[];
}

export function RecommendationsSection({ recommendations }: RecommendationsSectionProps) {
  if (!recommendations || recommendations.length === 0) return null;

  return (
    <Card className="border-none shadow-none bg-transparent">
      <CardHeader className="px-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-2xl font-bold">
          <CheckSquare className="w-6 h-6 text-primary" />
          Recommendations
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        <div className="space-y-4">
          {recommendations.map((rec, i) => (
            <div key={i} className="flex gap-4 items-start bg-blue-500/5 border border-blue-500/10 p-5 rounded-2xl">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold text-sm">
                {i + 1}
              </div>
              <p className="text-lg font-medium">{rec}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
