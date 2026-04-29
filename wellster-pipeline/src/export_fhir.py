"""
FHIR R4 Export — Convert unified tables to HL7 FHIR standard

Generates a FHIR Bundle containing:
  - Patient resources (demographics)
  - Observation resources (BMI measurements, blood pressure)
  - MedicationStatement resources (medication history)
  - QuestionnaireResponse resources (unified survey answers)

This enables interoperability with any EHR system, hospital, or insurance company
that supports FHIR — which is mandated in the US (21st Century Cures Act) and
increasingly adopted in the EU.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


KNOWN_FHIR_RESOURCE_TYPES: frozenset[str] = frozenset({
    "AdverseEvent",
    "AllergyIntolerance",
    "Bundle",
    "Condition",
    "Consent",
    "DocumentReference",
    "Media",
    "MedicationRequest",
    "MedicationStatement",
    "Observation",
    "Patient",
    "QuestionnaireResponse",
})

CONDITION_CATEGORIES: frozenset[str] = frozenset({
    "MEDICAL_HISTORY_AND_CONDITIONS",
    "MEDICAL_CONDITIONS",
    "COMORBIDITY_SCREENING",
})


def _fhir_patient(row: pd.Series) -> dict:
    """Convert a patient row to a FHIR Patient resource."""
    gender_map = {"female": "female", "male": "male"}
    return {
        "resourceType": "Patient",
        "id": f"patient-{int(row['user_id'])}",
        "identifier": [{"system": "urn:wellster:patient", "value": str(int(row["user_id"]))}],
        "gender": gender_map.get(str(row.get("gender", "")).lower(), "unknown"),
        "extension": [
            {
                "url": "urn:wellster:age",
                "valueInteger": int(row["current_age"]),
            }
        ],
    }


def _fhir_bmi_observation(row: pd.Series) -> dict:
    """Convert a BMI measurement to a FHIR Observation resource."""
    obs = {
        "resourceType": "Observation",
        "id": f"bmi-{int(row['user_id'])}-{int(row['treatment_id'])}",
        "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                   "code": "vital-signs", "display": "Vital Signs"}]}],
        "code": {"coding": [{"system": "http://loinc.org", "code": "39156-5", "display": "Body mass index"}],
                 "text": "BMI"},
        "subject": {"reference": f"Patient/patient-{int(row['user_id'])}"},
        "valueQuantity": {"value": round(row["bmi"], 2), "unit": "kg/m2",
                          "system": "http://unitsofmeasure.org", "code": "kg/m2"},
        "component": [
            {"code": {"coding": [{"system": "http://loinc.org", "code": "8302-2", "display": "Body height"}]},
             "valueQuantity": {"value": row["height_cm"], "unit": "cm",
                               "system": "http://unitsofmeasure.org", "code": "cm"}},
            {"code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]},
             "valueQuantity": {"value": row["weight_kg"], "unit": "kg",
                               "system": "http://unitsofmeasure.org", "code": "kg"}},
        ],
    }
    if pd.notna(row.get("date")):
        d = str(row["date"])
        obs["effectiveDateTime"] = d[:10] + "T" + d[11:19] + "Z"
    return obs


def _fhir_condition(user_id: int, canonical: str) -> dict | None:
    """Convert a canonical comorbidity to a FHIR Condition with ICD-10 + SNOMED codes."""
    from src.medical_codes import get_condition_code

    codes = get_condition_code(canonical)
    if not codes:
        return None

    return {
        "resourceType": "Condition",
        "id": f"cond-{user_id}-{canonical.lower()}",
        "subject": {"reference": f"Patient/patient-{user_id}"},
        "code": {
            "coding": [
                {"system": codes["icd10"]["system"], "code": codes["icd10"]["code"],
                 "display": codes["icd10"]["display"]},
                {"system": codes["snomed"]["system"], "code": codes["snomed"]["code"],
                 "display": codes["snomed"]["display"]},
            ],
            "text": codes["icd10"]["display"],
        },
        "clinicalStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                         "code": "active", "display": "Active"}],
        },
    }


def _fhir_adverse_event(user_id: int, canonical: str) -> dict | None:
    """Convert a canonical side effect to a FHIR AdverseEvent with SNOMED codes."""
    from src.medical_codes import get_side_effect_code

    codes = get_side_effect_code(canonical)
    if not codes:
        return None

    return {
        "resourceType": "AdverseEvent",
        "id": f"ae-{user_id}-{canonical.lower()}",
        "subject": {"reference": f"Patient/patient-{user_id}"},
        "event": {
            "coding": [{"system": codes["system"], "code": codes["code"],
                         "display": codes["display"]}],
            "text": codes["display"],
        },
        "seriousness": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/adverse-event-seriousness",
                         "code": "non-serious", "display": "Non-serious"}],
        },
    }


def _fhir_medication(row: pd.Series) -> dict:
    """Convert a medication history row to a FHIR MedicationStatement with RxNorm/ATC codes."""
    from src.medical_codes import get_medication_code

    product = str(row["product"])
    med_concept = {"text": product}

    # Add RxNorm + ATC coding
    codes = get_medication_code(product)
    if codes:
        med_concept["coding"] = [
            {"system": codes["rxnorm"]["system"], "code": codes["rxnorm"]["code"],
             "display": codes["rxnorm"]["display"]},
            {"system": codes["atc"]["system"], "code": codes["atc"]["code"],
             "display": codes["atc"]["display"]},
        ]

    med = {
        "resourceType": "MedicationStatement",
        "id": f"med-{int(row['user_id'])}-{int(row['treatment_id'])}",
        "status": "active" if pd.isna(row.get("ended")) else "completed",
        "subject": {"reference": f"Patient/patient-{int(row['user_id'])}"},
        "medicationCodeableConcept": med_concept,
        "dosage": [{"text": str(row["dosage"]) if pd.notna(row.get("dosage")) else ""}],
    }
    if pd.notna(row.get("started")):
        period = {"start": str(row["started"])[:10] + "T" + str(row["started"])[11:19] + "Z"}
        if pd.notna(row.get("ended")):
            period["end"] = str(row["ended"])[:10] + "T" + str(row["ended"])[11:19] + "Z"
        med["effectivePeriod"] = period
    return med


def export_fhir_bundle(
    patients: pd.DataFrame,
    bmi: pd.DataFrame,
    med_hist: pd.DataFrame,
    survey: pd.DataFrame | None = None,
) -> dict:
    """Build a FHIR R4 Bundle with all unified patient data.

    Includes:
      - Patient resources
      - Observation (BMI with LOINC codes)
      - MedicationStatement (with RxNorm + ATC codes)
      - Condition (comorbidities with ICD-10 + SNOMED CT codes)
      - AdverseEvent (side effects with SNOMED CT codes)
    """
    entries: list[dict] = []

    # Patients
    for _, row in patients.iterrows():
        resource = _fhir_patient(row)
        entries.append({"resource": resource, "fullUrl": f"urn:uuid:{resource['id']}"})

    # BMI observations
    for _, row in bmi.iterrows():
        resource = _fhir_bmi_observation(row)
        entries.append({"resource": resource, "fullUrl": f"urn:uuid:{resource['id']}"})

    # Medications
    for _, row in med_hist.iterrows():
        resource = _fhir_medication(row)
        entries.append({"resource": resource, "fullUrl": f"urn:uuid:{resource['id']}"})

    # Conditions + AdverseEvents from survey canonical answers
    if survey is not None:
        # Use the shared parser so we handle both cases: the column may be a
        # JSON string (fresh off the CSV) or already a Python list (if the
        # caller pre-parsed it via `UnifiedDataRepository`). Doing
        # json.loads(str(list)) silently produces an empty list and drops
        # the row, which is exactly the bug Codex caught for Phase 4.
        from src.datastore import parse_canonical

        seen_conditions: set[str] = set()
        seen_adverse: set[str] = set()

        for _, row in survey.iterrows():
            uid = int(row["user_id"])
            cat = row.get("clinical_category", "")
            canonicals = parse_canonical(row.get("answer_canonical"))
            if not canonicals:
                continue

            for c in canonicals:
                if cat in CONDITION_CATEGORIES:
                    key = f"{uid}-{c}"
                    if key not in seen_conditions and c not in ("NONE", "NO", "YES"):
                        resource = _fhir_condition(uid, c)
                        if resource:
                            entries.append({"resource": resource, "fullUrl": f"urn:uuid:{resource['id']}"})
                            seen_conditions.add(key)

                elif cat == "SIDE_EFFECT_REPORT":
                    key = f"{uid}-{c}"
                    if key not in seen_adverse and c not in ("NONE", "NO_SIDE_EFFECTS", "NO_SEVERE_DISCONTINUATION"):
                        resource = _fhir_adverse_event(uid, c)
                        if resource:
                            entries.append({"resource": resource, "fullUrl": f"urn:uuid:{resource['id']}"})
                            seen_adverse.add(key)

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        "meta": {"source": "UniQ Questionnaire Intelligence Engine"},
        "total": len(entries),
        "entry": entries,
    }
    return bundle


def validate_fhir_bundle(bundle: dict[str, Any]) -> list[str]:
    """Smoke-validate the subset of FHIR R4 we emit.

    This is intentionally not a full HL7 profile validator. It catches the
    failures that matter for the pilot: wrong resource shape, mismatched
    `total`, unknown resourceType typos, missing ids/fullUrls, and broken
    Patient subject references.
    """
    errors: list[str] = []
    if bundle.get("resourceType") != "Bundle":
        errors.append("bundle.resourceType must be Bundle")
    if bundle.get("type") != "collection":
        errors.append("bundle.type must be collection")

    entries = bundle.get("entry")
    if not isinstance(entries, list):
        return errors + ["bundle.entry must be a list"]
    if bundle.get("total") != len(entries):
        errors.append("bundle.total must match len(entry)")

    patient_ids: set[str] = set()
    subject_refs: list[str] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry[{idx}] must be an object")
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            errors.append(f"entry[{idx}].resource must be an object")
            continue
        resource_type = resource.get("resourceType")
        if resource_type not in KNOWN_FHIR_RESOURCE_TYPES:
            errors.append(f"entry[{idx}] has unknown resourceType {resource_type!r}")
        resource_id = resource.get("id")
        if not resource_id:
            errors.append(f"entry[{idx}] resource is missing id")
        if not entry.get("fullUrl"):
            errors.append(f"entry[{idx}] is missing fullUrl")
        if resource_type == "Patient" and resource_id:
            patient_ids.add(str(resource_id))
        subject = resource.get("subject")
        if isinstance(subject, dict) and subject.get("reference"):
            subject_refs.append(str(subject["reference"]))

    for ref in subject_refs:
        if not ref.startswith("Patient/"):
            errors.append(f"subject reference {ref!r} is not a Patient reference")
            continue
        if ref.removeprefix("Patient/") not in patient_ids:
            errors.append(f"subject reference {ref!r} does not resolve in bundle")

    return errors


def export_all_formats() -> dict[str, bytes]:
    """Generate all export formats from the unified data."""
    patients = pd.read_csv(config.PATIENTS_TABLE)
    bmi = pd.read_csv(config.BMI_TIMELINE_TABLE)
    med_hist = pd.read_csv(config.MEDICATION_HISTORY_TABLE)
    episodes = pd.read_csv(config.TREATMENT_EPISODES_TABLE)
    mapping = pd.read_csv(config.MAPPING_TABLE)
    from src.datastore import UnifiedDataRepository

    repo = UnifiedDataRepository.from_output_dir()

    exports = {}

    # CSV (already exist)
    for name in ["survey_unified", "patients", "bmi_timeline", "treatment_episodes",
                 "medication_history", "mapping_table", "quality_report"]:
        fp = config.OUTPUT_DIR / f"{name}.csv"
        if fp.exists():
            exports[f"{name}.csv"] = fp.read_bytes()

    # JSON — unified tables as nested JSON
    unified_json = {
        "meta": {
            "generated": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
            "engine": "UniQ",
            "patients": len(patients),
            "categories": int(mapping["clinical_category"].nunique()),
        },
        "patients": json.loads(patients.to_json(orient="records")),
        "bmi_timeline": json.loads(bmi.to_json(orient="records")),
        "treatment_episodes": json.loads(episodes.to_json(orient="records")),
        "medication_history": json.loads(med_hist.to_json(orient="records")),
    }
    exports["unified_data.json"] = json.dumps(unified_json, indent=2).encode("utf-8")

    # FHIR R4 Bundle (with coded conditions + adverse events)
    fhir_bundle = export_fhir_bundle(
        repo.patients,
        repo.bmi_timeline,
        repo.medication_history,
        repo.survey_validated,
    )
    exports["fhir_bundle.json"] = json.dumps(fhir_bundle, indent=2).encode("utf-8")

    # Answer normalization map
    norm_path = config.OUTPUT_DIR / "answer_normalization.json"
    if norm_path.exists():
        exports["answer_normalization.json"] = norm_path.read_bytes()

    # Taxonomy
    tax_path = config.OUTPUT_DIR / "taxonomy.json"
    if tax_path.exists():
        exports["taxonomy.json"] = tax_path.read_bytes()

    return exports


if __name__ == "__main__":
    exports = export_all_formats()
    for name, data in exports.items():
        print(f"  {name:35s} {len(data):>10,} bytes")

    # Save FHIR bundle
    fhir_path = config.OUTPUT_DIR / "fhir_bundle.json"
    fhir_path.write_bytes(exports["fhir_bundle.json"])
    print(f"\nFHIR bundle saved to {fhir_path}")

    bundle = json.loads(exports["fhir_bundle.json"])
    print(f"FHIR resources: {bundle['total']}")
    resource_types = {}
    for entry in bundle["entry"]:
        rt = entry["resource"]["resourceType"]
        resource_types[rt] = resource_types.get(rt, 0) + 1
    for rt, count in sorted(resource_types.items()):
        print(f"  {rt:30s} {count:>5}")
