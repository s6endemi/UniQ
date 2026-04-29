"""Patient endpoints — typed patient-record lookups, per-patient FHIR export, clinical annotations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.deps import get_repo
from src.api.models import (
    ClinicalAnnotation,
    ClinicalAnnotationCreate,
    PatientRecordResponse,
)
from src.clinical_annotations import (
    annotations_for_patient,
    append_annotation,
)
from src.datastore import PatientRecord, UnifiedDataRepository
from src.export_fhir import export_fhir_bundle, validate_fhir_bundle
from src.retractions import is_patient_retracted

router = APIRouter(tags=["patients"])


def _to_model(p: PatientRecord) -> PatientRecordResponse:
    return PatientRecordResponse(
        user_id=p.user_id,
        gender=p.gender,
        current_age=p.current_age,
        total_treatments=p.total_treatments,
        active_treatments=p.active_treatments,
        current_medication=p.current_medication,
        current_dosage=p.current_dosage,
        tenure_days=p.tenure_days,
        latest_bmi=p.latest_bmi,
        earliest_bmi=p.earliest_bmi,
        bmi_change=p.bmi_change,
    )


@router.get("/patients/{user_id}", response_model=PatientRecordResponse)
def get_patient(
    user_id: int,
    repo: UnifiedDataRepository = Depends(get_repo),
) -> PatientRecordResponse:
    if is_patient_retracted(user_id):
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")
    record = repo.patient(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")
    return _to_model(record)


@router.get("/export/{user_id}/fhir")
@router.get("/v1/export/{user_id}/fhir")
def export_fhir(
    user_id: int,
    repo: UnifiedDataRepository = Depends(get_repo),
) -> dict:
    """FHIR R4 Bundle with every resource for one patient.

    Uses the legacy hardcoded code tables in `medical_codes.py` for now —
    that path still works for obesity data. A later phase swaps it for
    `semantic_mapping.json` once enough entries have been reviewed.
    """
    if is_patient_retracted(user_id) or repo.patient(user_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")

    patients_df = repo.patients[repo.patients["user_id"] == user_id]
    bmi_df = repo.bmi_timeline[repo.bmi_timeline["user_id"] == user_id]
    med_df = repo.medication_history[repo.medication_history["user_id"] == user_id]
    # Validated layer for FHIR export: only categories with clinician-
    # signed mappings make it into the bundle. Raw audit data stays
    # accessible via the substrate API but does not ship in FHIR.
    survey_df = repo.survey_validated_for_patient(user_id)

    bundle = export_fhir_bundle(patients_df, bmi_df, med_df, survey_df)
    errors = validate_fhir_bundle(bundle)
    if errors:
        raise HTTPException(
            status_code=500,
            detail={"message": "Generated FHIR bundle failed smoke validation", "errors": errors},
        )
    return bundle


# ---- Clinical annotations -------------------------------------------------
#
# First write-back surface on the substrate. Every other resource is
# derived from raw upstream data; annotations come from the clinician
# directly. They convert UniQ from a one-shot snapshot into operational
# memory — Martin's "Living Substrate" requirement.


@router.get(
    "/v1/patients/{user_id}/annotations",
    response_model=list[ClinicalAnnotation],
)
def list_patient_annotations(
    user_id: int,
    repo: UnifiedDataRepository = Depends(get_repo),
) -> list[ClinicalAnnotation]:
    if is_patient_retracted(user_id) or repo.patient(user_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")
    raw = annotations_for_patient(user_id)
    return [ClinicalAnnotation.model_validate(a) for a in raw]


@router.post(
    "/v1/patients/{user_id}/annotations",
    response_model=ClinicalAnnotation,
    status_code=201,
)
def create_patient_annotation(
    user_id: int,
    payload: ClinicalAnnotationCreate,
    repo: UnifiedDataRepository = Depends(get_repo),
    x_uniq_reviewer: str | None = Header(None),
    x_uniq_role: str | None = Header(None),
) -> ClinicalAnnotation:
    if is_patient_retracted(user_id) or repo.patient(user_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")
    # Reviewer headers override the demo author defaults baked into
    # `clinical_annotations.append_annotation`. Empty / missing headers
    # fall back to the demo author so the existing UI flow keeps working
    # without auth wiring.
    author = (
        x_uniq_reviewer.strip()
        if x_uniq_reviewer and x_uniq_reviewer.strip()
        else None
    )
    role = (
        x_uniq_role.strip()
        if x_uniq_role and x_uniq_role.strip()
        else None
    )
    record = append_annotation(
        patient_id=user_id,
        note=payload.note,
        event_id=payload.event_id,
        category=payload.category,
        author=author,
        role=role,
    )
    return ClinicalAnnotation.model_validate(record)
