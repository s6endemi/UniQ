/**
 * Typed client for the UniQ FastAPI backend.
 *
 * Browser code never calls this directly — it goes through Next.js BFF
 * routes under /api/uniq/* which call this module server-side. That keeps
 * the FastAPI base URL out of the client bundle and centralises auth /
 * streaming concerns in Next.js.
 */

const FASTAPI_BASE = process.env.UNIQ_API_BASE ?? "http://127.0.0.1:8000";

export type ConfidenceLevel = "high" | "medium" | "low";
export type ReviewStatus = "pending" | "approved" | "overridden" | "rejected";

export interface CodeEntry {
  system: string;
  code: string;
  display?: string | null;
}

export interface MappingEntry {
  category: string;
  display_label: string;
  standard_concept: string | null;
  fhir_resource_type: string;
  fhir_category: string | null;
  codes: CodeEntry[];
  confidence: ConfidenceLevel;
  review_status: ReviewStatus;
  reasoning: string | null;
  validation_errors?: string[] | null;
}

export interface MappingUpdate {
  display_label?: string;
  standard_concept?: string | null;
  fhir_resource_type?: string;
  fhir_category?: string | null;
  codes?: CodeEntry[];
  reasoning?: string;
  review_status?: "approved" | "overridden" | "rejected";
}

export interface HealthResponse {
  status: "ok" | "degraded";
  artifacts_loaded: boolean;
  patients: number;
  categories: number;
  mapping_entries: number;
}

export interface PatientRecord {
  user_id: number;
  gender: string;
  current_age: number;
  total_treatments: number;
  active_treatments: number;
  current_medication: string | null;
  current_dosage: string | null;
  tenure_days: number | null;
  latest_bmi: number | null;
  earliest_bmi: number | null;
  bmi_change: number | null;
}

export interface ColumnInfo {
  column: string;
  type: string;
}

export interface SchemaResponse {
  tables: Record<string, ColumnInfo[]>;
}

export interface CategoriesResponse {
  categories: string[];
  count: number;
}

export interface ChatResponse {
  reply: string;
  sql: string | null;
  rows: Array<Record<string, unknown>> | null;
  chart_spec: Record<string, unknown> | null;
  truncated: boolean;
}

class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(`UniQ API ${status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${FASTAPI_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, body);
  }
  return body as T;
}

export const uniq = {
  health: () => request<HealthResponse>("/health"),
  schema: () => request<SchemaResponse>("/schema"),
  categories: () => request<CategoriesResponse>("/categories"),

  listMapping: () => request<MappingEntry[]>("/mapping"),
  getMapping: (category: string) =>
    request<MappingEntry>(`/mapping/${encodeURIComponent(category)}`),
  patchMapping: (category: string, update: MappingUpdate) =>
    request<MappingEntry>(`/mapping/${encodeURIComponent(category)}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),

  getPatient: (id: number) => request<PatientRecord>(`/patients/${id}`),
  fhirExport: (id: number) => request<Record<string, unknown>>(`/export/${id}/fhir`),

  chat: (message: string, sessionId?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId ?? null }),
    }),
};

export { ApiError };
