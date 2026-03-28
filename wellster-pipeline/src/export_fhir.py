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
        obs["effectiveDateTime"] = str(row["date"])[:19] + "Z"
    return obs


def _fhir_medication(row: pd.Series) -> dict:
    """Convert a medication history row to a FHIR MedicationStatement."""
    med = {
        "resourceType": "MedicationStatement",
        "id": f"med-{int(row['user_id'])}-{int(row['treatment_id'])}",
        "status": "active" if pd.isna(row.get("ended")) else "completed",
        "subject": {"reference": f"Patient/patient-{int(row['user_id'])}"},
        "medicationCodeableConcept": {"text": str(row["product"])},
        "dosage": [{"text": str(row["dosage"]) if pd.notna(row.get("dosage")) else ""}],
    }
    if pd.notna(row.get("started")):
        period = {"start": str(row["started"])[:19] + "Z"}
        if pd.notna(row.get("ended")):
            period["end"] = str(row["ended"])[:19] + "Z"
        med["effectivePeriod"] = period
    return med


def export_fhir_bundle(
    patients: pd.DataFrame,
    bmi: pd.DataFrame,
    med_hist: pd.DataFrame,
) -> dict:
    """Build a FHIR R4 Bundle with all unified patient data."""
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

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat() + "Z",
        "meta": {"source": "UniQ Questionnaire Intelligence Engine"},
        "total": len(entries),
        "entry": entries,
    }
    return bundle


def export_all_formats() -> dict[str, bytes]:
    """Generate all export formats from the unified data."""
    patients = pd.read_csv(config.PATIENTS_TABLE)
    bmi = pd.read_csv(config.BMI_TIMELINE_TABLE)
    med_hist = pd.read_csv(config.MEDICATION_HISTORY_TABLE)
    episodes = pd.read_csv(config.TREATMENT_EPISODES_TABLE)
    survey = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
    mapping = pd.read_csv(config.MAPPING_TABLE)

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

    # FHIR R4 Bundle
    fhir_bundle = export_fhir_bundle(patients, bmi, med_hist)
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
