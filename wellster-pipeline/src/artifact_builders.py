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
    PatientBmiPoint,
    PatientEvent,
    PatientHeader,
    PatientMedicationSegment,
    PatientRecordArtifact,
    PatientRecordPayload,
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


def build_patient_record(
    *,
    repo: Any,  # UnifiedDataRepository — typed loosely to avoid import cycle
    user_id: int,
    title: str,
    subtitle: str,
    artifact_id: str | None = None,
) -> PatientRecordArtifact:
    """Assemble the multi-track patient timeline artifact.

    Pulls every per-patient feed off the repository (BMI, medications,
    quality flags, survey rows, mapping table) and projects them onto a
    single chronological event list with provenance attached. The
    frontend renders that list as a swim-lane timeline.

    Each event carries enough metadata to drive the audit-trail card
    without a second backend call: the raw `surrogate_key` (or
    derived equivalent), the normalised category, the medical code, and
    the HITL review status that gated the category into the substrate.
    """
    record = repo.patient(user_id)
    if record is None:
        raise ValueError(f"Patient {user_id} not found in substrate")

    bmi_df = repo.bmi_for_patient(user_id)
    meds_df = repo.medications_for_patient(user_id)
    quality_df = repo.quality_for_patient(user_id)
    survey_df = repo.survey_for_patient(user_id)

    # mapping → review_status per clinical_category, plus first medical code
    category_review = _category_review_index(repo)
    category_codes = _category_codes_index(repo)

    brand = _first_brand(survey_df)
    # Treatment status — clinically, "active" means the patient is still
    # receiving prescriptions. Wellster's CRM-level `active_treatments`
    # flag can be 0 even when the latest medication is ongoing (because
    # their CRM closes treatment records on different criteria). Use
    # whichever signal says the patient is active: CRM flag OR any
    # ongoing medication segment.
    has_ongoing_med = (
        "ended" in meds_df.columns
        and meds_df["ended"].isna().any()
    )
    is_active = (
        (record.active_treatments and record.active_treatments > 0)
        or bool(has_ongoing_med)
    )
    status: Literal["active", "inactive"] = "active" if is_active else "inactive"
    header = PatientHeader(
        user_id=record.user_id,
        label=f"PT-{record.user_id}",
        brand=brand,
        gender=record.gender,
        current_age=record.current_age,
        current_medication=record.current_medication,
        current_dosage=record.current_dosage,
        tenure_days=record.tenure_days,
        status=status,
    )

    # ---- Events ------------------------------------------------------
    events: list[PatientEvent] = []
    bmi_series: list[PatientBmiPoint] = []

    for idx, row in bmi_df.iterrows():
        ts = _iso(row.get("date"))
        if ts is None:
            continue
        bmi_value = _safe_float(row.get("bmi"))
        if bmi_value is None:
            continue
        bmi_series.append(PatientBmiPoint(date=ts, value=bmi_value))
        weight = _safe_float(row.get("weight_kg"))
        height = _safe_float(row.get("height_cm"))
        detail_bits: list[str] = []
        if weight is not None:
            detail_bits.append(f"{weight:.1f} kg")
        if height is not None:
            detail_bits.append(f"{height:.0f} cm")
        events.append(
            PatientEvent(
                id=f"bmi-{idx}",
                track="bmi",
                timestamp=ts,
                label=f"BMI {bmi_value:.2f}",
                detail=" · ".join(detail_bits) or None,
                value=bmi_value,
                source_field=str(row.get("data_quality_flag") or "BMI_DERIVED"),
                source_category="BMI_MEASUREMENT",
                code_system="LOINC",
                code="39156-5",
                review_status=category_review.get("BMI_MEASUREMENT"),
            )
        )

    medications: list[PatientMedicationSegment] = []
    for idx, row in meds_df.iterrows():
        started_iso = _iso(row.get("started"))
        if started_iso is None:
            continue
        ended_iso = _iso(row.get("ended"))
        product = str(row.get("product") or "Medication")
        dosage = row.get("dosage")
        dosage_str = None if pd.isna(dosage) else str(dosage)
        medications.append(
            PatientMedicationSegment(
                name=product,
                dosage=dosage_str,
                started=started_iso,
                ended=ended_iso,
            )
        )
        # MEDICATION_HISTORY is a derived table, not a discovered category;
        # CURRENT_MEDICATIONS is the closest registered mapping with codes.
        rx_code, rx_system = category_codes.get(
            "CURRENT_MEDICATIONS", category_codes.get("MEDICATION_HISTORY", (None, None))
        )
        med_review = category_review.get(
            "CURRENT_MEDICATIONS", category_review.get("MEDICATION_HISTORY", "approved")
        )
        label = f"{product}{' · ' + dosage_str if dosage_str else ''}"
        detail = "Rx renewal" if str(row.get("order_type") or "").upper() == "SP" else None
        events.append(
            PatientEvent(
                id=f"med-{idx}",
                track="medication",
                timestamp=started_iso,
                label=label,
                detail=detail,
                source_field=str(row.get("order_type") or "MEDICATION_HISTORY"),
                source_category="MEDICATION_HISTORY",
                code_system=rx_system or "RxNorm",
                code=rx_code,
                review_status=med_review,
            )
        )

    # Side effects + survey-driven events. We keep this surface narrow:
    # SIDE_EFFECT_REPORT becomes a side_effect track, MEDICAL_HISTORY_*
    # and BLOOD_PRESSURE_* become condition track, the rest is omitted to
    # avoid drowning the timeline in consent-form noise.
    survey_track_map = {
        "SIDE_EFFECT_REPORT": ("side_effect", "warn"),
        "MEDICAL_HISTORY_AND_CONDITIONS": ("condition", "info"),
        "BLOOD_PRESSURE_AND_CARDIOVASCULAR": ("condition", "info"),
        "WEIGHT_LOSS_PROGRESS_AND_DOSING": ("survey", "info"),
        "REORDER_AND_FOLLOW_UP_STATUS": ("survey", "info"),
    }
    for idx, row in survey_df.iterrows():
        category = str(row.get("clinical_category") or "")
        spec = survey_track_map.get(category)
        if spec is None:
            continue
        track_name, severity = spec
        ts = _iso(row.get("created_at"))
        if ts is None:
            continue
        question = str(row.get("question_de") or row.get("question_en") or "").strip()
        answer = str(row.get("answer_de") or row.get("answer_en") or "").strip()
        if not answer:
            continue
        # Filter out negative findings so the timeline shows real signals,
        # not "patient confirmed they have no diabetes" noise. Applied to
        # side_effect AND condition tracks because both are dominated by
        # boilerplate "none of the above" answers in self-report surveys.
        if track_name in {"side_effect", "condition"}:
            lowered = answer.lower().strip()
            negative_phrases = (
                "keine nebenwirkung",
                "nichts davon",
                "keine der genannten",
                "keiner der genannten",
                "keines der genannten",
                "nicht zutreffend",
                "no side effect",
                "none of the above",
            )
            if (
                lowered in {"nein", "no", "none", "n/a"}
                or any(p in lowered for p in negative_phrases)
            ):
                continue
        code, system = category_codes.get(category, (None, None))
        events.append(
            PatientEvent(
                id=f"survey-{idx}",
                track=track_name,  # type: ignore[arg-type]
                timestamp=ts,
                label=answer[:80],
                detail=question[:120] if question else None,
                severity=severity,  # type: ignore[arg-type]
                source_field=str(row.get("surrogate_key") or ""),
                source_category=category,
                code_system=system,
                code=code,
                review_status=category_review.get(category),
            )
        )

    for idx, row in quality_df.iterrows():
        # Quality alerts have no native timestamp — pin them to the
        # patient's latest activity so they still appear on the right
        # edge of the timeline rather than getting silently dropped.
        anchor_ts = _iso(record.latest_activity_date)
        if anchor_ts is None and bmi_series:
            anchor_ts = bmi_series[-1].date
        if anchor_ts is None:
            continue
        severity_raw = str(row.get("severity") or "info").lower()
        severity = "alert" if severity_raw == "error" else "warn" if severity_raw == "warning" else "info"
        events.append(
            PatientEvent(
                id=f"qa-{idx}",
                track="quality",
                timestamp=anchor_ts,
                label=str(row.get("check_type") or "quality flag"),
                detail=str(row.get("description") or row.get("details") or "")[:160] or None,
                severity=severity,  # type: ignore[arg-type]
                source_field=str(row.get("check_type") or "quality_report"),
                source_category="QUALITY_FLAG",
                review_status="approved",
            )
        )

    events.sort(key=lambda e: e.timestamp)

    timeline_start = (
        events[0].timestamp if events else _iso(record.first_order_date) or ""
    )
    timeline_end = (
        events[-1].timestamp if events else _iso(record.latest_activity_date) or ""
    )

    quality_summary: dict[str, int] = {}
    if not quality_df.empty and "severity" in quality_df.columns:
        for sev, count in quality_df["severity"].astype(str).str.lower().value_counts().items():
            quality_summary[str(sev)] = int(count)

    distinct_source_fields = (
        survey_df["surrogate_key"].nunique() if "surrogate_key" in survey_df.columns else 0
    )

    kpis: list[Kpi] = [
        Kpi(
            label="Tenure",
            value=f"{record.tenure_days} d" if record.tenure_days is not None else "—",
        ),
    ]
    if record.bmi_change is not None:
        delta_dir = "down" if record.bmi_change < 0 else "up"
        kpis.append(
            Kpi(
                label="BMI delta",
                value=f"{record.bmi_change:+.2f}",
                delta=f"{record.earliest_bmi:.1f} → {record.latest_bmi:.1f}"
                if record.earliest_bmi is not None and record.latest_bmi is not None
                else None,
                delta_direction=delta_dir,  # type: ignore[arg-type]
            )
        )
    else:
        kpis.append(Kpi(label="BMI delta", value="—"))
    kpis.append(
        Kpi(
            label="Treatments",
            value=f"{record.active_treatments}/{record.total_treatments}",
        )
    )
    kpis.append(Kpi(label="Events", value=f"{len(events):,}"))

    payload = PatientRecordPayload(
        header=header,
        kpis=kpis,
        medications=medications,
        events=events,
        bmi_series=bmi_series,
        timeline_start=timeline_start,
        timeline_end=timeline_end,
        quality_summary=quality_summary,
        fhir_resource_count=len(events) + len(medications) + (1 if record else 0),
        source_field_count=int(distinct_source_fields),
    )

    return PatientRecordArtifact(
        id=artifact_id or _artifact_id("patient"),
        title=title,
        subtitle=subtitle,
        payload=payload,
    )


