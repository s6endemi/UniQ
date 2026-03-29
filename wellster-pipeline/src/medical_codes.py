"""
Medical Coding Layer — Maps UniQ categories to international healthcare standards

Maps each clinical category to:
  - FHIR R4 ResourceType
  - Primary coding system (LOINC, SNOMED CT, ICD-10, RxNorm)
  - Specific codes for canonical answer values

This transforms our unified data from "clean CSV" to "clinically coded,
interoperable healthcare data" — ready for EHR integration, regulatory
reporting, and cross-system analytics.

Standards used:
  - LOINC (Logical Observation Identifiers Names & Codes) — observations, lab results
  - SNOMED CT (Systematized Nomenclature of Medicine) — clinical terms
  - ICD-10 (International Classification of Diseases) — diagnoses
  - RxNorm — medications
  - ATC (Anatomical Therapeutic Chemical) — drug classification
"""

# ── Category → FHIR ResourceType + Primary Code ─────────────────────────────

CATEGORY_CODING = {
    "BMI_MEASUREMENT": {
        "fhir_type": "Observation",
        "fhir_category": "vital-signs",
        "loinc": [
            {"code": "39156-5", "display": "Body mass index (BMI)"},
            {"code": "29463-7", "display": "Body weight"},
            {"code": "8302-2", "display": "Body height"},
        ],
    },
    "BLOOD_PRESSURE_CHECK": {
        "fhir_type": "Observation",
        "fhir_category": "vital-signs",
        "loinc": [
            {"code": "85354-9", "display": "Blood pressure panel"},
        ],
    },
    "SIDE_EFFECT_REPORT": {
        "fhir_type": "AdverseEvent",
        "fhir_category": "adverse-event",
        "snomed": {"code": "281647001", "display": "Adverse reaction"},
    },
    "MEDICAL_CONDITIONS": {
        "fhir_type": "Condition",
        "fhir_category": "encounter-diagnosis",
        "system": "ICD-10 / SNOMED CT",
    },
    "COMORBIDITY_SCREENING": {
        "fhir_type": "Condition",
        "fhir_category": "encounter-diagnosis",
        "system": "ICD-10 / SNOMED CT",
    },
    "TREATMENT_ADHERENCE": {
        "fhir_type": "MedicationStatement",
        "fhir_category": "medication",
        "extension": "http://hl7.org/fhir/StructureDefinition/medication-adherence",
    },
    "MEDICATION_HISTORY": {
        "fhir_type": "MedicationStatement",
        "fhir_category": "medication",
        "system": "RxNorm / ATC",
    },
    "PRIOR_GLP1_MEDICATION": {
        "fhir_type": "MedicationStatement",
        "fhir_category": "medication",
        "system": "RxNorm / ATC",
    },
    "TREATMENT_EFFECTIVENESS": {
        "fhir_type": "Observation",
        "fhir_category": "survey",
        "loinc": [{"code": "77577-9", "display": "Patient reported outcome measure"}],
    },
    "LIFESTYLE_ASSESSMENT": {
        "fhir_type": "Observation",
        "fhir_category": "social-history",
        "loinc": [{"code": "72166-2", "display": "Tobacco smoking status"}],
    },
    "EXERCISE_FREQUENCY": {
        "fhir_type": "Observation",
        "fhir_category": "social-history",
        "loinc": [{"code": "68516-4", "display": "Exercise frequency"}],
    },
    "WEIGHT_MANAGEMENT_HISTORY": {
        "fhir_type": "Observation",
        "fhir_category": "social-history",
        "loinc": [{"code": "LP172862-0", "display": "Weight management"}],
    },
    "INFORMED_CONSENT": {
        "fhir_type": "Consent",
        "fhir_category": "consent",
    },
    "TREATMENT_CONFIRMATION": {
        "fhir_type": "Consent",
        "fhir_category": "consent",
    },
    "DOSING_INSTRUCTIONS": {
        "fhir_type": "MedicationRequest",
        "fhir_category": "medication",
    },
    "IDENTITY_VERIFICATION": {
        "fhir_type": "DocumentReference",
        "fhir_category": "document",
    },
    "BODY_PHOTO": {
        "fhir_type": "Media",
        "fhir_category": "image",
    },
    "PHOTO_UPLOAD": {
        "fhir_type": "Media",
        "fhir_category": "image",
    },
}


# ── Canonical Answers → Medical Codes ────────────────────────────────────────

