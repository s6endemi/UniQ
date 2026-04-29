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

export interface MappingResetResponse {
  approved: number;
  rejected: number;
  pending: number;
  overridden: number;
  changed: number;
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

export type ResourceStatus = "signed" | "queryable" | "exportable" | "monitored" | "next";

export interface SubstrateForeignKey {
  target_resource: string;
  key: string;
  label: string;
}

export interface SubstrateResource {
  name: string;
  label: string;
  row_count: number;
  primary_key: string;
  foreign_keys: SubstrateForeignKey[];
  sample_fields: string[];
  status: ResourceStatus;
  api_hooks: string[];
}

export interface SubstrateRelationship {
  from_resource: string;
  to_resource: string;
  key: string;
  label: string;
}

export interface SubstrateAuditEvent {
  label: string;
  detail: string;
  status: ReviewStatus;
}

export interface SubstrateManifestResponse {
  version: string;
  headline: string;
  resources: SubstrateResource[];
  relationships: SubstrateRelationship[];
  audit_events: SubstrateAuditEvent[];
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

// --- Patient record artifact ---------------------------------------------
//
// Single-patient deep view. Mirror of `wellster-pipeline/src/api/models.py`.
// Where cohort_trend answers "what does this population do over time?",
// patient_record answers "what is the full, audited clinical story of one
// person?". Each PatientEvent carries enough provenance to render the
// audit-trail card without a second backend round-trip.

export type PatientEventTrack =
  | "bmi"
  | "medication"
  | "side_effect"
  | "condition"
  | "quality"
  | "survey"
  | "annotation";

// --- Clinical annotations -------------------------------------------------
//
// First write-back resource on the substrate. Mirror of
// `wellster-pipeline/src/api/models.py::ClinicalAnnotation`. Lives next
// to PatientEvent because annotations are rendered as a 5th timeline
// track inside the patient_record artifact.

export type AnnotationCategory =
  | "clinical_note"
  | "correction"
  | "follow_up"
  | "risk_flag";

export interface ClinicalAnnotation {
  id: string;
  patient_id: number;
  event_id: string | null;
  category: AnnotationCategory;
  note: string;
  author: string;
  role: string;
  created_at: string;
}

export interface ClinicalAnnotationCreate {
  note: string;
  event_id?: string | null;
  category?: AnnotationCategory;
}

export type PatientEventSeverity = "normal" | "info" | "warn" | "alert";

export interface PatientHeader {
  user_id: number;
  label: string;
  brand: string | null;
  gender: string;
  current_age: number;
  current_medication: string | null;
  current_dosage: string | null;
  tenure_days: number | null;
  status: "active" | "inactive";
}

export interface PatientMedicationSegment {
  name: string;
  dosage: string | null;
  started: string;
  ended: string | null;
}

export interface PatientEvent {
  id: string;
  track: PatientEventTrack;
  timestamp: string;
  label: string;
  detail: string | null;
  severity: PatientEventSeverity | null;
  value: number | null;
  source_field: string | null;
  source_category: string | null;
  code_system: string | null;
  code: string | null;
  review_status: ReviewStatus | null;
}

export interface PatientBmiPoint {
  date: string;
  value: number;
}

export interface PatientRecordPayload {
  header: PatientHeader;
  kpis: Kpi[];
  medications: PatientMedicationSegment[];
  events: PatientEvent[];
  bmi_series: PatientBmiPoint[];
  timeline_start: string;
  timeline_end: string;
  quality_summary: Record<string, number>;
  fhir_resource_count: number;
  source_field_count: number;
}

// --- Opportunity / screening-candidates artifact -------------------------
//
// Cross-brand candidate list: patients on `source_brand` who could be
// screened for `target_brand` follow-up. Mirror of
// `wellster-pipeline/src/api/models.py::OpportunityListPayload`.
//
// UI language is "Screening candidates", never "eligible" or "leads" —
// we surface the cohort, the operational decision belongs to the
// customer's clinical / outreach team. No revenue figures appear here:
// the truth layer reports the cohort, the customer values it.

export type CandidatePriority = "high" | "medium" | "low";
export type TrendDirection = "up" | "down" | "stable" | "unknown";

export interface ActivationFilterStep {
  label: string;
  count: number;
  description: string | null;
}

export interface ScreeningCandidate {
  user_id: number;
  label: string;
  latest_bmi: number | null;
  bmi_trend: TrendDirection;
  age: number | null;
  gender: string | null;
  current_treatment: string | null;
  current_dosage: string | null;
  tenure_days: number | null;
  days_since_activity: number | null;
  reason_summary: string;
  priority: CandidatePriority;
}

export interface OpportunityListPayload {
  headline: string;
  methodology: string;
  activation_path: ActivationFilterStep[];
  kpis: Kpi[];
  candidates: ScreeningCandidate[];
  total_candidates: number;
  source_brand: string;
  target_brand: string;
  bmi_threshold: number;
  activity_window_days: number;
}

export type ArtifactKind =
  | "cohort_trend"
  | "alerts_table"
  | "table"
  | "fhir_bundle"
  | "patient_record"
  | "opportunity_list";

export type ChatArtifact =
  | { kind: "cohort_trend"; id: string; title: string; subtitle: string; payload: CohortTrendPayload }
  | { kind: "alerts_table"; id: string; title: string; subtitle: string; payload: AlertsTablePayload }
  | { kind: "table"; id: string; title: string; subtitle: string; payload: TablePayload }
  | { kind: "fhir_bundle"; id: string; title: string; subtitle: string; payload: FhirBundlePayload }
  | { kind: "patient_record"; id: string; title: string; subtitle: string; payload: PatientRecordPayload }
  | { kind: "opportunity_list"; id: string; title: string; subtitle: string; payload: OpportunityListPayload };

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
  substrateManifest: () => request<SubstrateManifestResponse>("/v1/substrate/manifest"),

  listMapping: () => request<MappingEntry[]>("/mapping"),
  getMapping: (category: string) =>
    request<MappingEntry>(`/mapping/${encodeURIComponent(category)}`),
  patchMapping: (category: string, update: MappingUpdate) =>
    request<MappingEntry>(`/mapping/${encodeURIComponent(category)}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),
  resetMapping: () =>
    request<MappingResetResponse>("/mapping/reset", { method: "POST" }),

  getPatient: (id: number) => request<PatientRecord>(`/patients/${id}`),
  fhirExport: (id: number) => request<Record<string, unknown>>(`/export/${id}/fhir`),

  chat: (message: string, sessionId?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId ?? null }),
    }),
};

export { ApiError };
