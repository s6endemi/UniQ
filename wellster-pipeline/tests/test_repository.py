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

    # ------------------------------------------------------------------
    # Ground-truth value correctness (independent path: raw CSV via Pandas)
    # ------------------------------------------------------------------

    raw_patients = pd.read_csv(config.PATIENTS_TABLE)
    raw_patients["user_id"] = pd.to_numeric(raw_patients["user_id"], errors="coerce").astype("Int64")

    # Deterministic sample: first, 25%, 50%, 75%, last patient by user_id.
    sorted_uids = sorted(int(u) for u in raw_patients["user_id"].dropna())
    pick_indices = [0, len(sorted_uids) // 4, len(sorted_uids) // 2,
                    3 * len(sorted_uids) // 4, len(sorted_uids) - 1]
    sample_uids = [sorted_uids[i] for i in pick_indices]

    mismatches: list[str] = []
    for uid in sample_uids:
        raw_row = raw_patients[raw_patients["user_id"] == uid].iloc[0]
        rec = repo.patient(uid)
        if rec is None:
            mismatches.append(f"uid={uid}: repo returned None but CSV has row")
            continue
        # Gender string equality
        raw_gender = str(raw_row["gender"]) if pd.notna(raw_row["gender"]) else ""
        if rec.gender != raw_gender:
            mismatches.append(
                f"uid={uid}: gender {rec.gender!r} vs CSV {raw_gender!r}"
            )
        # Age int equality (both should be int after coercion)
        if pd.notna(raw_row["current_age"]):
            if rec.current_age != int(raw_row["current_age"]):
                mismatches.append(
                    f"uid={uid}: age {rec.current_age} vs CSV {int(raw_row['current_age'])}"
                )
        # Treatment count equality
        if pd.notna(raw_row.get("total_treatments")):
            if rec.total_treatments != int(raw_row["total_treatments"]):
                mismatches.append(
                    f"uid={uid}: total_treatments "
                    f"{rec.total_treatments} vs CSV {int(raw_row['total_treatments'])}"
                )

    if not mismatches:
        _ok("patient() values match raw CSV",
            f"{len(sample_uids)} patients × 3 fields, all equal")
    else:
        _fail("patient() values match raw CSV",
              f"{len(mismatches)} mismatches; first: {mismatches[0]}")

    # BMI values physiologically plausible among rows the pipeline itself
    # considers clean (data_quality_flag == 'ok'). This cross-checks two
    # independent validation paths: pipeline quality flagging in unify.py
    # and our post-hoc physiological sanity range.
    bmi_clean = repo.bmi_timeline[
        repo.bmi_timeline["data_quality_flag"] == "ok"
    ].head(200)
    flagged_count = int(
        (repo.bmi_timeline["data_quality_flag"] != "ok").sum()
    )
    if len(bmi_clean) > 0:
        out_of_range = bmi_clean[
            (bmi_clean["bmi"] < 10) | (bmi_clean["bmi"] > 80)
        ]
        if len(out_of_range) == 0:
            _ok("clean BMI rows are physiologically plausible",
                f"{len(bmi_clean)} 'ok' samples in [10, 80]; "
                f"{flagged_count} pre-flagged by pipeline")
        else:
            _fail(
                "clean BMI rows are physiologically plausible",
                f"{len(out_of_range)} 'ok'-flagged rows outside [10, 80] — "
                f"pipeline quality flag under-fired",
            )

    # bmi_for_patient filter tightness: NO uid leakage
    if len(repo.bmi_timeline) > 0:
        uid_with_bmi = int(repo.bmi_timeline["user_id"].dropna().iloc[0])
        patient_bmi = repo.bmi_for_patient(uid_with_bmi)
        if len(patient_bmi) > 0 and (patient_bmi["user_id"] == uid_with_bmi).all():
            _ok("bmi_for_patient filter is tight (no uid leakage)",
                f"uid={uid_with_bmi}, {len(patient_bmi)} rows")
        else:
            _fail("bmi_for_patient filter is tight (no uid leakage)",
                  "other user_ids leaked into result")

    # survey_for_patient content actually belongs to the patient
    some_uid = int(repo.patients["user_id"].dropna().iloc[0])
    survey_slice = repo.survey_for_patient(some_uid)
    if len(survey_slice) > 0:
        bad = survey_slice[survey_slice["user_id"] != some_uid]
        if len(bad) == 0:
            _ok("survey_for_patient content matches uid",
                f"uid={some_uid}, {len(survey_slice)} rows, all match")
        else:
            _fail("survey_for_patient content matches uid",
                  f"{len(bad)} rows leaked")

    return _report_and_exit()


if __name__ == "__main__":
    sys.exit(main())
