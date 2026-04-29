"""Meta endpoints: /health, /schema, /categories, /substrate/*."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import config  # type: ignore[import-not-found]

from src.api.deps import AppState, get_query, get_state
from src.api.models import (
    CategoriesResponse,
    ColumnInfo,
    HealthResponse,
    MaterializationManifestSummary,
    SchemaResponse,
    SubstrateAuditEvent,
    SubstrateForeignKey,
    SubstrateManifestResponse,
    SubstrateRelationship,
    SubstrateResource,
)
from src.query_service import DuckDBQueryService

router = APIRouter(tags=["meta"])


# Whitelist for snapshot exports — only data resources whose canonical
# CSV lives in output/. Frontend offers these as "snapshot export"; the
# operational system of record stays at the customer. This is an
# Exit/Interop/Trust signal, not a database-replacement download.
_SNAPSHOT_EXPORTS: dict[str, str] = {
    "patients": "patients.csv",
    "bmi_timeline": "bmi_timeline.csv",
    "medication_history": "medication_history.csv",
    "treatment_episodes": "treatment_episodes.csv",
    "quality_report": "quality_report.csv",
    "survey_unified": "survey_unified.csv",
}


@router.get("/health", response_model=HealthResponse)
def health(state: AppState = Depends(get_state)) -> HealthResponse:
    """Liveness + artifact-readiness signal."""
    if not state.ready or state.repo is None:
        return HealthResponse(
            status="degraded",
            artifacts_loaded=False,
            patients=0,
            categories=0,
            mapping_entries=0,
        )
    mapping = state.read_mapping()
    return HealthResponse(
        status="ok",
        artifacts_loaded=True,
        patients=state.repo.count_patients(),
        categories=len(state.repo.categories()),
        mapping_entries=sum(1 for k in mapping if not k.startswith("__")),
    )


@router.get("/schema", response_model=SchemaResponse)
def schema(query: DuckDBQueryService = Depends(get_query)) -> SchemaResponse:
    """Full table+column map. Chatbot feeds this into its prompt as context."""
    raw = query.schema()
    return SchemaResponse(
        tables={
            table: [ColumnInfo(column=c["column"], type=c["type"]) for c in cols]
            for table, cols in raw.items()
        }
    )


@router.get("/categories", response_model=CategoriesResponse)
def categories(
    query: DuckDBQueryService = Depends(get_query),
) -> CategoriesResponse:
    """Distinct clinical_category values discovered by the AI classifier."""
    cats = query.list_categories()
    return CategoriesResponse(categories=cats, count=len(cats))


@router.get(
    "/v1/substrate/manifest",
    response_model=SubstrateManifestResponse,
)
def substrate_manifest(
    state: AppState = Depends(get_state),
) -> SubstrateManifestResponse:
    """Repository-level manifest for the live clinical substrate.

    This is the API shape behind the `/substrate-ready` repository map:
    concrete resources, row counts, key relationships, and the API hooks
    a downstream consumer can build against. It intentionally reports
    the substrate as a repository, not as a one-off cleaned table.
    """
    if state.repo is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="Pipeline artifacts not loaded. Run `python pipeline.py` first.",
        )

    repo = state.repo
    resources = [
        _resource(
            name="patients",
            label="Patients",
            row_count=len(repo.patients),
            primary_key="user_id",
            sample_fields=[
                "gender",
                "current_age",
                "current_medication",
                "latest_bmi",
            ],
            status="signed",
            api_hooks=["GET /v1/patients", "GET /v1/patients/{id}"],
        ),
        _resource(
            name="bmi_timeline",
            label="BMI Timeline",
            row_count=len(repo.bmi_timeline),
            primary_key="user_id + date",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=["date", "height_cm", "weight_kg", "bmi"],
            status="queryable",
            api_hooks=["GET /v1/observations?type=bmi"],
        ),
        _resource(
            name="medication_history",
            label="Medication History",
            row_count=len(repo.medication_history),
            primary_key="user_id + started",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=["product", "dosage", "started", "ended"],
            status="queryable",
            api_hooks=["GET /v1/patients/{id}/medications"],
        ),
        _resource(
            name="treatment_episodes",
            label="Treatment Episodes",
            row_count=len(repo.episodes),
            primary_key="treatment_id",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=["product", "brand", "start_date", "latest_date"],
            status="queryable",
            api_hooks=["GET /v1/treatments/{id}"],
        ),
        _resource(
            name="quality_report",
            label="Quality Report",
            row_count=len(repo.quality_report),
            primary_key="check_type + user_id",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=["severity", "check_type", "description"],
            status="monitored",
            api_hooks=["GET /v1/quality/flags"],
        ),
        _resource(
            name="survey_unified",
            label="Survey Events (raw)",
            row_count=len(repo.survey),
            primary_key="surrogate_key",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=[
                "clinical_category",
                "answer_canonical",
                "normalization_status",
                "created_at",
            ],
            status="queryable",
            api_hooks=["GET /v1/patients/{id}/events"],
        ),
        _resource(
            name="survey_validated",
            label="Survey Events (validated)",
            row_count=len(repo.survey_validated),
            primary_key="surrogate_key",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=[
                "clinical_category",
                "answer_canonical",
                "normalization_status",
            ],
            status="signed",
            api_hooks=[
                "GET /v1/patients/{id}/events?validated=true",
                "(default for FHIR + analyst + cohort consumers)",
            ],
        ),
        _resource(
            name="semantic_mapping",
            label="Semantic Mapping",
            row_count=_mapping_count(state),
            primary_key="clinical_category",
            sample_fields=[
                "fhir_resource_type",
                "codes",
                "review_status",
            ],
            status="signed",
            api_hooks=["GET /v1/mapping", "PATCH /v1/mapping/{category}"],
        ),
        _resource(
            name="fhir_bundle",
            label="FHIR Bundle",
            row_count=len(repo.patients),
            primary_key="user_id",
            foreign_keys=[("patients", "user_id", "patient identity")],
            sample_fields=["Patient", "Observation", "MedicationStatement"],
            status="exportable",
            api_hooks=["GET /v1/export/{id}/fhir"],
        ),
        _resource(
            name="clinical_annotations",
            label="Clinical Annotations",
            row_count=_annotation_count_safe(),
            primary_key="id",
            foreign_keys=[("patients", "patient_id", "patient identity")],
            sample_fields=["category", "note", "author", "created_at"],
            status="monitored",
            api_hooks=[
                "GET /v1/patients/{id}/annotations",
                "POST /v1/patients/{id}/annotations",
            ],
        ),
    ]

    relationships = [
        SubstrateRelationship(
            from_resource=name,
            to_resource="patients",
            key="user_id",
            label="joins by user_id",
        )
        for name in (
            "bmi_timeline",
            "medication_history",
            "treatment_episodes",
            "quality_report",
            "survey_unified",
            "fhir_bundle",
        )
    ]

    return SubstrateManifestResponse(
        version="v1",
        headline=(
            "Approval does not create a report. "
            "It materializes a clinical repository."
        ),
        resources=resources,
        relationships=relationships,
        audit_events=[_audit_event(state)],
        materialization=_materialization_summary(),
    )


def _materialization_summary() -> MaterializationManifestSummary | None:
    """Read the materialization manifest from disk, project to API shape.

    Returns None if no manifest has been generated yet — that's a valid
    state during very early bootstrap and shouldn't 500 the substrate
    endpoint.
    """
    try:
        from src.materialization_manifest import load_manifest

        manifest = load_manifest()
    except Exception:
        return None
    if not manifest:
        return None
    sm = manifest.get("semantic_mapping") or {}
    nr = manifest.get("normalization") or {}
    retractions = manifest.get("retractions") or {}
    chat_eval = (manifest.get("evals") or {}).get("chat_agent") or {}
    output_tables = manifest.get("output_tables") or {}
    validated_table = output_tables.get("survey_validated") or {}
    return MaterializationManifestSummary(
        run_id=str(manifest.get("run_id") or "unknown"),
        generated_at=str(manifest.get("generated_at") or ""),
        git_commit=manifest.get("git_commit"),
        input_row_count=(manifest.get("input") or {}).get("row_count"),
        semantic_mapping_categories=int(sm.get("categories", 0)),
        semantic_mapping_by_status=dict(sm.get("by_status") or {}),
        normalization_total_records=int(
            (nr.get("registry_stats") or {}).get("total_records", 0)
        ),
        normalization_by_status={
            k.replace("by_status_", ""): v
            for k, v in (nr.get("registry_stats") or {}).items()
            if k.startswith("by_status_")
        },
        normalization_queue_open=int(
            (nr.get("queue_stats") or {}).get("open", 0)
        ),
        validation_completeness=dict(
            validated_table.get("validation_completeness") or {}
        ),
        retraction_active_tombstones=int(
            retractions.get("active_tombstones", 0) or 0
        ),
        chat_eval_passed=chat_eval.get("passed"),
        chat_eval_total=chat_eval.get("total"),
        chat_eval_stale=chat_eval.get("stale"),
        output_table_hashes={
            name: info.get("file_hash")
            for name, info in output_tables.items()
            if isinstance(info, dict)
        },
    )


def _annotation_count_safe() -> int:
    """Count clinical annotations on disk; never raise into the manifest path."""
    try:
        from src.clinical_annotations import annotation_count

        return annotation_count()
    except Exception:
        return 0


def _audit_event_from_annotation() -> SubstrateAuditEvent | None:
    """Surface the most recent clinician annotation as the audit beat.

    Returns None if no annotations exist (in which case the manifest
    falls back to the mapping-sign-off audit). When an annotation does
    exist, it always wins — clinician write-back is the strongest
    living-substrate evidence we can present.
    """
    try:
        from src.clinical_annotations import latest_annotation

        latest = latest_annotation()
    except Exception:
        return None
    if not latest:
        return None
    author = str(latest.get("author") or "Clinician")
    patient_id = latest.get("patient_id")
    note = str(latest.get("note") or "")
    note_short = note if len(note) <= 90 else note[:87].rstrip() + "..."
    label = f"{author} added clinical note · PT-{patient_id}"
    detail = note_short or "Clinician contributed context to the substrate"
    return SubstrateAuditEvent(label=label, detail=detail, status="approved")


def _resource(
    *,
    name: str,
    label: str,
    row_count: int,
    primary_key: str,
    sample_fields: list[str],
    status: str,
    api_hooks: list[str],
    foreign_keys: list[tuple[str, str, str]] | None = None,
) -> SubstrateResource:
    return SubstrateResource(
        name=name,
        label=label,
        row_count=row_count,
        primary_key=primary_key,
        foreign_keys=[
            SubstrateForeignKey(target_resource=target, key=key, label=label_)
            for target, key, label_ in (foreign_keys or [])
        ],
        sample_fields=sample_fields,
        status=status,  # type: ignore[arg-type]
        api_hooks=api_hooks,
    )


def _mapping_count(state: AppState) -> int:
    mapping = state.read_mapping()
    return sum(1 for key in mapping if not key.startswith("__"))


def _audit_event(state: AppState) -> SubstrateAuditEvent:
    # Living-substrate beat first: if any clinician has added an
    # annotation, that is by definition the freshest provenance event.
    # The audit strip surfaces it so the page reflects substrate motion
    # rather than the static mapping sign-off.
    annotation_event = _audit_event_from_annotation()
    if annotation_event is not None:
        return annotation_event

    mapping = state.read_mapping()
    preferred = "BMI_MEASUREMENT"
    if preferred in mapping and isinstance(mapping[preferred], dict):
        category = preferred
        entry = mapping[preferred]
    else:
        category, entry = next(
            (
                (key, value)
                for key, value in mapping.items()
                if not key.startswith("__") and isinstance(value, dict)
            ),
            ("semantic_mapping", {}),
        )
    codes = entry.get("codes") if isinstance(entry, dict) else []
    first_code = codes[0] if codes and isinstance(codes[0], dict) else {}
    code_label = "standard code"
    if first_code.get("code"):
        system = _short_code_system(str(first_code.get("system") or ""))
        code_label = f"{system} {first_code['code']}"
    status = str(entry.get("review_status") or "approved")
    if status not in {"pending", "approved", "overridden", "rejected"}:
        status = "approved"
    return SubstrateAuditEvent(
        label=f"{category} signed into substrate",
        detail=f"{code_label} attached · now queryable and FHIR-ready",
        status=status,  # type: ignore[arg-type]
    )


def _short_code_system(system: str) -> str:
    lowered = system.lower()
    if "loinc" in lowered:
        return "LOINC"
    if "snomed" in lowered:
        return "SNOMED"
    if "rxnorm" in lowered:
        return "RxNorm"
    if "icd-10" in lowered or "icd10" in lowered:
        return "ICD-10"
    if "atc" in lowered:
        return "ATC"
    return system.split("/")[-1] or "code"


@router.get("/v1/substrate/resources/{name}/export.csv")
def substrate_resource_export(
    name: str,
    state: AppState = Depends(get_state),
) -> FileResponse:
    """Snapshot CSV export for one substrate resource.

    Positioning note: this is a *snapshot export*, not a database
    download. The operational system of record stays at the customer;
    UniQ continuously materialises the clinical truth layer beside it.
    The export is the trust / interop / audit signal — proof you can
    take the substrate out, plug it into a BI tool, hand it to a
    compliance officer, or feed it to a partner system.

    semantic_mapping is exposed via /v1/mapping (JSON) and fhir_bundle
    via /v1/export/{user_id}/fhir (per-patient). Those resources are
    intentionally absent from this whitelist.
    """
    if state.repo is None:
        raise HTTPException(
            status_code=503,
            detail="Pipeline artifacts not loaded.",
        )
    filename = _SNAPSHOT_EXPORTS.get(name)
    if filename is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No snapshot export for resource {name!r}. "
                "semantic_mapping is served via /v1/mapping (JSON); "
                "fhir_bundle via /v1/export/{user_id}/fhir (per-patient)."
            ),
        )
    path = Path(config.OUTPUT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Snapshot file {filename} not found in output directory.",
        )
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"uniq-{name}-snapshot.csv",
    )
