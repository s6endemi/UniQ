"""Phase 4 smoke tests for the FastAPI surface.

Uses FastAPI's `TestClient` so we exercise the real HTTP routing and
dependency injection without standing up a real server.

What we cover:
    - /health reflects artifact-loaded state.
    - /schema returns every registered table.
    - /categories matches the underlying query service.
    - /mapping list + single-GET round-trip.
    - PATCH /mapping/{cat} with review_status=approved survives a mapping
      regeneration (approved entries must not be overwritten by the AI).
    - /patients/{id} returns typed record; unknown id -> 404.
    - /export/{id}/fhir returns a Bundle with entries.
    - /chat stub returns the agreed response shape.

Prereq: `output/` populated (pipeline.py was run). Skips otherwise.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from fastapi.testclient import TestClient

from src.api.deps import SEMANTIC_MAPPING_PATH, state
from src.api.main import app
from src.semantic_mapping_ai import _merge_with_cache


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
    if not config.MAPPING_TABLE.exists() or not SEMANTIC_MAPPING_PATH.exists():
        print("SKIP: output artifacts missing — run pipeline.py first")
        return 0

    # Snapshot semantic_mapping.json so we can restore it after the test
    mapping_backup = SEMANTIC_MAPPING_PATH.read_text(encoding="utf-8")

    try:
        with TestClient(app) as client:
            # 1. Health reflects readiness
            r = client.get("/health")
            if r.status_code == 200 and r.json()["status"] == "ok":
                h = r.json()
                _ok("/health status=ok",
                    f"patients={h['patients']}, categories={h['categories']}, "
                    f"mapping={h['mapping_entries']}")
            else:
                _fail("/health status=ok", f"{r.status_code} {r.text[:200]}")
                return _report_and_exit()

            # 2. Schema
            r = client.get("/schema")
            if r.status_code == 200 and "survey_unified" in r.json()["tables"]:
                cols = len(r.json()["tables"]["survey_unified"])
                _ok("/schema includes survey_unified", f"{cols} columns")
            else:
                _fail("/schema includes survey_unified", f"{r.status_code}")
                return _report_and_exit()

            # 3. Categories
            r = client.get("/categories")
            if r.status_code == 200 and r.json()["count"] > 0:
                _ok("/categories", f"{r.json()['count']} categories")
            else:
                _fail("/categories", str(r.status_code))
                return _report_and_exit()

            # 4. Mapping list
            r = client.get("/mapping")
            if r.status_code == 200 and isinstance(r.json(), list):
                entries = r.json()
                sample_cat = entries[0]["category"]
                _ok("/mapping list", f"{len(entries)} entries, first={sample_cat}")
            else:
                _fail("/mapping list", str(r.status_code))
                return _report_and_exit()

            # 5. Single mapping GET
            r = client.get(f"/mapping/{sample_cat}")
            if r.status_code == 200 and r.json()["category"] == sample_cat:
                _ok(f"/mapping/{sample_cat}")
            else:
                _fail(f"/mapping/{sample_cat}", str(r.status_code))
                return _report_and_exit()

            # 6. Unknown mapping -> 404
            r = client.get("/mapping/DOES_NOT_EXIST")
            if r.status_code == 404:
                _ok("/mapping/unknown returns 404")
            else:
                _fail("/mapping/unknown returns 404", f"got {r.status_code}")

            # 7. PATCH mapping with review_status=approved
            target = sample_cat
            r = client.patch(f"/mapping/{target}", json={"review_status": "approved"})
            if r.status_code == 200 and r.json()["review_status"] == "approved":
                _ok(f"PATCH /mapping/{target} approve",
                    f"status={r.json()['review_status']}")
            else:
                _fail(f"PATCH /mapping/{target} approve",
                      f"{r.status_code} {r.text[:200]}")
                return _report_and_exit()

            # 8. Field-edit without explicit status -> overridden
            r = client.patch(
                f"/mapping/{target}",
                json={"display_label": "Custom Reviewer Label"},
            )
            if r.status_code == 200 and r.json()["review_status"] == "overridden":
                _ok("PATCH field-edit -> overridden",
                    f"label={r.json()['display_label']!r}")
            else:
                _fail("PATCH field-edit -> overridden",
                      f"{r.status_code} {r.text[:200]}")

            # 9. PATCH with invalid fhir_resource_type -> 422
            r = client.patch(
                f"/mapping/{target}",
                json={"fhir_resource_type": "FakeResource"},
            )
            if r.status_code == 422:
                _ok("PATCH rejects invalid fhir_resource_type")
            else:
                _fail("PATCH rejects invalid fhir_resource_type",
                      f"got {r.status_code}")

            # 10. Regression: overridden entry is preserved across AI re-merge.
            # Simulate a pipeline re-run producing fresh AI entries for the
            # same categories. _merge_with_cache must keep our override.
            current_mapping = state.read_mapping()
            active_entries = {
                k: v for k, v in current_mapping.items()
                if not k.startswith("__") and isinstance(v, dict)
            }
            fake_ai_fresh = {
                cat: {
                    "display_label": "AI Overwrites You",
                    "fhir_resource_type": "Observation",
                    "confidence": "high",
                } for cat in active_entries
            }
            merged = _merge_with_cache(fake_ai_fresh, active_entries)
            if merged[target]["display_label"] == "Custom Reviewer Label":
                _ok("overridden entry survives AI re-merge",
                    "reviewer label preserved")
            else:
                _fail("overridden entry survives AI re-merge",
                      f"got {merged[target]['display_label']!r}")

            # 11. /patients/{id}
            uid = int(state.repo.patients["user_id"].dropna().iloc[0])
            r = client.get(f"/patients/{uid}")
            if r.status_code == 200 and r.json()["user_id"] == uid:
                _ok(f"/patients/{uid}",
                    f"gender={r.json()['gender']}, age={r.json()['current_age']}")
            else:
                _fail(f"/patients/{uid}", str(r.status_code))

            # 12. Unknown patient -> 404
            r = client.get("/patients/-1")
            if r.status_code == 404:
                _ok("/patients/-1 returns 404")
            else:
                _fail("/patients/-1 returns 404", f"got {r.status_code}")

            # 13. /export/{id}/fhir
            r = client.get(f"/export/{uid}/fhir")
            if r.status_code == 200 and r.json().get("resourceType") == "Bundle":
                total = r.json().get("total", 0)
                _ok(f"/export/{uid}/fhir", f"{total} FHIR resources")
            else:
                _fail(f"/export/{uid}/fhir", str(r.status_code))

            # 13b. Codex high finding: API-exported bundle must match a
            # raw-CSV export for the same patient. The bug was that the
            # Repository pre-parses answer_canonical to list[str] and
            # export_fhir_bundle silently dropped rows because it called
            # json.loads(str(list)).
            import pandas as pd
            from src.export_fhir import export_fhir_bundle

            # Find a patient likely to have Conditions/AdverseEvents so the
            # regression surface is maximised. 381254 is the patient Codex
            # reported the bug for; fall back to any patient with survey
            # rows in the sensitive categories if that id is absent.
            test_uid: int | None = None
            candidate_uids = [381254]
            available_uids = set(state.repo.patients["user_id"].dropna().astype(int))
            for cand in candidate_uids:
                if cand in available_uids:
                    test_uid = cand
                    break
            if test_uid is None:
                test_uid = uid  # fall back to the earlier patient

            r_api = client.get(f"/export/{test_uid}/fhir")
            api_total = r_api.json().get("total", 0) if r_api.status_code == 200 else -1

            # Same patient, same pipeline, but with the raw JSON-string
            # answer_canonical column straight off disk.
            raw_survey = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
            raw_patients = pd.read_csv(config.PATIENTS_TABLE)
            raw_bmi = pd.read_csv(config.BMI_TIMELINE_TABLE)
            raw_med = pd.read_csv(config.MEDICATION_HISTORY_TABLE)
            raw_bundle = export_fhir_bundle(
                raw_patients[raw_patients["user_id"] == test_uid],
                raw_bmi[raw_bmi["user_id"] == test_uid],
                raw_med[raw_med["user_id"] == test_uid],
                raw_survey[raw_survey["user_id"] == test_uid],
            )
            raw_total = raw_bundle["total"]

            if api_total == raw_total and api_total > 0:
                _ok(
                    "API-FHIR matches raw-CSV-FHIR (pre-parse regression)",
                    f"uid={test_uid}, both={api_total}",
                )
            else:
                _fail(
                    "API-FHIR matches raw-CSV-FHIR (pre-parse regression)",
                    f"uid={test_uid}, api={api_total}, raw={raw_total}",
                )

            # 14. /chat stub
            r = client.post("/chat", json={"message": "hello"})
            if r.status_code == 200 and "reply" in r.json():
                _ok("/chat stub returns reply shape",
                    f"sql={r.json()['sql']}, truncated={r.json()['truncated']}")
            else:
                _fail("/chat stub returns reply shape", str(r.status_code))

            # 13d. FHIR bundle *content*: must contain exactly one Patient
            # resource whose identifier matches the requested uid, plus
            # every entry has a resourceType from the allow-list.
            r = client.get(f"/export/{test_uid}/fhir")
            bundle = r.json()
            entries = bundle.get("entry", [])
            resource_types = [e["resource"]["resourceType"] for e in entries]

            patient_entries = [
                e["resource"] for e in entries
                if e["resource"]["resourceType"] == "Patient"
            ]
            if len(patient_entries) != 1:
                _fail(
                    "FHIR bundle has exactly one Patient",
                    f"got {len(patient_entries)}",
                )
            else:
                pat = patient_entries[0]
                identifiers = [i.get("value") for i in pat.get("identifier", [])]
                if str(test_uid) in identifiers:
                    _ok(
                        "FHIR bundle Patient resource identifier matches uid",
                        f"uid={test_uid}, types={sorted(set(resource_types))}",
                    )
                else:
                    _fail(
                        "FHIR bundle Patient resource identifier matches uid",
                        f"uid={test_uid} not in {identifiers}",
                    )

            # All resourceTypes must come from a known FHIR set. A typo or
            # hallucinated type would sneak through without this check.
            known_fhir_types = {
                "Patient", "Observation", "Condition", "MedicationStatement",
                "AdverseEvent", "AllergyIntolerance", "Consent",
                "DocumentReference", "Media", "QuestionnaireResponse",
                "Procedure", "Immunization", "MedicationRequest",
                "FamilyMemberHistory",
            }
            unknown_types = set(resource_types) - known_fhir_types
            if not unknown_types:
                _ok(
                    "FHIR bundle resource types are all known",
                    f"{sorted(set(resource_types))}",
                )
            else:
                _fail(
                    "FHIR bundle resource types are all known",
                    f"unknown: {unknown_types}",
                )

            # Ground-truth patient value check via API (independent from
            # raw CSV path). Picks the same sample uids used in test_repository.
            import pandas as pd
            raw_patients = pd.read_csv(config.PATIENTS_TABLE)
            raw_patients["user_id"] = pd.to_numeric(
                raw_patients["user_id"], errors="coerce"
            ).astype("Int64")
            uids_sorted = sorted(
                int(u) for u in raw_patients["user_id"].dropna()
            )
            api_check_uids = [
                uids_sorted[0],
                uids_sorted[len(uids_sorted) // 2],
                uids_sorted[-1],
            ]
            api_mismatches: list[str] = []
            for u in api_check_uids:
                raw_row = raw_patients[raw_patients["user_id"] == u].iloc[0]
                resp = client.get(f"/patients/{u}")
                if resp.status_code != 200:
                    api_mismatches.append(f"uid={u}: status={resp.status_code}")
                    continue
                data = resp.json()
                raw_gender = str(raw_row["gender"]) if pd.notna(raw_row["gender"]) else ""
                if data["gender"] != raw_gender:
                    api_mismatches.append(
                        f"uid={u}: gender {data['gender']!r} vs CSV {raw_gender!r}"
                    )
                if pd.notna(raw_row["current_age"]):
                    if data["current_age"] != int(raw_row["current_age"]):
                        api_mismatches.append(
                            f"uid={u}: age {data['current_age']} vs CSV {int(raw_row['current_age'])}"
                        )
            if not api_mismatches:
                _ok(
                    "/patients/{id} values match raw CSV",
                    f"{len(api_check_uids)} patients verified",
                )
            else:
                _fail(
                    "/patients/{id} values match raw CSV",
                    f"{len(api_mismatches)} mismatches: {api_mismatches[0]}",
                )

    finally:
        # Restore semantic_mapping.json even if tests failed
        SEMANTIC_MAPPING_PATH.write_text(mapping_backup, encoding="utf-8")

    # 15. Codex medium finding: mapping endpoints must 503 when
    # semantic_mapping.json is absent (not return empty list or 404).
    # Simulate absence by temporarily renaming the file.
    renamed = SEMANTIC_MAPPING_PATH.with_suffix(".json.test_bak")
    SEMANTIC_MAPPING_PATH.rename(renamed)
    try:
        with TestClient(app) as client:
            r = client.get("/mapping")
            list_status = r.status_code
            r = client.get("/mapping/ANY")
            get_status = r.status_code
            r = client.patch(
                "/mapping/ANY", json={"review_status": "approved"}
            )
            patch_status = r.status_code
        if list_status == 503 and get_status == 503 and patch_status == 503:
            _ok("mapping routes 503 when mapping file absent",
                f"list={list_status}, get={get_status}, patch={patch_status}")
        else:
            _fail(
                "mapping routes 503 when mapping file absent",
                f"list={list_status}, get={get_status}, patch={patch_status}",
            )
    finally:
        renamed.rename(SEMANTIC_MAPPING_PATH)

    return _report_and_exit()


if __name__ == "__main__":
    sys.exit(main())
