"""Phase 2 smoke tests for `UnifiedDataRepository`.

These are intentionally light — they verify the repository loads, dtypes
are coerced correctly, `answer_canonical` is pre-parsed, and patient-keyed
accessors return the right rows. Replaced by a proper pytest suite during
Phase 5 (Packaging + formal test setup).

Prerequisites: a previous pipeline run (`output/` populated). Skips
gracefully if artifacts are missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.datastore import PatientRecord, UnifiedDataRepository


_results: list[tuple[str, str, str]] = []


def _ok(name: str, detail: str = "") -> None:
    _results.append(("OK", name, detail))


def _fail(name: str, detail: str) -> None:
    _results.append(("FAIL", name, detail))


def _report_and_exit() -> int:
    icons = {"OK": "[OK]", "FAIL": "[X]"}
    for status, name, detail in _results:
        print(f"  {icons[status]} {name}" + (f"  -- {detail}" if detail else ""))
    passes = sum(1 for s, *_ in _results if s == "OK")
    fails = sum(1 for s, *_ in _results if s == "FAIL")
    print(f"\n{passes} pass, {fails} fail")
    return 1 if fails else 0


def main() -> int:
    if not config.MAPPING_TABLE.exists():
        print("SKIP: output artifacts missing — run pipeline.py first")
        return 0

    repo = UnifiedDataRepository.from_output_dir()
    _ok(
        "repo loads from output_dir",
        f"{repo.count_patients():,} patients, {len(repo.categories())} categories",
    )

    # dtype coercion
    uid_dtype = repo.patients["user_id"].dtype
    if pd.api.types.is_integer_dtype(uid_dtype):
        _ok("patients.user_id is integer", str(uid_dtype))
    else:
        _fail("patients.user_id is integer", str(uid_dtype))
        return _report_and_exit()

    if "date" in repo.bmi_timeline.columns:
        bmi_dtype = repo.bmi_timeline["date"].dtype
        if pd.api.types.is_datetime64_any_dtype(bmi_dtype):
            _ok("bmi.date is datetime", str(bmi_dtype))
        else:
            _fail("bmi.date is datetime", str(bmi_dtype))
            return _report_and_exit()

    # answer_canonical pre-parsed
    sample = repo.survey["answer_canonical"].head(200)
    as_lists = sum(isinstance(v, list) for v in sample)
    if as_lists == len(sample):
        _ok("answer_canonical pre-parsed to list", f"{as_lists}/{len(sample)} samples")
    else:
        _fail("answer_canonical pre-parsed to list", f"only {as_lists}/{len(sample)}")
        return _report_and_exit()

    # Patient lookup — known + unknown
    some_uid = int(repo.patients["user_id"].dropna().iloc[0])
    p = repo.patient(some_uid)
    if p is None:
        _fail(f"patient({some_uid}) returns record", "got None")
        return _report_and_exit()
    if not isinstance(p, PatientRecord):
        _fail("patient() returns PatientRecord", type(p).__name__)
        return _report_and_exit()
    if p.user_id != some_uid:
        _fail("patient().user_id matches", f"{p.user_id} != {some_uid}")
        return _report_and_exit()
    _ok(
        f"patient({some_uid})",
        f"age={p.current_age}, gender={p.gender}, treatments={p.total_treatments}",
    )

    if repo.patient(-1) is None:
        _ok("patient(-1) returns None")
    else:
        _fail("patient(-1) returns None", "got a record")
        return _report_and_exit()

    # BMI timeline filtered + sorted
    uid_with_bmi = int(repo.bmi_timeline["user_id"].dropna().iloc[0])
    bmi = repo.bmi_for_patient(uid_with_bmi)
    if not (bmi["user_id"] == uid_with_bmi).all():
        _fail("bmi_for_patient filter", "leaked other user_ids")
        return _report_and_exit()
    if len(bmi) >= 2 and not bmi["date"].is_monotonic_increasing:
        _fail("bmi_for_patient sorted", "dates not monotonic increasing")
        return _report_and_exit()
    _ok(f"bmi_for_patient({uid_with_bmi})", f"{len(bmi)} rows, sorted")

    # Survey filter by category
    survey_all = repo.survey_for_patient(some_uid)
    if not (survey_all["user_id"] == some_uid).all():
        _fail("survey_for_patient filter", "leaked other user_ids")
        return _report_and_exit()
    _ok(f"survey_for_patient({some_uid})", f"{len(survey_all)} rows")

    if "BMI_MEASUREMENT" in repo.categories():
        subset = repo.survey_for_patient(some_uid, category="BMI_MEASUREMENT")
        cats = set(subset["clinical_category"].unique())
        if cats and cats != {"BMI_MEASUREMENT"}:
            _fail("survey_for_patient category filter", f"leaked {cats}")
            return _report_and_exit()
        _ok("survey_for_patient category=BMI_MEASUREMENT", f"{len(subset)} rows")

    # Metadata sanity
    active = repo.count_active_patients()
    total = repo.count_patients()
    if 0 <= active <= total:
        _ok("count_active_patients in [0, count_patients]", f"{active} / {total}")
    else:
        _fail("count_active_patients in [0, count_patients]", f"{active} / {total}")
        return _report_and_exit()

    return _report_and_exit()


if __name__ == "__main__":
    sys.exit(main())