CONDITION_CODES = {
    # Canonical answer → (ICD-10, SNOMED CT, display)
    "HYPERTENSION": ("I10", "38341003", "Essential hypertension"),
    "HYPERLIPIDEMIA": ("E78.5", "55822004", "Hyperlipidemia"),
    "DIABETES": ("E11", "73211009", "Diabetes mellitus type 2"),
    "DIABETES_TYPE_2": ("E11", "44054006", "Diabetes mellitus type 2"),
    "PREDIABETES": ("R73.03", "15777000", "Prediabetes"),
    "ASTHMA": ("J45", "195967001", "Asthma"),
    "HYPOTHYROIDISM": ("E03.9", "40930008", "Hypothyroidism"),
    "SLEEP_APNEA": ("G47.33", "73430006", "Obstructive sleep apnea"),
    "OBSTRUCTIVE_SLEEP_APNEA": ("G47.33", "73430006", "Obstructive sleep apnea"),
    "DYSLIPIDEMIA": ("E78.5", "370992007", "Dyslipidemia"),
    "DEPRESSION": ("F32.9", "35489007", "Depressive disorder"),
    "ANXIETY": ("F41.9", "48694002", "Anxiety disorder"),
    "ARTHRITIS": ("M13.9", "3723001", "Arthritis"),
    "GOUT": ("M10.9", "90560007", "Gout"),
    "PCOS": ("E28.2", "237055002", "Polycystic ovary syndrome"),
    "FATTY_LIVER": ("K76.0", "197321007", "Non-alcoholic fatty liver disease"),
    "GERD": ("K21.0", "235595009", "Gastroesophageal reflux disease"),
    "MIGRAINE": ("G43.9", "37796009", "Migraine"),
    "CONTRACEPTION": ("Z30", "13197004", "Contraception"),
}

SIDE_EFFECT_CODES = {
    # Canonical answer → (SNOMED CT code, display)
    "OCCASIONAL_NAUSEA": ("422587007", "Nausea"),
    "GI_COMPLAINTS": ("386618008", "Gastrointestinal symptom"),
    "NAUSEA_VOMITING": ("422587007", "Nausea and vomiting"),
    "CONSTIPATION": ("14760008", "Constipation"),
    "DIARRHEA": ("62315008", "Diarrhea"),
    "FATIGUE": ("84229001", "Fatigue"),
    "HEADACHE": ("25064002", "Headache"),
    "DIZZINESS": ("404640003", "Dizziness"),
    "INJECTION_SITE_REACTION": ("95376002", "Injection site reaction"),
    "SLEEP_DISTURBANCE": ("53888004", "Sleep disorder"),
    "APPETITE_LOSS": ("79890006", "Loss of appetite"),
    "ABDOMINAL_PAIN": ("21522001", "Abdominal pain"),
}

MEDICATION_CODES = {
    # Product name → (RxNorm, ATC, generic name)
    "Mounjaro": ("2601734", "A10BJ07", "Tirzepatide"),
    "Wegovy": ("2200644", "A10BJ06", "Semaglutide"),
    "Saxenda": ("1598268", "A10BJ02", "Liraglutide"),
    "Tirzepatide": ("2601734", "A10BJ07", "Tirzepatide"),
    "Semaglutide": ("2200644", "A10BJ06", "Semaglutide"),
    "Liraglutide": ("1598268", "A10BJ02", "Liraglutide"),
}

BLOOD_PRESSURE_CODES = {
    "NORMAL": ("normal", "Blood pressure within normal range (90/60 - 140/90)"),
    "HIGH": ("high", "Blood pressure above 140/90 mmHg"),
}


def get_category_coding(category: str) -> dict:
    """Get the FHIR + medical coding for a clinical category."""
    return CATEGORY_CODING.get(category, {
        "fhir_type": "Observation",
        "fhir_category": "survey",
    })


def get_condition_code(canonical_answer: str) -> dict | None:
    """Get ICD-10 + SNOMED code for a canonical condition."""
    entry = CONDITION_CODES.get(canonical_answer)
    if entry:
        icd10, snomed, display = entry
        return {
            "icd10": {"system": "http://hl7.org/fhir/sid/icd-10", "code": icd10, "display": display},
            "snomed": {"system": "http://snomed.info/sct", "code": snomed, "display": display},
        }
    return None


def get_side_effect_code(canonical_answer: str) -> dict | None:
    """Get SNOMED code for a canonical side effect."""
    entry = SIDE_EFFECT_CODES.get(canonical_answer)
    if entry:
        code, display = entry
        return {"system": "http://snomed.info/sct", "code": code, "display": display}
    return None


def get_medication_code(product_name: str) -> dict | None:
    """Get RxNorm + ATC codes for a medication."""
    # Try exact match first, then partial
    for key, (rxnorm, atc, generic) in MEDICATION_CODES.items():
        if key.lower() in product_name.lower():
            return {
                "rxnorm": {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rxnorm, "display": generic},
                "atc": {"system": "http://www.whocc.no/atc", "code": atc, "display": generic},
            }
    return None


def get_coding_summary() -> dict:
    """Get a summary of all medical codes available."""
    return {
        "standards": ["LOINC", "SNOMED CT", "ICD-10", "RxNorm", "ATC"],
        "conditions_coded": len(CONDITION_CODES),
        "side_effects_coded": len(SIDE_EFFECT_CODES),
        "medications_coded": len(MEDICATION_CODES),
        "fhir_resource_types": sorted(set(v["fhir_type"] for v in CATEGORY_CODING.values())),
    }
