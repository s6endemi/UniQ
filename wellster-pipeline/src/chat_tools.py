"""Tool implementations for the Phase 6 chat agent.

Thin wrappers around DuckDBQueryService + export_fhir_bundle so the
Anthropic tool-use loop has a clean surface. The surface is deliberately
minimal — the agent works better with five well-described tools than
fifteen vaguely-defined ones.

Tool schemas are defined in `chat_prompts.py`; this module only
implements the functions that run when Claude emits a `tool_use` block.
Every executor returns a JSON-serialisable dict so the outer loop can
round-trip it straight into the Messages API as `tool_result` content.

One non-obvious choice: `execute_sql` also captures and returns a small
preview of the result, plus full column/row info, in one call. The
previous design had a separate `sample_rows` step, which doubled the
tool round-trips with no new information. We still expose `sample_rows`
for schema exploration (Claude can peek at a table before writing SQL),
but once an agent generates a query it gets everything it needs back in
a single invocation.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd

from src.datastore import UnifiedDataRepository
from src.export_fhir import export_fhir_bundle
from src.query_service import DuckDBQueryService, QueryGuardrailViolation


class ChatToolError(Exception):
    """Raised when a tool invocation is malformed (bad args, missing repo)."""


def _jsonable(value: Any) -> Any:
    """Coerce pandas/numpy scalars to plain Python so json.dumps works.

    Claude tool-result content is stringified JSON, so any leftover
    numpy.int64 or pd.Timestamp would blow up the Messages API call.
    """
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    # numpy scalars expose .item()
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return str(value)


def _rows_jsonable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: _jsonable(v) for k, v in r.items()} for r in rows]


# ---- Tool executors -------------------------------------------------------


def tool_get_schema_context(query: DuckDBQueryService, _args: dict) -> dict[str, Any]:
    """Return the full schema + category list in one shot.

    The agent almost always needs both at once; splitting them forces an
    extra tool round-trip. Keeping this combined tool small means it fits
    the Anthropic prompt cache boundary with room to spare.
    """
    return {
        "tables": query.schema(),
        "categories": query.list_categories(),
        "notes": {
            "primary_table": "survey_unified",
            "patient_id_col": "user_id",
            "bmi_table": "bmi_timeline",
            "medication_table": "medication_history",
            "category_col": "clinical_category",
        },
    }


def tool_sample_rows(query: DuckDBQueryService, args: dict) -> dict[str, Any]:
    table = args.get("table")
    if not isinstance(table, str):
        raise ChatToolError("`table` (string) is required")
    n = int(args.get("n", 5))
    try:
        rows = query.sample(table, n=n)
    except QueryGuardrailViolation as exc:
        return {"error": str(exc)}
    return {"table": table, "rows": _rows_jsonable(rows), "row_count": len(rows)}


def tool_execute_sql(query: DuckDBQueryService, args: dict) -> dict[str, Any]:
    sql = args.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise ChatToolError("`sql` (non-empty string) is required")
    try:
        result = query.execute_sql(sql)
    except QueryGuardrailViolation as exc:
        return {"error": f"Query rejected: {exc}", "sql": sql}
    except Exception as exc:  # noqa: BLE001 — surface DuckDB errors to the agent
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "sql": sql,
        }
    # Trim the preview to keep the model context lean; full rows live in
    # the outer agent's run-log and are used by the artifact builder.
    preview = result.rows[:20]
    return {
        "sql": sql,
        "columns": result.columns,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "preview": _rows_jsonable(preview),
    }


def tool_build_fhir_bundle(
    repo: UnifiedDataRepository,
    args: dict,
) -> dict[str, Any]:
    """Assemble a single-patient FHIR R4 bundle.

    The full bundle is large; we return a summary *plus* the full bundle
    back to the caller so the outer loop can attach it as the artifact
    payload. Claude only needs the summary for its reasoning.
    """
    user_id = args.get("user_id")
    if user_id is None:
        raise ChatToolError("`user_id` is required")
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise ChatToolError(f"`user_id` must be an integer, got {user_id!r}")

    if repo.patient(user_id_int) is None:
        return {"error": f"Unknown user_id {user_id_int}", "user_id": user_id_int}

    patients_df = repo.patients[repo.patients["user_id"] == user_id_int]
    bmi_df = repo.bmi_timeline[repo.bmi_timeline["user_id"] == user_id_int]
    med_df = repo.medication_history[repo.medication_history["user_id"] == user_id_int]
    survey_df = repo.survey[repo.survey["user_id"] == user_id_int]

    bundle = export_fhir_bundle(patients_df, bmi_df, med_df, survey_df)
    counts: dict[str, int] = {}
    for entry in bundle.get("entry", []):
        rtype = entry.get("resource", {}).get("resourceType", "Unknown")
        counts[rtype] = counts.get(rtype, 0) + 1

    return {
        "user_id": user_id_int,
        "resource_total": bundle.get("total", len(bundle.get("entry", []))),
        "resource_counts": counts,
        "bundle": bundle,
    }


# ---- Dispatcher -----------------------------------------------------------


ToolExecutor = Callable[[dict[str, Any]], dict[str, Any]]


def build_tool_registry(
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> dict[str, ToolExecutor]:
    """Bind the service + repo into a name → executor mapping.

    Separated from the executor definitions so the agent loop can stay
    framework-free. The returned mapping is fresh per request (closures
    are cheap) so we avoid leaking state between sessions.
    """
    return {
        "get_schema_context": lambda a: tool_get_schema_context(query, a),
        "sample_rows": lambda a: tool_sample_rows(query, a),
        "execute_sql": lambda a: tool_execute_sql(query, a),
        "build_fhir_bundle": lambda a: tool_build_fhir_bundle(repo, a),
    }


def encode_tool_result(payload: dict[str, Any]) -> str:
    """JSON-stringify a tool result for the Messages API.

    Anthropic's `tool_result` content accepts either a string or a list of
    content blocks; we always pass a string and let the model re-parse.
    """
    return json.dumps(payload, ensure_ascii=False, default=str)
