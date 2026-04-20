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


# --- Chat (Phase 6 — stubbed for now) --------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    sql: str | None = None  # populated when the agent ran a query
    rows: list[dict[str, Any]] | None = None
    chart_spec: dict[str, Any] | None = None
    truncated: bool = False


# --- Meta ------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    artifacts_loaded: bool
    patients: int
    categories: int
    mapping_entries: int
