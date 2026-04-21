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

// --- Chat (Phase 6 — hybrid SQL agent with template artifacts) ------------
//
// Mirror of `wellster-pipeline/src/api/models.py::ChatResponse`. Four
// template families (see backend for rationale); extra kinds added later
// are pure additions to the discriminated union — existing consumers keep
// working unchanged.

export type DeltaDirection = "up" | "down" | "neutral";

export interface Kpi {
  label: string;
  value: string;
  delta?: string | null;
  delta_direction?: DeltaDirection | null;
}

export interface ChartSeries {
  name: string;
  points: number[];
}

export interface Chart {
  title: string;
  subtitle?: string | null;
  x_labels: string[];
  y_label?: string | null;
  series: ChartSeries[];
}

export interface TableColumn {
  key: string;
  label: string;
  align?: "left" | "right" | null;
  emphasis?: boolean;
}

export interface TableData {
  columns: TableColumn[];
  rows: Array<Record<string, string | number | null>>;
}

export interface CohortTrendPayload {
  kpis: Kpi[];
  chart: Chart;
  table: TableData;
}

export interface AlertsTablePayload {
  kpis: Kpi[];
  table: TableData;
}

export interface TablePayload {
  kpis?: Kpi[] | null;
  table: TableData;
}

export interface FhirBundlePayload {
  resourceType: "Bundle";
  id: string;
  type: string;
  timestamp: string;
  entry: Array<{ resource: Record<string, unknown> }>;
}

export type ArtifactKind =
  | "cohort_trend"
  | "alerts_table"
  | "table"
  | "fhir_bundle";

export type ChatArtifact =
  | { kind: "cohort_trend"; id: string; title: string; subtitle: string; payload: CohortTrendPayload }
  | { kind: "alerts_table"; id: string; title: string; subtitle: string; payload: AlertsTablePayload }
  | { kind: "table"; id: string; title: string; subtitle: string; payload: TablePayload }
  | { kind: "fhir_bundle"; id: string; title: string; subtitle: string; payload: FhirBundlePayload };

export interface ChatTrace {
  intent: string;
  recipe: string | null;
  sql: string[];
  row_counts: number[];
  artifact_kind: ArtifactKind | null;
}

export interface ChatResponse {
  steps: string[];
  reply: string;
  artifact: ChatArtifact | null;
  trace: ChatTrace;
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