# ---- Patient-record helpers ----------------------------------------------


def _load_semantic_mapping() -> dict[str, dict[str, Any]]:
    """Read semantic_mapping.json from the active OUTPUT_DIR.

    Cached on the function object so we only hit disk once per process.
    The mapping file is the authoritative source for review_status and
    medical codes per clinical_category — it is what the /mapping API
    serves and what the HITL flow writes to.
    """
    cached = getattr(_load_semantic_mapping, "_cache", None)
    if cached is not None:
        return cached
    try:
        import json
        import sys
        from pathlib import Path

        # The builder runs inside FastAPI process, where config has
        # already been imported. Re-import lazily to avoid module-level
        # coupling and keep this helper testable in isolation.
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import config  # type: ignore[import-not-found]

        path = Path(config.OUTPUT_DIR) / "semantic_mapping.json"
        if not path.exists():
            cached = {}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached = data if isinstance(data, dict) else {}
    except Exception:
        cached = {}
    setattr(_load_semantic_mapping, "_cache", cached)
    return cached


def _category_review_index(repo: Any) -> dict[str, str]:
    """Map clinical_category → its current review_status from semantic mapping."""
    mapping = _load_semantic_mapping()
    return {
        str(category): str(entry.get("review_status") or "pending")
        for category, entry in mapping.items()
        if isinstance(entry, dict)
    }


