"use client";

import { use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  Building2,
  FileText,
  BarChart3,
  Search,
  Database,
  Cpu,
  Loader2,
  Check,
  X,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  useIngestionStream,
  STAGE_ORDER,
  STAGE_LABELS,
  type IngestionStage,
} from "@/hooks/use-ingestion-stream";
import { cn } from "@/lib/utils";

interface IngestionPageProps {
  params: Promise<{ ingestion_id: string }>;
}

export default function IngestionPage({ params }: IngestionPageProps) {
  const { ingestion_id } = use(params);
  const stream = useIngestionStream(ingestion_id);

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return null;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const getStageIcon = (stage: IngestionStage) => {
    switch (stage) {
      case "validate":
        return <Search className="w-4 h-4" />;
      case "download_facts":
        return <Database className="w-4 h-4" />;
      case "download_filings":
        return <FileText className="w-4 h-4" />;
      case "parse_xbrl":
        return <BarChart3 className="w-4 h-4" />;
      case "embed_text":
        return <Cpu className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 pb-20">
      {/* Sticky Header */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-neutral-100">
        <div className="container mx-auto px-4 md:px-8 h-20 flex items-center justify-between max-w-7xl">
          <div className="flex items-center gap-6">
            <Link href="/">
              <Button variant="ghost" size="icon" className="rounded-full hover:bg-neutral-100">
                <ArrowLeft className="w-5 h-5 text-neutral-600" />
              </Button>
            </Link>
            <div className="flex flex-col">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-neutral-900 tracking-tight">
                  {stream.companyInfo?.name || "Initializing Ingestion..."}
                </h1>
                {stream.companyInfo?.ticker && (
                  <Badge className="bg-neutral-900 text-white rounded-md">
                    {stream.companyInfo.ticker}
                  </Badge>
                )}
                {stream.companyInfo?.isUpdate && (
                  <Badge variant="outline" className="text-amber-600 border-amber-200 bg-amber-50">
                    Update
                  </Badge>
                )}
              </div>
              <p className="text-sm text-neutral-500 font-medium flex items-center gap-2">
                <Clock className="w-3 h-3" />
                {formatDuration(stream.elapsedSeconds)} elapsed
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Badge variant="outline" className={cn(
              "px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider",
              stream.connected ? "text-emerald-600 border-emerald-100 bg-emerald-50" : "text-neutral-400 border-neutral-100 bg-neutral-50"
            )}>
              {stream.connected ? "Live Connection" : "Disconnected"}
            </Badge>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 md:px-8 py-12 max-w-5xl space-y-12">
        {/* Pipeline Progress Bar */}
        <div className="relative">
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-neutral-200 -translate-y-1/2" />
          <div className="relative flex justify-between">
            {STAGE_ORDER.map((stageId) => {
              const stage = stream.stages[stageId];
              const isCompleted = stage.status === "completed";
              const isRunning = stage.status === "running";
              const isFailed = stage.status === "failed";

              return (
                <div key={stageId} className="flex flex-col items-center gap-3 z-10 bg-neutral-50 px-2">
                  <div className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500",
                    isCompleted ? "bg-emerald-500 text-white scale-110 shadow-lg shadow-emerald-100" :
                    isRunning ? "bg-neutral-900 text-white ring-4 ring-neutral-100 animate-pulse" :
                    isFailed ? "bg-red-500 text-white" :
                    "bg-white border-2 border-neutral-200 text-neutral-400"
                  )}>
                    {isCompleted ? <Check className="w-5 h-5" /> : 
                     isFailed ? <AlertCircle className="w-5 h-5" /> : 
                     getStageIcon(stageId)}
                  </div>
                  <span className={cn(
                    "text-[10px] font-bold uppercase tracking-widest hidden md:block",
                    isRunning ? "text-neutral-900" : "text-neutral-400"
                  )}>
                    {STAGE_LABELS[stageId].split(' ').pop()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Current Stage Detail */}
        {stream.currentStage && (
          <Card className="p-8 border-none shadow-2xl shadow-neutral-200/50 rounded-[32px] overflow-hidden relative group">
            <div className="absolute top-0 left-0 w-2 h-full bg-neutral-900" />
            <div className="space-y-8">
              <div className="flex justify-between items-start">
                <div className="space-y-2">
                  <Badge variant="outline" className="bg-neutral-50 text-neutral-500 border-neutral-100 uppercase tracking-widest text-[10px]">
                    Current Stage
                  </Badge>
                  <h2 className="text-3xl font-black text-neutral-900">
                    {STAGE_LABELS[stream.currentStage]}
                  </h2>
                </div>
                <div className="p-4 rounded-3xl bg-neutral-100 text-neutral-900">
                  {getStageIcon(stream.currentStage)}
                </div>
              </div>

              {stream.stages[stream.currentStage].progress ? (
                <div className="space-y-4">
                  <div className="flex justify-between text-sm font-bold">
                    <span className="text-neutral-900">
                      {stream.stages[stream.currentStage].progress?.message}
                    </span>
                    <span className="text-neutral-400">
                      {Math.round((stream.stages[stream.currentStage].progress!.current / stream.stages[stream.currentStage].progress!.total) * 100)}%
                    </span>
                  </div>
                  <Progress 
                    value={(stream.stages[stream.currentStage].progress!.current / stream.stages[stream.currentStage].progress!.total) * 100} 
                    className="h-3 bg-neutral-100"
                  />
                  <p className="text-xs text-neutral-400 font-medium">
                    Processing {stream.stages[stream.currentStage].progress?.current} of {stream.stages[stream.currentStage].progress?.total} items...
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-4 text-neutral-500 italic py-4">
                  <Loader2 className="w-5 h-5 animate-spin text-neutral-900" />
                  Initialising data pipeline components...
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Success / Failure States */}
        {stream.result && (
          <Card className="p-10 border-none shadow-2xl shadow-emerald-100/50 rounded-[40px] bg-white border-t-8 border-emerald-500 overflow-hidden text-center space-y-8 animate-in zoom-in-95 duration-500">
            <div className="w-24 h-24 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center mx-auto mb-6 ring-8 ring-emerald-50/50">
              <CheckCircle2 className="w-12 h-12" />
            </div>
            
            <div className="space-y-2">
              <h2 className="text-4xl font-black text-neutral-900 tracking-tight">Ingestion Complete</h2>
              <p className="text-neutral-500 text-lg">
                {stream.companyInfo?.name} has been successfully indexed and is ready for multi-agent auditing.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-6 pt-4 max-w-2xl mx-auto">
              <div className="p-6 rounded-3xl bg-neutral-50 border border-neutral-100">
                <div className="text-2xl font-black text-neutral-900">{stream.result.filings_count}</div>
                <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mt-1">Filings</div>
              </div>
              <div className="p-6 rounded-3xl bg-neutral-50 border border-neutral-100">
                <div className="text-2xl font-black text-neutral-900">{stream.result.financial_items_extracted}</div>
                <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mt-1">Line Items</div>
              </div>
              <div className="p-6 rounded-3xl bg-neutral-50 border border-neutral-100">
                <div className="text-2xl font-black text-neutral-900">{stream.result.chunks_generated}</div>
                <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mt-1">Text Chunks</div>
              </div>
            </div>

            <div className="pt-8">
              <Link href="/">
                <Button className="rounded-2xl h-16 px-12 text-lg font-black bg-neutral-900 hover:bg-neutral-800 text-white shadow-xl shadow-neutral-200 transition-all hover:scale-105 active:scale-95">
                  View Company in Dashboard
                  <ArrowRight className="w-6 h-6 ml-3" />
                </Button>
              </Link>
            </div>
          </Card>
        )}

        {stream.failure && (
          <Card className="p-10 border-none shadow-2xl shadow-red-100/50 rounded-[40px] bg-white border-t-8 border-red-500 text-center space-y-6 animate-in shake-in duration-500">
            <div className="w-20 h-20 rounded-full bg-red-50 text-red-500 flex items-center justify-center mx-auto">
              <AlertCircle className="w-10 h-10" />
            </div>
            <div className="space-y-2">
              <h2 className="text-3xl font-black text-neutral-900">Ingestion Failed</h2>
              <p className="text-red-600 font-bold uppercase tracking-widest text-xs">
                Error in stage: {stream.failure.failed_stage}
              </p>
              <div className="mt-4 p-6 rounded-2xl bg-neutral-50 text-neutral-600 font-mono text-sm break-all border border-neutral-100">
                {stream.failure.error_message}
              </div>
            </div>
            <div className="pt-6">
              <Link href="/">
                <Button variant="outline" className="rounded-2xl h-14 px-8 font-bold border-2 border-neutral-100">
                  Return to Dashboard
                </Button>
              </Link>
            </div>
          </Card>
        )}

        {/* Completed Stages List */}
        <div className="space-y-4">
          <h3 className="text-sm font-bold text-neutral-400 uppercase tracking-widest px-2">
            Execution Log
          </h3>
          <div className="space-y-2">
            {STAGE_ORDER.map((stageId) => {
              const stage = stream.stages[stageId];
              if (stage.status === "pending" || stage.status === "running") return null;

              return (
                <div 
                  key={stageId}
                  className="group flex items-center justify-between p-4 px-6 rounded-2xl bg-white border border-neutral-100 hover:border-neutral-200 transition-all"
                >
                  <div className="flex items-center gap-4">
                    <div className={cn(
                      "w-8 h-8 rounded-xl flex items-center justify-center",
                      stage.status === "completed" ? "bg-emerald-50 text-emerald-500" : "bg-red-50 text-red-500"
                    )}>
                      {stage.status === "completed" ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="font-bold text-neutral-900">{STAGE_LABELS[stageId]}</div>
                      <div className="text-xs text-neutral-400 font-medium">
                        {stage.status === "completed" ? `Finished in ${formatDuration(stage.duration)}` : "Failed during processing"}
                      </div>
                    </div>
                  </div>
                  {stage.status === "completed" && (
                    <div className="flex gap-2">
                      {Object.entries(stage.summary || {}).slice(0, 2).map(([key, value]) => (
                        <Badge key={key} variant="outline" className="bg-neutral-50 text-neutral-400 border-none text-[10px] font-bold">
                          {key.replace(/_/g, ' ')}: {String(value)}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
