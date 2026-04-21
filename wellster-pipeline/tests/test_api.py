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

            # 14. /chat — Phase 6 hybrid agent.
            #
            # Only the deterministic recipe paths are exercised here
            # because the generic agent fallback needs a live Sonnet
            # call, which cannot run in CI / review sandboxes. Recipe
            # coverage is what Codex asked for: concrete evidence that
            # the three golden-path intents produce the right artifact
            # kind and the response shape matches the new contract.

            # 14a. Contract shape on a minimal request.
            r = client.post("/chat", json={"message": "Show BMI trends for Mounjaro patients"})
            if r.status_code != 200:
                _fail("/chat responds 200 on cohort prompt",
                      f"{r.status_code} {r.text[:200]}")
                return _report_and_exit()
            body = r.json()
            required_keys = {"steps", "reply", "artifact", "trace"}
            missing = required_keys - set(body.keys())
            if missing:
                _fail("/chat response has new contract keys",
                      f"missing: {missing}")
                return _report_and_exit()
            _ok("/chat response has new contract keys (steps/reply/artifact/trace)")

            # 14b. Cohort-trajectory recipe: dashboard artifact + recipe trace.
            art = body["artifact"]
            trace = body["trace"]
            if (art and art["kind"] == "cohort_trend"
                    and trace["recipe"] == "cohort_trajectory"
                    and trace["artifact_kind"] == "cohort_trend"):
                _ok("/chat cohort_trajectory recipe fires",
                    f"series={len(art['payload']['chart']['series'])}, "
                    f"kpis={len(art['payload']['kpis'])}, "
                    f"table_rows={len(art['payload']['table']['rows'])}")
            else:
                _fail("/chat cohort_trajectory recipe fires",
                      f"kind={art and art.get('kind')!r}, "
                      f"trace.recipe={trace.get('recipe')!r}")

            # 14c. Ops-alerts recipe on quality-issue wording.
            r = client.post("/chat", json={"message": "Which patients have data quality issues?"})
            if r.status_code != 200:
                _fail("/chat responds 200 on alerts prompt", str(r.status_code))
            else:
                body = r.json()
                art = body["artifact"]
                if (art and art["kind"] == "alerts_table"
                        and body["trace"]["recipe"] == "ops_alerts"):
                    _ok("/chat ops_alerts recipe fires",
                        f"kpis={len(art['payload']['kpis'])}, "
                        f"table_rows={len(art['payload']['table']['rows'])}")
                else:
                    _fail("/chat ops_alerts recipe fires",
                          f"kind={art and art.get('kind')!r}, "
                          f"trace.recipe={body['trace'].get('recipe')!r}")

            # 14d. Patient-FHIR recipe: use a real uid so the recipe
            # takes the success path (bundle built, kind=fhir_bundle).
            r = client.post(
                "/chat",
                json={"message": f"Generate a FHIR bundle for patient {uid}"},
            )
            if r.status_code != 200:
                _fail("/chat responds 200 on FHIR prompt", str(r.status_code))
            else:
                body = r.json()
                art = body["artifact"]
                if (art and art["kind"] == "fhir_bundle"
                        and body["trace"]["recipe"] == "patient_fhir_bundle"):
                    entries = art["payload"].get("entry", [])
                    _ok("/chat patient_fhir_bundle recipe fires",
                        f"entries={len(entries)}")
                else:
                    _fail("/chat patient_fhir_bundle recipe fires",
                          f"kind={art and art.get('kind')!r}, "
                          f"trace.recipe={body['trace'].get('recipe')!r}")

            # 14e. Empty message is a 400 (validation), not 500.
            r = client.post("/chat", json={"message": "   "})
            if r.status_code == 400:
                _ok("/chat rejects empty message with 400")
            else:
                _fail("/chat rejects empty message with 400",
                      f"got {r.status_code}")

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

    # 16. Malformed semantic_mapping.json must explicitly degrade (not 200 ok).
    # /health must report status="degraded" AND mapping_entries=0; the
    # status assertion was missing before — Codex caught the gap.
    SEMANTIC_MAPPING_PATH.write_text("{ this is not json", encoding="utf-8")
    try:
        with TestClient(app) as client:
            r_health = client.get("/health")
            r_mapping = client.get("/mapping")
        if r_health.status_code != 200:
            _fail("/health responds when mapping file malformed",
                  f"returned {r_health.status_code}")
        else:
            h = r_health.json()
            if h["status"] == "degraded" and h["mapping_entries"] == 0:
                _ok("/health explicitly reports degraded on malformed mapping",
                    f"status={h['status']}, mapping={h['mapping_entries']}")
            else:
                _fail("/health explicitly reports degraded on malformed mapping",
                      f"got status={h['status']}, mapping={h['mapping_entries']}")
        if r_mapping.status_code == 503:
            _ok("/mapping returns 503 on malformed mapping file")
        else:
            _fail("/mapping returns 503 on malformed mapping file",
                  f"got {r_mapping.status_code}")
    finally:
        # Restore from the backup snapshot we took at top of main()
        SEMANTIC_MAPPING_PATH.write_text(mapping_backup, encoding="utf-8")

    # 17. Atomic-write behaviour: after a write_mapping call, no sibling
    # .tmp leftover should remain. Proves the rename step happened.
    tmp_leftovers = list(SEMANTIC_MAPPING_PATH.parent.glob(".semantic_mapping.*.tmp"))
    if not tmp_leftovers:
        _ok("write_mapping leaves no .tmp leftover",
            "temp-file + os.replace pattern intact")
    else:
        _fail("write_mapping leaves no .tmp leftover",
              f"found: {[p.name for p in tmp_leftovers]}")

    # 18. Concurrent writers+readers: every read must resolve to EITHER
    # the previous complete document OR the new complete document —
    # never anything else.
    #
    # Readers go through `atomic_read_json` — the same retrying path
    # `deps.read_mapping` uses in production. This tests two things at
    # once: (a) the retry logic actually suppresses the Windows
    # PermissionError race during concurrent writes, and (b) that fix
    # is on the production code path, not just the test.
    #
    # `threading.excepthook` is the second belt: if ANY unhandled
    # exception escapes a worker thread (because a future regression
    # bypasses atomic_read_json, or a new thread is added without
    # defensive catching), it is captured into `thread_escapes` and
    # fails the assertion below. Previously such escapes printed a
    # traceback to stderr but did not fail the test — this is exactly
    # the false-green pattern Codex flagged on the writer side first
    # (Windows PermissionError leaked past the bare except) and now
    # on the reader side (same race, opposite direction).
    import threading

    from src.io_utils import AtomicReadError, atomic_read_json

    versions = [
        {"__stress_marker__": "VERSION_A", "payload": "A" * 100},
        {"__stress_marker__": "VERSION_B", "payload": "B" * 100},
    ]
    known_markers = {v["__stress_marker__"] for v in versions}

    # Seed with VERSION_A so readers have a valid baseline.
    state.write_mapping(versions[0])

    partial_or_unknown: list[str] = []
    writer_errors: list[str] = []
    thread_escapes: list[str] = []
    total_reads = 0
    stop_flag = {"stop": False}

    previous_excepthook = threading.excepthook

    def capture_thread_exception(args) -> None:  # threading.ExceptHookArgs
        thread_escapes.append(
            f"thread {args.thread.name}: "
            f"{args.exc_type.__name__}: {args.exc_value}"
        )

    threading.excepthook = capture_thread_exception

    def writer_worker() -> None:
        # Previous version of this test silently swallowed writer
        # exceptions, which let Windows PermissionError on os.replace
        # crash the thread while the test still reported green. Now
        # surface every exception through writer_errors so the test
        # actually fails if the atomic write regresses.
        for i in range(100):
            if stop_flag["stop"]:
                break
            try:
                with state.mapping_lock():
                    state.write_mapping(versions[i % 2])
            except Exception as exc:
                writer_errors.append(f"iter {i}: {type(exc).__name__}: {exc}")

    def strict_reader_worker() -> None:
        nonlocal total_reads
        for _ in range(500):
            if stop_flag["stop"]:
                break
            total_reads += 1
            try:
                parsed = atomic_read_json(SEMANTIC_MAPPING_PATH)
            except FileNotFoundError:
                partial_or_unknown.append("file missing during read")
                continue
            except json.JSONDecodeError as e:
                partial_or_unknown.append(
                    f"partial JSON seen: err={e.msg}"
                )
                continue
            except AtomicReadError as e:
                partial_or_unknown.append(
                    f"permission lock did not clear after retries: {e}"
                )
                continue
            marker = parsed.get("__stress_marker__")
            if marker not in known_markers:
                partial_or_unknown.append(
                    f"unknown marker {marker!r} (parse ok, content wrong)"
                )

    try:
        t_w = threading.Thread(target=writer_worker, name="writer")
        t_r1 = threading.Thread(target=strict_reader_worker, name="reader-1")
        t_r2 = threading.Thread(target=strict_reader_worker, name="reader-2")
        t_w.start(); t_r1.start(); t_r2.start()
        t_w.join(); t_r1.join(); t_r2.join()
        stop_flag["stop"] = True
    finally:
        threading.excepthook = previous_excepthook

    if not partial_or_unknown:
        _ok(
            "concurrent readers only see complete versions (strict)",
            f"100 writes × {total_reads} reads; every read matched a known marker",
        )
    else:
        _fail(
            "concurrent readers only see complete versions (strict)",
            f"{len(partial_or_unknown)} anomalies; first: {partial_or_unknown[0]}",
        )

    # The writer must survive 100 iterations against active readers.
    # Windows PermissionError on os.replace is caught and retried by
    # `atomic_write_json` in src/io_utils.py; any remaining exception
    # surfaces here.
    if not writer_errors:
        _ok("writer survives 100 iters against active readers")
    else:
        _fail(
            "writer survives 100 iters against active readers",
            f"{len(writer_errors)} writer errors; first: {writer_errors[0]}",
        )

    # Belt-and-suspenders: catch any OTHER unhandled exception that
    # escaped a worker thread. Before this guard, a PermissionError on
    # the reader side would print a traceback from the thread and exit
    # cleanly — green test, live race. Now the test fails honestly.
    if not thread_escapes:
        _ok("no unhandled exceptions escaped any stress-test thread")
    else:
        _fail(
            "no unhandled exceptions escaped any stress-test thread",
            f"{len(thread_escapes)} escapes; first: {thread_escapes[0]}",
        )

    # Restore backup one more time after the stress loop
    SEMANTIC_MAPPING_PATH.write_text(mapping_backup, encoding="utf-8")

    # 19. PatientRecord survives pd.NA demographic fields (Codex low finding)
    import pandas as pd
    from src.datastore import PatientRecord

    na_row = pd.Series({
        "user_id": 999999,
        "gender": pd.NA,
        "current_age": pd.NA,
        "total_treatments": pd.NA,
        "active_treatments": pd.NA,
        "current_medication": pd.NA,
        "current_dosage": pd.NA,
        "tenure_days": pd.NA,
        "latest_bmi": pd.NA,
        "earliest_bmi": pd.NA,
        "bmi_change": pd.NA,
        "first_order_date": pd.NaT,
        "latest_activity_date": pd.NaT,
    })
    try:
        rec = PatientRecord.from_row(na_row)
        if (rec.user_id == 999999
                and rec.gender == ""
                and rec.current_age == 0
                and rec.tenure_days is None
                and rec.latest_bmi is None):
            _ok("PatientRecord.from_row tolerates pd.NA",
                "all missing fields cleanly coerced")
        else:
            _fail("PatientRecord.from_row tolerates pd.NA",
                  f"got gender={rec.gender!r}, age={rec.current_age}, "
                  f"tenure={rec.tenure_days}, bmi={rec.latest_bmi}")
    except Exception as e:
        _fail("PatientRecord.from_row tolerates pd.NA",
              f"raised {type(e).__name__}: {e}")

    return _report_and_exit()


if __name__ == "__main__":
    sys.exit(main())
