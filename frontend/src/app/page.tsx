import { Header } from "@/components/layout/header";
import { CompaniesGrid } from "@/components/audit/companies-grid";
import { listCompanies, listAudits } from "@/lib/api/client";
import { DashboardSection } from "@/components/dashboard/dashboard-section";
import type { Company, AuditSummary } from "@/types/audit";

import { cookies } from "next/headers";

// Force dynamic rendering to ensure fresh data on every visit
export const dynamic = "force-dynamic";

export default async function HomePage() {
  let companies: Company[] = [];
  let audits: AuditSummary[] = [];
  let error: string | null = null;
  
  try {
    const cookieStore = await cookies();
    const cookieHeader = cookieStore.toString();

    // Parallel fetch of companies and audits with forwarded cookies
    const [companiesRes, auditsRes] = await Promise.all([
      listCompanies({ headers: { Cookie: cookieHeader } }),
      listAudits({}, { headers: { Cookie: cookieHeader } })
    ]);
    
    companies = companiesRes.companies;
    audits = auditsRes.audits;
  } catch (err) {
    console.error("Failed to fetch dashboard data:", err);
    error = err instanceof Error ? err.message : "Failed to load dashboard data";
  }
  
  const hasAudits = audits.length > 0;

  return (
    <div className="min-h-screen bg-neutral-50 pb-20">
      <Header />
      
      <main className="container mx-auto px-4 md:px-8 py-12 max-w-7xl overflow-hidden">
        {/* Compact Hero Section */}
        <section className="mb-12">
          <h1 className="text-4xl font-bold text-neutral-900 tracking-tight">
            AuditChain Executive Dashboard
          </h1>
          <p className="text-neutral-500 mt-2 text-lg">
            Intelligent fraud detection and financial integrity analysis.
          </p>
        </section>

        {/* Error Handling */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-12">
            <p className="text-sm text-red-800 font-medium">
              Dashboard sync failed: {error}
            </p>
            <p className="text-xs text-red-600 mt-2">
              Make sure the back-end API is running and accessible
            </p>
          </div>
        )}

        {/* Dashboard Section (Metrics, Charts, Recent Audits) */}
        {!error && hasAudits ? (
          <DashboardSection audits={audits} />
        ) : !error && (
          <div className="mb-16 py-16 text-center border-2 border-dashed border-neutral-200 rounded-3xl bg-neutral-100/50">
            <div className="max-w-md mx-auto space-y-4">
              <h2 className="text-2xl font-bold text-neutral-800">Ready to audit?</h2>
              <p className="text-neutral-500">
                You haven't run any audits yet. Select a company from the list below to generate your first executive report.
              </p>
            </div>
          </div>
        )}

        {/* Available Companies Section */}
        <section className="space-y-8">
          <div className="flex flex-col gap-1">
            <h2 className="text-2xl font-bold tracking-tight text-neutral-900">
              Available Companies
            </h2>
            <p className="text-neutral-500">
              Select a target entity to begin a multi-agent audit pipeline.
            </p>
          </div>
          
          {!error && (
            <CompaniesGrid companies={companies} />
          )}
        </section>
      </main>
    </div>
  );
}
