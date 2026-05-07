import type {
  Company,
  CompanyListResponse,
  AuditSummary,
  AuditListResponse,
  AuditDetail,
  CreateAuditRequest,
  CreateAuditResponse,
} from "@/types/audit";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_URL}${path}`;
  
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, detail);
  }
  
  return response.json();
}

// Companies
export async function listCompanies(options: RequestInit = {}): Promise<CompanyListResponse> {
  return request<CompanyListResponse>("/api/companies/", options);
}

export async function getCompany(cik: string, options: RequestInit = {}): Promise<Company> {
  return request<Company>(`/api/companies/${cik}`, options);
}

// Audits
export async function startAudit(payload: CreateAuditRequest): Promise<CreateAuditResponse> {
  return request<CreateAuditResponse>("/api/audits/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listAudits(
  params?: {
    limit?: number;
    status?: string;
  },
  options: RequestInit = {}
): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", params.limit.toString());
  if (params?.status) query.set("status", params.status);
  
  const queryStr = query.toString();
  const path = queryStr ? `/api/audits/?${queryStr}` : "/api/audits/";
  
  return request<AuditListResponse>(path, options);
}

export async function getAuditDetail(runId: string): Promise<AuditDetail> {
  return request<AuditDetail>(`/api/audits/${runId}`);
}

// API Info
export interface ApiInfo {
  statistics: {
    total_companies: number;
    total_audits: number;
  };
  available_models: {
    fast_model: string;
    smart_model: string;
  };
  environment: string;
}

export async function getApiInfo(): Promise<ApiInfo> {
  return request<ApiInfo>("/api/info");
}

import type {
  CreateIngestionRequest,
  CreateIngestionResponse,
} from "@/types/ingestion";

export { ApiError };
export const API_BASE_URL = API_URL;

// ─────────────────────────────────────────────────────────────────────────────
// Ingestion — Custom Errors
// ─────────────────────────────────────────────────────────────────────────────

export class CompanyExistsError extends Error {
  constructor(public cik: string, public detail: string) {
    super(detail);
    this.name = "CompanyExistsError";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Ingestion — API Functions
// ─────────────────────────────────────────────────────────────────────────────

export interface CheckCompanyResult {
  exists: boolean;
  company_name?: string;
  ticker?: string;
  filings_count?: number;
  audit_runs_count?: number;
}

export async function checkCompanyExists(cik: string): Promise<CheckCompanyResult> {
  return request<CheckCompanyResult>(`/api/companies/check/${cik}`);
}

export async function startIngestion(
  payload: CreateIngestionRequest,
): Promise<CreateIngestionResponse> {
  const url = `${API_URL}/api/companies/add`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch {
      // ignore parse errors
    }

    // Distinguish between "company already exists" (show modal) and
    // "ingestion already running" (show standard error)
    if (response.status === 409 && detail.includes("already exists")) {
      throw new CompanyExistsError(payload.cik, detail);
    }

    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export interface IngestionListResponse {
  ingestion_runs: Array<{
    ingestion_id: string;
    cik: string;
    status: string;
    current_stage: string | null;
    started_at: string | null;
    completed_at: string | null;
    duration_seconds: number | null;
    is_update: boolean;
    error_message: string | null;
    filings_count: number | null;
    chunks_generated: number | null;
    financial_items_extracted: number | null;
  }>;
  total: number;
}

export async function listIngestions(params?: {
  limit?: number;
  status?: string;
}): Promise<IngestionListResponse> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", params.limit.toString());
  if (params?.status) query.set("status", params.status);

  const queryStr = query.toString();
  const path = queryStr
    ? `/api/companies/ingestions?${queryStr}`
    : "/api/companies/ingestions";

  return request<IngestionListResponse>(path);
}
