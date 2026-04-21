"""Deterministic artifact builders — DataFrames in, validated payloads out.

The chat agent picks a *family* (cohort_trend / alerts_table / table /
fhir_bundle) and hands over the data. These builders handle the
mechanical transformation: humanising column names, choosing alignment
from dtype, clipping rows, JSON-safing values, and finally validating
through the Pydantic artifact models.

Validation is the critical bit. If any builder raises ValidationError,
the agent is expected to catch it and fall back to the generic `table`
builder — never ship a broken artifact to the UI.

One tiny convention worth knowing: the default row limit here is 50
rather than the query-service cap of 10_000. The UI tables are meant to
be scanned, not paginated; 50 rows fit on one screen and keep JSON
payloads small.
"""

from __future__ import annotations

import uuid
from typing import Any, Iterable, Literal

import pandas as pd
from pandas.api.types import is_numeric_dtype

from src.api.models import (
    AlertsTableArtifact,
    AlertsTablePayload,
    Chart,
    ChartSeries,
    CohortTrendArtifact,
    CohortTrendPayload,
    FhirBundleArtifact,
    FhirBundlePayload,
    Kpi,
    TableArtifact,
    TableColumn,
    TableData,
    TablePayload,
)


DEFAULT_TABLE_LIMIT = 50


# ---- Conversions ----------------------------------------------------------


def humanise(col: str) -> str:
    """snake_case → Title Case, preserving known acronyms.

    Plain `.title()` would turn 'bmi_w0' into 'Bmi W0'; we uppercase a
    short list of known medical/technical acronyms so the ledger looks
    professional out of the box.
    """
    acronyms = {"bmi", "hba1c", "id", "w0", "w12", "w24", "rx", "fhir", "icd", "loinc"}
    parts = col.split("_")
    return " ".join(p.upper() if p.lower() in acronyms else p.capitalize() for p in parts)


def _jsonable_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return str(value)


def df_to_table(
    df: pd.DataFrame,
    *,
    labels: dict[str, str] | None = None,
    emphasis: Iterable[str] | None = None,
    align_overrides: dict[str, Literal["left", "right"]] | None = None,
    columns: list[str] | None = None,
    limit: int | None = DEFAULT_TABLE_LIMIT,
) -> TableData:
    """Convert a DataFrame to a TableData payload.

    Args:
        columns: Subset + order of columns. Defaults to df.columns.
        labels: Override display label per column (else humanised).
        emphasis: Column keys whose values should render in `--signal-ink`.
        align_overrides: Force alignment per column (else numeric → right).
        limit: Max rows (None for no limit).
    """
    labels = labels or {}
    emphasis_set = set(emphasis or ())
    align_overrides = align_overrides or {}
    cols = list(columns) if columns is not None else [str(c) for c in df.columns]

    col_defs: list[TableColumn] = []
    for c in cols:
        if c not in df.columns:
            continue
        align = align_overrides.get(c) or (
            "right" if is_numeric_dtype(df[c].dtype) else "left"
        )
        col_defs.append(
            TableColumn(
                key=c,
                label=labels.get(c, humanise(c)),
                align=align,
                emphasis=c in emphasis_set,
            )
        )

    view = df[cols] if cols else df
    if limit is not None:
        view = view.head(limit)
    rows: list[dict[str, Any]] = []
    for _, row in view.iterrows():
        rows.append({c: _jsonable_scalar(row[c]) for c in cols if c in df.columns})

    return TableData(columns=col_defs, rows=rows)


def _artifact_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---- Artifact builders ----------------------------------------------------


def build_cohort_trend(
    *,
    title: str,
    subtitle: str,
    kpis: list[Kpi],
    chart_title: str,
    chart_subtitle: str | None,
    x_labels: list[str],
    y_label: str | None,
    series: list[ChartSeries],
    table: TableData,
    artifact_id: str | None = None,
) -> CohortTrendArtifact:
    if not series:
        raise ValueError("cohort_trend requires at least one ChartSeries")
    first_len = len(series[0].points)
    if len(x_labels) != first_len:
        raise ValueError(
            f"x_labels length ({len(x_labels)}) does not match series points "
            f"({first_len})"
        )
    for s in series[1:]:
        if len(s.points) != first_len:
            raise ValueError(
                f"series '{s.name}' has {len(s.points)} points; expected {first_len}"
            )

    return CohortTrendArtifact(
        id=artifact_id or _artifact_id("cohort-trend"),
        title=title,
        subtitle=subtitle,
        payload=CohortTrendPayload(
            kpis=kpis,
            chart=Chart(
                title=chart_title,
                subtitle=chart_subtitle,
                x_labels=x_labels,
                y_label=y_label,
                series=series,
            ),
            table=table,
        ),
    )


def build_alerts_table(
    *,
    title: str,
    subtitle: str,
    kpis: list[Kpi],
    table: TableData,
    artifact_id: str | None = None,
) -> AlertsTableArtifact:
    return AlertsTableArtifact(
        id=artifact_id or _artifact_id("alerts"),
        title=title,
        subtitle=subtitle,
        payload=AlertsTablePayload(kpis=kpis, table=table),
    )


def build_table(
    *,
    title: str,
    subtitle: str,
    table: TableData,
    kpis: list[Kpi] | None = None,
    artifact_id: str | None = None,
) -> TableArtifact:
    return TableArtifact(
        id=artifact_id or _artifact_id("table"),
        title=title,
        subtitle=subtitle,
        payload=TablePayload(kpis=kpis, table=table),
    )


def build_fhir_bundle(
    *,
    title: str,
    subtitle: str,
    bundle: dict[str, Any],
    artifact_id: str | None = None,
) -> FhirBundleArtifact:
    """Wrap an existing FHIR Bundle dict as an artifact.

    The export_fhir_bundle output uses camelCase `resourceType`; the
    Pydantic model accepts that via the populate_by_name alias.
    """
    return FhirBundleArtifact(
        id=artifact_id or _artifact_id("fhir"),
        title=title,
        subtitle=subtitle,
        payload=FhirBundlePayload.model_validate(
            {
                "resourceType": bundle.get("resourceType", "Bundle"),
                "id": bundle.get("id", _artifact_id("bundle")),
                "type": bundle.get("type", "collection"),
                "timestamp": bundle.get("timestamp", ""),
                "entry": bundle.get("entry", []),
            }
        ),
    )


# ---- Degraded-path helpers ------------------------------------------------


def build_degraded_table_from_df(
    *,
    df: pd.DataFrame,
    intent_label: str,
    reason: str,
) -> TableArtifact:
    """Fallback artifact when a richer builder fails.

    We keep the original intent label in the title so users can still read
    what the agent was trying to answer, and put the degradation reason in
    the subtitle — honest about what didn't render.
    """
    return build_table(
        title=intent_label,
        subtitle=f"Table view · {reason}",
        table=df_to_table(df),
    )


def build_empty_table(
    *,
    title: str,
    subtitle: str = "No matching rows",
) -> TableArtifact:
    """Zero-row artifact for queries that return nothing.

    Still an artifact — "nothing matched" is a valid answer and the user
    should see a clear surface rather than the agent silently omitting it.
    """
    return build_table(
        title=title,
        subtitle=subtitle,
        table=TableData(columns=[], rows=[]),
    )
