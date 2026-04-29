"""Internal models for the unified Phase 6 v2 chat agent.

These are *not* API response models. They validate Anthropic tool inputs for
the v2 agent so prompt/output contracts live in one place and the runtime
does not have to hand-parse arbitrary dicts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


HANDLE_PATTERN = r"^[a-z][a-z0-9_]{1,40}$"


class ExecuteSqlInput(BaseModel):
    handle: str = Field(
        ...,
        pattern=HANDLE_PATTERN,
        description="Short snake_case result handle for later present_* tools.",
    )
    sql: str = Field(
        ...,
        min_length=1,
        description="A single read-only SELECT / WITH statement.",
    )


class SampleRowsInput(BaseModel):
    table: str
    n: int = Field(5, ge=1, le=50)


class SeriesSpec(BaseModel):
    name: str = Field(..., min_length=1)
    y_column: str = Field(..., min_length=1)


class PresentCohortTrendInput(BaseModel):
    trend_handle: str = Field(..., pattern=HANDLE_PATTERN)
    table_handle: str | None = Field(None, pattern=HANDLE_PATTERN)
    x_column: str = Field(..., min_length=1)
    series: list[SeriesSpec] = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    chart_title: str = Field(..., min_length=1)
    chart_subtitle: str | None = None
    y_label: str | None = None
    reply_text: str = Field(..., min_length=1)


class PresentAlertsTableInput(BaseModel):
    table_handle: str = Field(..., pattern=HANDLE_PATTERN)
    title: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    severity_column: str = Field("severity", min_length=1)
    reply_text: str = Field(..., min_length=1)
    total_count: int | None = Field(
        None,
        description=(
            "True total issue count when the underlying table_handle was "
            "LIMITed. Without this the Total Issues KPI defaults to the "
            "rendered row count which under-reports the substrate."
        ),
    )


class PresentFhirBundleInput(BaseModel):
    user_id: int
    title: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    reply_text: str = Field(..., min_length=1)


class PresentTableInput(BaseModel):
    table_handle: str = Field(..., pattern=HANDLE_PATTERN)
    title: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    reply_text: str = Field(..., min_length=1)


class PresentPatientRecordInput(BaseModel):
    user_id: int = Field(..., description="Wellster numeric user_id, e.g. 381119.")
    title: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    reply_text: str = Field(..., min_length=1)


WellsterBrand = Literal["spring", "golighter", "mysummer"]


class PresentOpportunityListInput(BaseModel):
    """Cross-brand screening-candidate list.

    Backend executes a fixed, deterministic Pandas filter — no LLM-
    generated SQL. The agent only specifies cohort scope and clinical
    threshold; everything else is parameter-locked at the contract level.
    """

    title: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    reply_text: str = Field(..., min_length=1)
    source_brand: WellsterBrand = Field(
        "spring",
        description="Brand the candidate cohort currently belongs to.",
    )
    target_brand: WellsterBrand = Field(
        "golighter",
        description="Brand we are screening candidates FOR (excluded if patient already has history with it).",
    )
    bmi_threshold: float = Field(
        27.0,
        ge=15.0,
        le=60.0,
        description="Minimum BMI to qualify as a screening candidate.",
    )
    activity_window_days: int = Field(
        180,
        ge=30,
        le=730,
        description="Maximum days since last patient activity to include.",
    )
    limit: int = Field(
        20,
        ge=5,
        le=100,
        description="Max candidates rendered in the table (full count still surfaced via total_candidates).",
    )


TerminalToolName = Literal[
    "present_cohort_trend",
    "present_alerts_table",
    "present_fhir_bundle",
    "present_table",
    "present_patient_record",
    "present_opportunity_list",
]
