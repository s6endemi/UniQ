"""Chat eval harness.

Runs `tests/chat_eval_cases.json` against the /chat endpoint and
emits a per-case, per-assertion report. Deliberately **does not**
fail the suite at any threshold — Codex sets those when comparing
v1 to v2.

Why the harness looks like this
-------------------------------

- The harness uses FastAPI's TestClient so it runs offline, in-process,
  against whatever agent `/chat` is currently wired to. No ports, no
  uvicorn, no flakiness from a live server.
- Per-case pass/fail is computed from externally observable properties
  (artifact kind, SQL count, reply terms, artifact payload terms,
  latency). It does NOT look at internal recipe names, so the same
  cases work across v1 (recipe-first) and v2 (unified agent).
- Generic-agent cases fire a real Sonnet call. That means runs cost
  money and take time (~6–14 s per generic-path case). 16 cases run
  in roughly 1–3 minutes end-to-end.
- Output shape is stable: a structured JSON report, plus a
  human-scannable stdout summary. Stable enough for Codex to diff v1
  vs v2 runs by piping both reports through any diff tool.

Usage
-----

    python tests/run_chat_eval.py
    python tests/run_chat_eval.py --out tests/eval_report.json
    python tests/run_chat_eval.py --filter positive
    python tests/run_chat_eval.py --filter neg_avg_bmi
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

import config
from src.api.deps import SEMANTIC_MAPPING_PATH
from src.api.main import app


CASES_PATH = Path(__file__).parent / "chat_eval_cases.json"


# ---- Assertion helpers ---------------------------------------------------


def _assert_artifact_kind(case: dict, actual_kind: str | None) -> dict:
    expected = case.get("expected_artifact_kind")
    return {
        "expected": expected,
        "actual": actual_kind,
        "pass": actual_kind == expected,
    }


def _assert_disallowed(case: dict, actual_kind: str | None) -> dict:
    disallowed = list(case.get("disallowed_artifact_kinds") or [])
    return {
        "disallowed": disallowed,
        "actual": actual_kind,
        "pass": actual_kind not in disallowed,
    }


def _assert_sql_count(case: dict, actual: int) -> dict:
    lo = int(case.get("min_sql_count", 0))
    hi = int(case.get("max_sql_count", 99))
    return {
        "min": lo,
        "max": hi,
        "actual": actual,
        "pass": lo <= actual <= hi,
    }


def _assert_fhir_tool(case: dict, artifact: dict | None) -> dict:
    required = bool(case.get("requires_fhir_tool", False))
    used = artifact is not None and artifact.get("kind") == "fhir_bundle"
    return {
        "required": required,
        "used": used,
        "pass": (not required) or used,
    }


def _assert_reply_contains(case: dict, reply: str) -> dict:
    required = list(case.get("must_contain_reply_terms") or [])
    lower = reply.lower()
    missing = [t for t in required if t.lower() not in lower]
    return {
        "required": required,
        "missing": missing,
        "pass": not missing,
    }


def _assert_reply_excludes(case: dict, reply: str) -> dict:
    forbidden = list(case.get("must_not_contain_reply_terms") or [])
    lower = reply.lower()
    present = [t for t in forbidden if t.lower() in lower]
    return {
        "forbidden": forbidden,
        "present": present,
        "pass": not present,
    }


def _assert_artifact_contains(case: dict, artifact: dict | None) -> dict:
    required = list(case.get("artifact_must_contain_terms") or [])
    haystack = json.dumps(artifact, ensure_ascii=False).lower() if artifact else ""
    missing = [t for t in required if t.lower() not in haystack]
    return {
        "required": required,
        "missing": missing,
        "pass": not missing,
    }


def _assert_latency(case: dict, latency_ms: int) -> dict:
    budget = int(case.get("latency_budget_ms", 30000))
    return {
        "budget_ms": budget,
        "actual_ms": latency_ms,
        "pass": latency_ms <= budget,
    }


def compute_assertions(case: dict, body: dict, latency_ms: int) -> dict[str, dict]:
    artifact = body.get("artifact")
    trace = body.get("trace") or {}
    reply = body.get("reply") or ""
    kind = artifact.get("kind") if artifact else None
    sql_count = len(trace.get("sql") or [])

    return {
        "artifact_kind": _assert_artifact_kind(case, kind),
        "disallowed_artifact_kind": _assert_disallowed(case, kind),
        "sql_count": _assert_sql_count(case, sql_count),
        "fhir_tool": _assert_fhir_tool(case, artifact),
        "reply_must_contain": _assert_reply_contains(case, reply),
        "reply_must_not_contain": _assert_reply_excludes(case, reply),
        "artifact_must_contain": _assert_artifact_contains(case, artifact),
        "latency": _assert_latency(case, latency_ms),
    }


# ---- Per-case runner -----------------------------------------------------


def run_case(client: TestClient, case: dict) -> dict[str, Any]:
    start = time.monotonic()
    try:
        resp = client.post("/chat", json={"message": case["prompt"]})
    except Exception as exc:  # noqa: BLE001 — surface anything to the report
        return {
            "id": case["id"],
            "category": case["category"],
            "failure_mode": case["failure_mode"],
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": int((time.monotonic() - start) * 1000),
            "assertions": {},
            "actual": {},
        }
    latency_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code != 200:
        return {
            "id": case["id"],
            "category": case["category"],
            "failure_mode": case["failure_mode"],
            "status": "http_error",
            "http_status": resp.status_code,
            "detail": resp.text[:500],
            "latency_ms": latency_ms,
            "assertions": {},
            "actual": {},
        }

    body = resp.json()
    assertions = compute_assertions(case, body, latency_ms)
    all_pass = all(a["pass"] for a in assertions.values())

    artifact = body.get("artifact")
    trace = body.get("trace") or {}
    return {
        "id": case["id"],
        "category": case["category"],
        "failure_mode": case["failure_mode"],
        "status": "pass" if all_pass else "fail",
        "http_status": 200,
        "latency_ms": latency_ms,
        "actual": {
            "artifact_kind": artifact.get("kind") if artifact else None,
            "sql_count": len(trace.get("sql") or []),
            "intent": trace.get("intent"),
            "recipe": trace.get("recipe"),
            "reply_preview": (body.get("reply") or "")[:240],
        },
        "assertions": assertions,
    }


# ---- Report printing -----------------------------------------------------


def _short_fail_list(result: dict[str, Any]) -> str:
    return ", ".join(
        name for name, a in result["assertions"].items() if not a["pass"]
    )


def print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    http_err = sum(1 for r in results if r["status"] == "http_error")
    exc_err = sum(1 for r in results if r["status"] == "error")

    by_cat: dict[str, list[dict]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    print()
    print("=" * 68)
    print(f"Overall: {passed}/{total} pass  ({http_err} http_error, {exc_err} exception)")
    print()
    print("By category:")
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        ok = sum(1 for r in rs if r["status"] == "pass")
        print(f"  {cat:15s}  {ok:2d}/{len(rs):2d}")

    failing = [r for r in results if r["status"] not in ("pass",)]
    if failing:
        print()
        print("Failing cases:")
        for r in failing:
            if r["status"] == "pass":
                continue
            failed_assertions = _short_fail_list(r) if r["assertions"] else r["status"]
            print(
                f"  [{r['failure_mode']:38s}] {r['id']:30s}  "
                f"actual_kind={r['actual'].get('artifact_kind')!r}  "
                f"failed: {failed_assertions}"
            )

    latencies = [r["latency_ms"] for r in results if r["status"] in ("pass", "fail")]
    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[len(latencies_sorted) // 2]
        p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        print()
        print(f"Latency: p50={p50}ms, p95={p95}ms, max={max(latencies_sorted)}ms")


# ---- Main ---------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Chat eval runner.")
    ap.add_argument("--cases", type=str, default=str(CASES_PATH))
    ap.add_argument("--out", type=str, default=str(config.OUTPUT_DIR / "chat_eval_report.json"),
                    help="Write full JSON report to this path.")
    ap.add_argument("--filter", type=str, default=None,
                    help="Substring match against case id or category.")
    ap.add_argument("--agent-mode", type=str, default=None,
                    choices=["v1", "v2"],
                    help="Temporarily force UNIQ_AGENT_MODE for this run.")
    args = ap.parse_args()

    # Gate early on missing artifacts so we do not blame the agent for
    # a degraded FastAPI state.
    if not config.MAPPING_TABLE.exists() or not SEMANTIC_MAPPING_PATH.exists():
        print("SKIP: pipeline artifacts missing — run `python pipeline.py` first.")
        return 0

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.filter:
        needle = args.filter.lower()
        cases = [c for c in cases
                 if needle in c["id"].lower() or needle in c["category"].lower()]
        if not cases:
            print(f"No cases match filter {args.filter!r}.")
            return 1

    print(f"Running {len(cases)} case{'s' if len(cases) != 1 else ''} against /chat…")
    print(f"  (cases file: {args.cases})")
    if args.agent_mode:
        import os
        os.environ["UNIQ_AGENT_MODE"] = args.agent_mode
        print(f"  (agent mode: {args.agent_mode})")
    print()

    results: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for i, case in enumerate(cases, 1):
            marker = "…"
            print(f"  [{i:2d}/{len(cases)}] {case['id']:34s} {marker}  ",
                  end="", flush=True)
            result = run_case(client, case)
            results.append(result)
            status_tag = {
                "pass": "OK",
                "fail": "FAIL",
                "http_error": "HTTP",
                "error": "EXC",
            }.get(result["status"], "?")
            print(f"{status_tag:5s}  {result['latency_ms']:>6}ms  "
                  f"kind={result['actual'].get('artifact_kind')!r}")

    print_summary(results)

    report = {
        "meta": {
            "generated_at": time.time(),
            "cases_file": args.cases,
            "total": len(results),
            "passed": sum(1 for r in results if r["status"] == "pass"),
        },
        "results": results,
    }
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nJSON report: {out_path}")
        try:
            from src.materialization_manifest import write_manifest

            write_manifest(save=True)
            print("materialization manifest updated with eval result")
        except Exception as exc:
            print(
                "warning: materialization manifest not updated "
                f"({type(exc).__name__}: {exc})"
            )

    # Always exit 0 — this harness intentionally does not fail CI.
    # Codex owns the threshold assertions for v1-vs-v2 comparison.
    return 0


if __name__ == "__main__":
    sys.exit(main())