def _category_codes_index(repo: Any) -> dict[str, tuple[str | None, str | None]]:
    """Map clinical_category → (code, short_system) from semantic mapping."""
    mapping = _load_semantic_mapping()
    out: dict[str, tuple[str | None, str | None]] = {}
    for category, entry in mapping.items():
        if not isinstance(entry, dict):
            continue
        codes = entry.get("codes") or []
        if codes:
            first = codes[0] if isinstance(codes[0], dict) else {}
            out[str(category)] = (
                str(first.get("code")) if first.get("code") else None,
                _short_code_system(str(first.get("system") or "")),
            )
        else:
            out[str(category)] = (None, None)
    return out


def _short_code_system(system: str) -> str | None:
    if not system:
        return None
    s = system.lower()
    if "loinc" in s:
        return "LOINC"
    if "snomed" in s:
        return "SNOMED"
    if "icd-10" in s or "icd10" in s:
        return "ICD-10"
    if "rxnorm" in s:
        return "RxNorm"
    if "atc" in s or "whocc" in s:
        return "ATC"
    return system.split("/")[-1] or None


def _first_brand(survey_df: Any) -> str | None:
    if "brand" not in getattr(survey_df, "columns", []):
        return None
    series = survey_df["brand"].dropna()
    if series.empty:
        return None
    return str(series.iloc[0])


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return None
    if ts is None or pd.isna(ts):
        return None
    return ts.isoformat()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
