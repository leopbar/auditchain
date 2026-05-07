import { API_BASE_URL } from "@/lib/api/client";

export interface SecCompany {
  cik: string;
  ticker: string;
  name: string;
}

// Module-level cache to avoid redundant fetches
let cachedSecCompanies: SecCompany[] | null = null;

/**
 * Fetches the list of companies from our backend proxy.
 * This bypasses CORS issues when fetching directly from SEC.
 */
export async function fetchSecCompanies(): Promise<SecCompany[]> {
  if (cachedSecCompanies) {
    return cachedSecCompanies;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/companies/sec-directory`, {
      credentials: "include",
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch SEC companies: ${response.statusText}`);
    }

    const data = await response.json();
    const normalized: SecCompany[] = data.companies;

    // Sort by name for better UX
    normalized.sort((a, b) => a.name.localeCompare(b.name));

    cachedSecCompanies = normalized;
    return normalized;
  } catch (error) {
    console.error("SEC company fetch error:", error);
    return [];
  }
}
