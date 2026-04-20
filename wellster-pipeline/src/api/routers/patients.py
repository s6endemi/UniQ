"""Patient endpoints — typed patient-record lookups and per-patient FHIR export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_repo
from src.api.models import PatientRecordResponse
from src.datastore import PatientRecord, UnifiedDataRepository
from src.export_fhir import export_fhir_bundle

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
    record = repo.patient(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")
    return _to_model(record)


@router.get("/export/{user_id}/fhir")
def export_fhir(
    user_id: int,
    repo: UnifiedDataRepository = Depends(get_repo),
) -> dict:
    """FHIR R4 Bundle with every resource for one patient.

    Uses the legacy hardcoded code tables in `medical_codes.py` for now —
    that path still works for obesity data. A later phase swaps it for
    `semantic_mapping.json` once enough entries have been reviewed.
    """
    if repo.patient(user_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id {user_id}")

    patients_df = repo.patients[repo.patients["user_id"] == user_id]
    bmi_df = repo.bmi_timeline[repo.bmi_timeline["user_id"] == user_id]
    med_df = repo.medication_history[repo.medication_history["user_id"] == user_id]
    survey_df = repo.survey[repo.survey["user_id"] == user_id]

    bundle = export_fhir_bundle(patients_df, bmi_df, med_df, survey_df)
    return bundle
