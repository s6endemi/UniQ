"""Smoke-Test für Phase 0: demo.py's File-Loader gegen die frischen Artefakte.

Prueft:
  1. Alle Dateien aus _load_from_files() sind vorhanden und lesbar.
  2. Hardcoded Kategorie-Strings in demo.py existieren in der Taxonomie.
  3. Erwartete Spalten pro Tabelle sind vorhanden.

Output: PASS / WARN / FAIL Liste. Dies ist Golden-Master-Sanity,
nicht Unit-Test. Wird bei Phase 5 durch echte pytest-Tests abgeloest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


EXPECTED_COLUMNS = {
    "mapping": {"question_id", "question_en", "clinical_category", "answer_type",
                "confidence", "duplicate_count"},
    "survey": {"user_id", "treatment_id", "question_id", "question_en",
               "clinical_category", "answer_canonical", "parse_method", "product"},
    "patients": {"user_id", "gender", "current_age", "total_treatments",
                 "active_treatments", "current_medication", "tenure_days"},
    "episodes": {"treatment_id", "user_id", "product", "t_status",
                 "order_type", "start_date", "latest_date"},
    "bmi": {"user_id", "treatment_id", "date", "bmi", "product_at_time"},
    "med_hist": {"user_id", "product", "started", "ended", "duration_days"},
    "quality": {"check_type", "severity", "user_id", "description"},
}

# Kategorie-Strings, auf die demo.py hartcodiert angewiesen ist.
# Fehlende = UI-Page zeigt "No data" gegen aktuelle Taxonomie.
DEMO_HARDCODED_CATEGORIES = {
    "BMI_MEASUREMENT",            # Patient page, Insights/Overview
    "SIDE_EFFECT_REPORT",         # Insights/Side Effects tab
    "MEDICAL_CONDITIONS",         # Insights/Conditions tab
    "TREATMENT_ADHERENCE",        # Insights/Compliance tab
    "BLOOD_PRESSURE_CHECK",       # Results page example
    "COMORBIDITY_SCREENING",      # FHIR export path
}


def main() -> int:
    results: list[tuple[str, str, str]] = []

    def record(status: str, test: str, detail: str = "") -> None:
        results.append((status, test, detail))

    # 1. File existence
    paths = {
        "mapping": config.MAPPING_TABLE,
        "survey": config.SURVEY_UNIFIED_TABLE,
        "patients": config.PATIENTS_TABLE,
        "episodes": config.TREATMENT_EPISODES_TABLE,
        "bmi": config.BMI_TIMELINE_TABLE,
        "med_hist": config.MEDICATION_HISTORY_TABLE,
        "quality": config.QUALITY_REPORT_TABLE,
    }
    for name, path in paths.items():
        if path.exists():
            record("PASS", f"{name}.csv exists", f"{path.stat().st_size:,} bytes")
        else:
            record("FAIL", f"{name}.csv MISSING", str(path))
            return _report(results)

    norm_path = config.OUTPUT_DIR / "answer_normalization.json"
    tax_path = config.OUTPUT_DIR / "taxonomy.json"
    for p in (norm_path, tax_path):
        status = "PASS" if p.exists() else "FAIL"
        record(status, f"{p.name} exists")

    # 2. Schema check (same load pattern as demo._load_from_files)
    dataframes: dict[str, pd.DataFrame] = {}
    for name, path in paths.items():
        try:
            df = pd.read_csv(path, low_memory=False)
            dataframes[name] = df
            record("PASS", f"{name}.csv loads", f"{len(df):,} rows x {len(df.columns)} cols")
        except Exception as e:
            record("FAIL", f"{name}.csv load error", str(e))
            return _report(results)

    for name, required in EXPECTED_COLUMNS.items():
        present = set(dataframes[name].columns)
        missing = required - present
        if not missing:
            record("PASS", f"{name} schema ok")
        else:
            record("FAIL", f"{name} missing columns", str(sorted(missing)))

    # 3. Category drift check (the whole reason for the Concept-Schicht)
    taxonomy_cats = set(dataframes["mapping"]["clinical_category"].dropna().unique())
    record("INFO", "taxonomy size", f"{len(taxonomy_cats)} categories")

    for cat in sorted(DEMO_HARDCODED_CATEGORIES):
        if cat in taxonomy_cats:
            rows = (dataframes["survey"]["clinical_category"] == cat).sum()
            record("PASS", f"demo hardcodes {cat!r}", f"{rows:,} rows available")
        else:
            close = [c for c in taxonomy_cats if any(t in c for t in cat.split("_"))][:2]
            record("WARN", f"demo hardcodes {cat!r}", f"NOT in taxonomy; closest: {close}")

    # 4. answer_canonical JSON-parse smoke (the 5x-parsed field)
    survey = dataframes["survey"]
    sample = survey["answer_canonical"].dropna().head(500)
    parse_failures = 0
    for v in sample:
        try:
            parsed = json.loads(str(v))
            if not isinstance(parsed, list):
                parse_failures += 1
        except (json.JSONDecodeError, TypeError):
            parse_failures += 1
    if parse_failures == 0:
        record("PASS", "answer_canonical JSON-parseable", f"{len(sample)} samples ok")
    else:
        record("FAIL", "answer_canonical parse errors",
               f"{parse_failures}/{len(sample)} samples broken")

    return _report(results)


def _report(results: list[tuple[str, str, str]]) -> int:
    icons = {"PASS": "[OK]", "WARN": "[!]", "FAIL": "[X]", "INFO": "[i]"}
    for status, test, detail in results:
        print(f"  {icons[status]} {test}" + (f"  -- {detail}" if detail else ""))

    fails = sum(1 for s, _, _ in results if s == "FAIL")
    warns = sum(1 for s, _, _ in results if s == "WARN")
    passes = sum(1 for s, _, _ in results if s == "PASS")
    print(f"\n{passes} pass, {warns} warn, {fails} fail")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
