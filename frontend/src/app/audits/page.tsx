import { Header } from "@/components/layout/header";
import { listAudits } from "@/lib/api/client";
import { AuditHistoryList } from "@/components/audit-history/audit-history-list";
import Link from "next/link";
import { ChevronLeft, History } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function AuditHistoryPage() {
  const { audits } = await listAudits();

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col">
      <Header />
      
      <main className="container mx-auto px-6 py-12 max-w-6xl flex-1 space-y-10">
        {/* Compact Hero Section */}
        <section className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <Link 
              href="/" 
              className="inline-flex items-center gap-1.5 text-sm font-medium text-neutral-500 hover:text-primary transition-colors mb-2"
            >
              <ChevronLeft className="w-4 h-4" /> Back to Dashboard
            </Link>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-neutral-900 text-white shadow-lg">
                <History className="w-6 h-6" />
              </div>
              <h1 className="text-4xl font-bold text-neutral-900 tracking-tight">
                Audit History
              </h1>
            </div>
            <p className="text-neutral-500 text-lg">
              Comprehensive log of all investigative audit runs performed by the system.
            </p>
          </div>
        </section>

        <AuditHistoryList initialAudits={audits} />
      </main>
    </div>
  );
}
