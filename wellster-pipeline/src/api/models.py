"""Pydantic response / request models for the UniQ API.

Pydantic lives at the edge — it validates incoming requests and shapes
outgoing JSON, but does not leak into the Repository or QueryService
internals (those stay Pandas-native).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Shared primitives -----------------------------------------------------


class CodeEntry(BaseModel):
    system: str
    code: str
    display: str | None = None


ConfidenceLevel = Literal["high", "medium", "low"]
ReviewStatus = Literal["pending", "approved", "overridden", "rejected"]


# --- Mapping ---------------------------------------------------------------


class MappingEntry(BaseModel):
    """One semantic_mapping.json entry, exposed to clients."""

    category: str = Field(..., description="The discovered clinical_category name")
    display_label: str
    standard_concept: str | None = None
    fhir_resource_type: str
    fhir_category: str | None = None
    codes: list[CodeEntry] = Field(default_factory=list)
    confidence: ConfidenceLevel
    review_status: ReviewStatus = "pending"
    reasoning: str | None = None
    validation_errors: list[str] | None = None
    reviewed_by: str | None = None
    reviewed_role: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None


class MappingUpdate(BaseModel):
    """Partial update for a mapping entry. Only provided fields are changed."""

    display_label: str | None = None
    standard_concept: str | None = None
    fhir_resource_type: str | None = None
    fhir_category: str | None = None
    codes: list[CodeEntry] | None = None
    reasoning: str | None = None
    review_status: Literal["approved", "overridden", "rejected"] | None = None


# --- Schema / categories ---------------------------------------------------


class ColumnInfo(BaseModel):
    column: str
    type: str


class SchemaResponse(BaseModel):
    tables: dict[str, list[ColumnInfo]]


class CategoriesResponse(BaseModel):
    categories: list[str]
    count: int


# --- Normalization registry + queue -----------------------------------------
#
# The answer-normalization governance layer. Records are inspectable +
# reviewable per (category, original_value); unknowns surface in a queue
# rather than silently falling to null. Together they give Wellster a
# concrete answer to "how do you trust the answer normalization?".


NormalizationReviewStatus = Literal["pending", "approved", "overridden", "rejected"]
NormalizationQueueStatus = Literal["open", "promoted", "dismissed"]


class NormalizationRecordOut(BaseModel):
    id: str
    category: str
    original_value: str
    canonical_label: str
    review_status: NormalizationReviewStatus
    source_count: int
    first_seen: str | None = None
    last_seen: str | None = None
    reviewed_by: str | None = None
    reviewed_role: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None


class NormalizationRecordPatch(BaseModel):
    canonical_label: str | None = None
    review_status: NormalizationReviewStatus | None = None
    review_note: str | None = None


class NormalizationCoverage(BaseModel):
    total_records: int
    by_status_approved: int
    by_status_overridden: int
    by_status_pending: int
    by_status_rejected: int


class NormalizationListResponse(BaseModel):
    coverage: NormalizationCoverage
    records: list[NormalizationRecordOut]


class UnknownEntryOut(BaseModel):
    id: str
    category: str
    original_value: str
    first_seen: str
    last_seen: str
    occurrence_count: int
    status: NormalizationQueueStatus
    resolution: str | None = None
    resolved_by: str | None = None
    resolved_role: str | None = None
    resolved_at: str | None = None


class UnknownResolvePayload(BaseModel):
    """Payload for promoting / dismissing one unknown queue entry."""

    canonical_label: str | None = None
    status: NormalizationQueueStatus = "promoted"


class UnknownQueueResponse(BaseModel):
    stats: dict[str, int]
    entries: list[UnknownEntryOut]


# --- Clinical annotations ---------------------------------------------------
#
# First write-back resource on the substrate. Approval signs the schema;
# annotations let clinicians contribute clinical context back into the
# record post-signing. The substrate stops being a one-shot snapshot and
# starts being operational memory — the "Living Substrate" beat that
# Martin pushed for after the Spira call.
#
# Persistence is intentionally a flat JSON list (atomic_write_json) and
# not a database. For pitch + Wellster pilot we need durability and
# audit trail, not concurrent multi-writer integrity.


AnnotationCategory = Literal[
    "clinical_note",
    "correction",
    "follow_up",
    "risk_flag",
]


class ClinicalAnnotation(BaseModel):
    id: str
    patient_id: int
    event_id: str | None = Field(
        None,
        description=(
            "When the annotation is pinned to a specific timeline event "
            "(BMI measurement, medication change, side-effect report). "
            "Null for patient-level notes that don't belong to any one event."
        ),
    )
    category: AnnotationCategory = "clinical_note"
    note: str = Field(..., min_length=1)
    author: str
    role: str
    created_at: str  # ISO


class ClinicalAnnotationCreate(BaseModel):
    """Inbound payload for POST. Author/role/timestamp filled server-side."""

    note: str = Field(..., min_length=1, max_length=2000)
    event_id: str | None = None
    category: AnnotationCategory = "clinical_note"


# --- Substrate manifest ----------------------------------------------------


ResourceStatus = Literal["signed", "queryable", "exportable", "monitored", "next"]


class SubstrateForeignKey(BaseModel):
    target_resource: str
    key: str
    label: str


class SubstrateResource(BaseModel):
    name: str
    label: str
    row_count: int
    primary_key: str
    foreign_keys: list[SubstrateForeignKey] = Field(default_factory=list)
    sample_fields: list[str] = Field(default_factory=list)
    status: ResourceStatus
    api_hooks: list[str] = Field(default_factory=list)


class SubstrateRelationship(BaseModel):
    from_resource: str
    to_resource: str
    key: str
    label: str


class SubstrateAuditEvent(BaseModel):
    label: str
    detail: str
    status: ReviewStatus


class MaterializationManifestSummary(BaseModel):
    """Subset of the materialization manifest exposed via the substrate API.

    The full manifest lives at `output/materialization_manifest.json`.
    The summary surfaces the fields a consumer would actually verify
    (run_id, hashes, coverage stats) without forcing them to fetch a
    second endpoint."""

    run_id: str
    generated_at: str
    git_commit: str | None = None
    input_row_count: int | None = None
    semantic_mapping_categories: int = 0
    semantic_mapping_by_status: dict[str, int] = Field(default_factory=dict)
    normalization_total_records: int = 0
    normalization_by_status: dict[str, int] = Field(default_factory=dict)
    normalization_queue_open: int = 0
    validation_completeness: dict[str, int] = Field(default_factory=dict)
    retraction_active_tombstones: int = 0
    chat_eval_passed: int | None = None
    chat_eval_total: int | None = None
    chat_eval_stale: bool | None = None
    output_table_hashes: dict[str, str | None] = Field(default_factory=dict)


class SubstrateManifestResponse(BaseModel):
    version: str
    headline: str
    resources: list[SubstrateResource]
    relationships: list[SubstrateRelationship]
    audit_events: list[SubstrateAuditEvent] = Field(default_factory=list)
    materialization: MaterializationManifestSummary | None = None


# --- Patients --------------------------------------------------------------


class PatientRecordResponse(BaseModel):
    """Slim patient identity card. Full rows reachable via /patients/{id}/survey."""

    user_id: int
    gender: str
    current_age: int
    total_treatments: int
    active_treatments: int
    current_medication: str | None = None
    current_dosage: str | None = None
    tenure_days: int | None = None
    latest_bmi: float | None = None
    earliest_bmi: float | None = None
    bmi_change: float | None = None


# --- Chat (Phase 6 — hybrid SQL agent with template artifacts) ------------
#
# The agent returns a small, validated artifact shape rather than letting
# Claude improvise UI. Four template families cover every analytical
# question we ship; anything that does not fit degrades to `table`:
#
#   cohort_trend   — KPIs + chart (1..n series) + supporting table
#   alerts_table   — KPIs + a problem table (undocumented switches, gaps)
#   table          — KPIs optional + a raw table (generic fallback)
#   fhir_bundle    — FHIR R4 Bundle JSON (patient export)
#
# `trace` is mandatory and populated on every response. Today the frontend
# only surfaces it in dev tools; Phase 7 Workbench will lift it into the
# first-class provenance surface. Adding it from day one avoids a
# contract migration later.


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


# ---- Shared artifact primitives ------------------------------------------


DeltaDirection = Literal["up", "down", "neutral"]


class Kpi(BaseModel):
    label: str
    value: str
    delta: str | None = None
    delta_direction: DeltaDirection | None = None


class ChartSeries(BaseModel):
    name: str
    points: list[float]


class Chart(BaseModel):
    title: str
    subtitle: str | None = None
    x_labels: list[str] = Field(
        ...,
        description="Human-readable X-axis tick labels; length matches each series.",
    )
    y_label: str | None = None
    series: list[ChartSeries]


class TableColumn(BaseModel):
    key: str = Field(..., description="Row key for this column's value.")
    label: str
    align: Literal["left", "right"] | None = None
    emphasis: bool = False


class TableData(BaseModel):
    columns: list[TableColumn]
    rows: list[dict[str, Any]]


# ---- Payloads per artifact kind ------------------------------------------


class CohortTrendPayload(BaseModel):
    """KPI strip + one or more trend lines + a supporting table.

    Works for single-cohort trajectories and 2-3 series comparisons. The
    number of series dictates single vs compare visually; payload shape is
    identical.
    """

    kpis: list[Kpi]
    chart: Chart
    table: TableData


class AlertsTablePayload(BaseModel):
    kpis: list[Kpi]
    table: TableData


class TablePayload(BaseModel):
    """Generic fallback. KPIs optional so truly shapeless results still render."""

    kpis: list[Kpi] | None = None
    table: TableData


class FhirBundlePayload(BaseModel):
    """Subset of the FHIR R4 Bundle resource. Extra keys are passed through."""

    resource_type: Literal["Bundle"] = Field("Bundle", alias="resourceType")
    id: str
    type: str
    timestamp: str
    entry: list[dict[str, Any]]

    model_config = {"populate_by_name": True}


# ---- Patient record artifact ---------------------------------------------
#
# Single-patient deep view. Where cohort_trend answers "what does this
# population do over time?", patient_record answers "what is the full,
# audited clinical story of one person?". The substrate already has typed
# per-patient reads on the repository, so this artifact bypasses the SQL
# handle dance and lets the builder pull directly.


class PatientHeader(BaseModel):
    user_id: int
    label: str = Field(..., description="Display ID, e.g. 'PT-381119'.")
    brand: str | None = None
    gender: str
    current_age: int
    current_medication: str | None = None
    current_dosage: str | None = None
    tenure_days: int | None = None
    status: Literal["active", "inactive"]


class PatientMedicationSegment(BaseModel):
    name: str
    dosage: str | None = None
    started: str
    ended: str | None = Field(
        None,
        description="ISO date the script ended, or null if the medication is ongoing.",
    )


PatientEventTrack = Literal[
    "bmi", "medication", "side_effect", "condition", "quality", "survey", "annotation"
]
PatientEventSeverity = Literal["normal", "info", "warn", "alert"]


class PatientEvent(BaseModel):
    """One dot on the timeline.

    Carries enough provenance to render the audit trail card without a
    second backend round-trip: source field, normalised category, code
    system, and the HITL review status that gated it into the substrate.
    """

    id: str
    track: PatientEventTrack
    timestamp: str
    label: str
    detail: str | None = None
    severity: PatientEventSeverity | None = None
    value: float | None = None
    source_field: str | None = None
    source_category: str | None = None
    code_system: str | None = None
    code: str | None = None
    review_status: ReviewStatus | None = None


class PatientBmiPoint(BaseModel):
    date: str
    value: float


class PatientRecordPayload(BaseModel):
    header: PatientHeader
    kpis: list[Kpi]
    medications: list[PatientMedicationSegment]
    events: list[PatientEvent]
    bmi_series: list[PatientBmiPoint]
    timeline_start: str
    timeline_end: str
    quality_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Severity → count of quality alerts for this patient.",
    )
    fhir_resource_count: int = 0
    source_field_count: int = Field(
        0,
        description="Distinct raw source fields collapsed into this record — "
        "the 'chaos → order' headline metric for the audit panel.",
    )


# ---- Opportunity / screening-candidates artifact -------------------------
#
# Cross-brand candidate list: patients on `source_brand` who could be
# screened for `target_brand` follow-up based on a clinical filter (today:
# BMI threshold) and exclusion of existing target-brand history. The
# UI-facing language is "Screening candidates", never "eligible patients"
# or "leads" — we surface the cohort, the operational decision belongs to
# the customer's clinical / outreach team. No revenue figures appear in
# the payload; the truth layer reports the cohort, the customer values it.


CandidatePriority = Literal["high", "medium", "low"]
TrendDirection = Literal["up", "down", "stable", "unknown"]


class ActivationFilterStep(BaseModel):
    """One step in the funnel from total source cohort to final candidates."""

    label: str
    count: int
    description: str | None = None


class ScreeningCandidate(BaseModel):
    user_id: int
    label: str  # display id, e.g. "PT-381119"
    latest_bmi: float | None = None
    bmi_trend: TrendDirection = "unknown"
    age: int | None = None
    gender: str | None = None
    current_treatment: str | None = None
    current_dosage: str | None = None
    tenure_days: int | None = None
    days_since_activity: int | None = None
    reason_summary: str
    priority: CandidatePriority = "medium"


class OpportunityListPayload(BaseModel):
    headline: str
    methodology: str
    activation_path: list[ActivationFilterStep]
    kpis: list[Kpi]
    candidates: list[ScreeningCandidate]
    total_candidates: int = Field(
        ...,
        description="True total candidate count (may exceed the rendered list).",
    )
    source_brand: str
    target_brand: str
    bmi_threshold: float
    activity_window_days: int


# ---- Artifact discriminated union -----------------------------------------


class CohortTrendArtifact(BaseModel):
    kind: Literal["cohort_trend"] = "cohort_trend"
    id: str
    title: str
    subtitle: str
    payload: CohortTrendPayload


class AlertsTableArtifact(BaseModel):
    kind: Literal["alerts_table"] = "alerts_table"
    id: str
    title: str
    subtitle: str
    payload: AlertsTablePayload


class TableArtifact(BaseModel):
    kind: Literal["table"] = "table"
    id: str
    title: str
    subtitle: str
    payload: TablePayload


class FhirBundleArtifact(BaseModel):
    kind: Literal["fhir_bundle"] = "fhir_bundle"
    id: str
    title: str
    subtitle: str
    payload: FhirBundlePayload


class PatientRecordArtifact(BaseModel):
    kind: Literal["patient_record"] = "patient_record"
    id: str
    title: str
    subtitle: str
    payload: PatientRecordPayload


class OpportunityListArtifact(BaseModel):
    kind: Literal["opportunity_list"] = "opportunity_list"
    id: str
    title: str
    subtitle: str
    payload: OpportunityListPayload


ChatArtifact = (
    CohortTrendArtifact
    | AlertsTableArtifact
    | TableArtifact
    | FhirBundleArtifact
    | PatientRecordArtifact
    | OpportunityListArtifact
)

ArtifactKind = Literal[
    "cohort_trend",
    "alerts_table",
    "table",
    "fhir_bundle",
    "patient_record",
    "opportunity_list",
]


# ---- Trace & response -----------------------------------------------------


class ChatTrace(BaseModel):
    """Provenance of one chat answer — what the agent did, honestly reported.

    Workbench (Phase 7) will mine this for recipe extraction; we ship it
    early so no legacy traces exist without it.
    """

    intent: str = Field(..., description="Classified intent key, or 'unclassified'.")
    recipe: str | None = Field(
        None,
        description="Name of the deterministic recipe that handled this, if any.",
    )
    agent_mode: Literal["v1", "v2"] | None = Field(
        None,
        description="Which `/chat` runtime handled the request.",
    )
    sql: list[str] = Field(default_factory=list)
    row_counts: list[int] = Field(default_factory=list)
    artifact_kind: ArtifactKind | None = None
    tool_log: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-tool execution trace, for future Workbench provenance.",
    )


class ChatResponse(BaseModel):
    """Single-shot chat response. Phase 6: request → thinking → artifact, done.

    `steps` are synthetic — derived from which tools/queries the agent ran,
    not streamed tokens. The frontend paces them through its Thinking panel
    for Perplexity-style reveal.
    """

    steps: list[str]
    reply: str
    artifact: ChatArtifact | None = None
    trace: ChatTrace


# --- Meta ------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    artifacts_loaded: bool
    patients: int
    categories: int
    mapping_entries: int
