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
    "bmi", "medication", "side_effect", "condition", "quality", "survey"
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


ChatArtifact = (
    CohortTrendArtifact
    | AlertsTableArtifact
    | TableArtifact
    | FhirBundleArtifact
    | PatientRecordArtifact
)

ArtifactKind = Literal[
    "cohort_trend", "alerts_table", "table", "fhir_bundle", "patient_record"
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
