"""Unified v2 chat agent.

One Sonnet tool loop handles intent understanding, SQL, and artifact-family
selection. The model never emits raw artifact payloads; it only references SQL
result handles through terminal present_* tools. The backend resolves those
handles into validated builders.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import pandas as pd
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.api.models import ChartSeries, ChatArtifact, ChatResponse, ChatTrace, Kpi
from src.artifact_builders import (
    build_alerts_table,
    build_cohort_trend,
    build_degraded_table_from_df,
    build_empty_table,
    build_fhir_bundle,
    build_patient_record,
    build_table,
    df_to_table,
    humanise,
)
from src.chat_prompts_v2 import (
    CHAT_V2_MAX_TOKENS,
    CHAT_V2_MAX_TOOL_ITERATIONS,
    CHAT_V2_MODEL,
    CHAT_V2_TEMPERATURE,
    V2_TOOLS,
    system_prompt_with_cache_v2,
)
from src.chat_tools import ChatToolError, encode_tool_result, tool_build_fhir_bundle
from src.chat_v2_models import (
    ExecuteSqlInput,
    PresentAlertsTableInput,
    PresentCohortTrendInput,
    PresentFhirBundleInput,
    PresentPatientRecordInput,
    PresentTableInput,
    SampleRowsInput,
)
from src.datastore import UnifiedDataRepository
from src.query_service import DuckDBQueryService, QueryGuardrailViolation


TERMINAL_TOOLS: set[str] = {
    "present_cohort_trend",
    "present_alerts_table",
    "present_fhir_bundle",
    "present_patient_record",
    "present_table",
}


@dataclass
class SqlHandleResult:
    handle: str
    sql: str
    df: pd.DataFrame
    columns: list[str]
    row_count: int
    truncated: bool


@dataclass
class TerminalResult:
    artifact: ChatArtifact | None
    reply_text: str
    kind: str | None


@dataclass
class _AgentV2State:
    handles: dict[str, SqlHandleResult] = field(default_factory=dict)
    executed_sql: list[str] = field(default_factory=list)
    row_counts: list[int] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    sampled_tables: list[str] = field(default_factory=list)
    last_df: pd.DataFrame | None = None
    last_handle: str | None = None


def run_chat_agent_v2(
    message: str,
    *,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
    client: Any | None = None,
) -> ChatResponse:
    """Unified `/chat` runtime selected by `UNIQ_AGENT_MODE=v2`."""
    if client is None and not config.ANTHROPIC_API_KEY:
        return _degraded_no_key_response_v2(query)

    client = client or anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    state = _AgentV2State()
    system_blocks = system_prompt_with_cache_v2(
        schema=query.schema(),
        categories=query.list_categories(),
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": message}]

    final_text: str | None = None
    terminal: TerminalResult | None = None

    for _ in range(CHAT_V2_MAX_TOOL_ITERATIONS):
        try:
            response = client.messages.create(
                model=CHAT_V2_MODEL,
                max_tokens=CHAT_V2_MAX_TOKENS,
                temperature=CHAT_V2_TEMPERATURE,
                system=system_blocks,
                tools=V2_TOOLS,
                messages=messages,
            )
        except anthropic.APIError as exc:
            return _degraded_api_error_response_v2(exc)

        if response.stop_reason == "end_turn":
            final_text = _extract_text(response.content)
            break

        if response.stop_reason != "tool_use":
            final_text = _extract_text(response.content)
            break

        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            final_text = _extract_text(response.content)
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results: list[dict[str, Any]] = []

        for block in tool_uses:
            tool_name = str(block.name)
            args = dict(block.input or {})
            if tool_name in TERMINAL_TOOLS:
                terminal = _execute_terminal_tool(
                    state=state,
                    tool_name=tool_name,
                    args=args,
                    repo=repo,
                )
                break

            payload = _execute_data_tool(
                state=state,
                tool_name=tool_name,
                args=args,
                query=query,
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": encode_tool_result(payload),
                }
            )

        if terminal is not None:
            break

        messages.append({"role": "user", "content": tool_results})

    if terminal is not None:
        if terminal.kind is not None:
            state.steps.append(f"Selected artifact · {terminal.kind}")
        return ChatResponse(
            steps=state.steps,
            reply=terminal.reply_text,
            artifact=terminal.artifact,
            trace=ChatTrace(
                intent="unified_agent",
                recipe=None,
                agent_mode="v2",
                sql=state.executed_sql,
                row_counts=state.row_counts,
                artifact_kind=terminal.kind,
                tool_log=state.tool_log,
            ),
        )

    artifact = _fallback_artifact_from_state(state, fallback_title=_short_title(message))
    if artifact is not None:
        state.steps.append(f"Selected artifact · {artifact.kind}")

    reply = (final_text or "").strip()
    if not reply:
        if not state.executed_sql:
            reply = "I can answer questions about cohorts, quality issues, demographics, and FHIR exports."
            if not state.steps:
                state.steps.append("Answered directly · no data access needed")
        else:
            reply = _default_reply_from_state(state)

    return ChatResponse(
        steps=state.steps or ["Answered directly · no data access needed"],
        reply=reply,
        artifact=artifact,
        trace=ChatTrace(
            intent="unified_agent",
            recipe=None,
            agent_mode="v2",
            sql=state.executed_sql,
            row_counts=state.row_counts,
            artifact_kind=artifact.kind if artifact else None,
            tool_log=state.tool_log,
        ),
    )


def _execute_data_tool(
    *,
    state: _AgentV2State,
    tool_name: str,
    args: dict[str, Any],
    query: DuckDBQueryService,
) -> dict[str, Any]:
    try:
        if tool_name == "execute_sql":
            payload = _tool_execute_sql_v2(state, query, args)
        elif tool_name == "sample_rows":
            payload = _tool_sample_rows_v2(state, query, args)
        else:
            raise ChatToolError(f"Unknown tool {tool_name!r}")
    except ChatToolError as exc:
        payload = {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        payload = {"error": f"{type(exc).__name__}: {exc}"}

    status = "error" if "error" in payload else "ok"
    log_entry = {
        "tool": tool_name,
        "args": args,
        "status": status,
    }
    if "handle" in payload:
        log_entry["handle"] = payload["handle"]
    if "row_count" in payload:
        log_entry["row_count"] = payload["row_count"]
    if "error" in payload:
        log_entry["error"] = payload["error"]
        state.steps.append(f"Tool error · {tool_name} · {str(payload['error'])[:80]}")
    state.tool_log.append(log_entry)
    return payload


def _tool_execute_sql_v2(
    state: _AgentV2State,
    query: DuckDBQueryService,
    args: dict[str, Any],
) -> dict[str, Any]:
    parsed = ExecuteSqlInput.model_validate(args)
    if parsed.handle in state.handles:
        raise ChatToolError(
            f"Handle {parsed.handle!r} already exists. Use a fresh snake_case handle."
        )

    try:
        result = query.execute_sql(parsed.sql)
    except QueryGuardrailViolation as exc:
        return {"error": f"Query rejected: {exc}", "handle": parsed.handle, "sql": parsed.sql}
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "handle": parsed.handle,
            "sql": parsed.sql,
        }

    df = result.to_dataframe()
    state.handles[parsed.handle] = SqlHandleResult(
        handle=parsed.handle,
        sql=parsed.sql,
        df=df,
        columns=result.columns,
        row_count=result.row_count,
        truncated=result.truncated,
    )
    state.executed_sql.append(parsed.sql)
    state.row_counts.append(result.row_count)
    state.last_df = df
    state.last_handle = parsed.handle
    state.steps.append(
        f"Queried substrate · {parsed.handle} · {result.row_count:,} row{'s' if result.row_count != 1 else ''}"
    )
    return {
        "handle": parsed.handle,
        "sql": parsed.sql,
        "columns": result.columns,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "preview": result.rows[:20],
    }


def _tool_sample_rows_v2(
    state: _AgentV2State,
    query: DuckDBQueryService,
    args: dict[str, Any],
) -> dict[str, Any]:
    parsed = SampleRowsInput.model_validate(args)
    rows = query.sample(parsed.table, n=parsed.n)
    state.sampled_tables.append(parsed.table)
    state.steps.append(f"Sampled · {parsed.table}")
    return {"table": parsed.table, "rows": rows, "row_count": len(rows)}


def _execute_terminal_tool(
    *,
    state: _AgentV2State,
    tool_name: str,
    args: dict[str, Any],
    repo: UnifiedDataRepository,
) -> TerminalResult:
    raw_reply = _coerce_reply_text(args)
    try:
        if tool_name == "present_cohort_trend":
            parsed = PresentCohortTrendInput.model_validate(args)
            artifact = _present_cohort_trend(state, parsed)
        elif tool_name == "present_alerts_table":
            parsed = PresentAlertsTableInput.model_validate(args)
            artifact = _present_alerts_table(state, parsed)
        elif tool_name == "present_fhir_bundle":
            parsed = PresentFhirBundleInput.model_validate(args)
            artifact = _present_fhir_bundle(repo, parsed)
        elif tool_name == "present_patient_record":
            parsed = PresentPatientRecordInput.model_validate(args)
            artifact = _present_patient_record(repo, parsed)
        elif tool_name == "present_table":
            parsed = PresentTableInput.model_validate(args)
            artifact = _present_table(state, parsed)
        else:
            raise ChatToolError(f"Unknown terminal tool {tool_name!r}")
    except (ValidationError, KeyError, ValueError, ChatToolError) as exc:
        fallback_title = _fallback_title_from_args(args, tool_name)
        if tool_name == "present_fhir_bundle":
            # Keep the UX clean: no raw Pydantic / exception strings in the
            # user-facing surface. Internal detail lives in the tool_log.
            artifact = build_empty_table(
                title=fallback_title,
                subtitle="Patient FHIR export unavailable",
            )
            reply = (
                "I could not assemble a FHIR bundle for that request. "
                "Please re-check the patient identifier and try again."
            )
        elif tool_name == "present_patient_record":
            artifact = build_empty_table(
                title=fallback_title,
                subtitle="Patient record unavailable",
            )
            reply = (
                "I could not open that patient record. Please re-check the "
                "patient identifier and try again."
            )
        else:
            artifact = _degrade_terminal_failure(
                state=state,
                tool_name=tool_name,
                reason=f"{type(exc).__name__}: {exc}",
                fallback_title=fallback_title,
            )
            reply = raw_reply or _default_reply_from_state(state)
        state.steps.append(f"Presentation degraded · {tool_name}")
        state.tool_log.append(
            {
                "tool": tool_name,
                "args": args,
                "status": "degraded",
                "error": f"{type(exc).__name__}: {exc}",
                "artifact_kind": artifact.kind if artifact else None,
            }
        )
        return TerminalResult(
            artifact=artifact,
            reply_text=reply,
            kind=artifact.kind if artifact else None,
        )

    state.tool_log.append(
        {
            "tool": tool_name,
            "args": args,
            "status": "ok",
            "artifact_kind": artifact.kind if artifact else None,
        }
    )
    return TerminalResult(
        artifact=artifact,
        reply_text=raw_reply or _default_reply_from_state(state),
        kind=artifact.kind if artifact else None,
    )


def _present_cohort_trend(
    state: _AgentV2State,
    parsed: PresentCohortTrendInput,
) -> ChatArtifact:
    trend = _require_handle(state, parsed.trend_handle)
    trend_df = trend.df.copy()
    if parsed.x_column not in trend_df.columns:
        raise KeyError(f"x_column {parsed.x_column!r} not found in handle {parsed.trend_handle!r}")

    series = []
    for spec in parsed.series:
        if spec.y_column not in trend_df.columns:
            raise KeyError(
                f"series column {spec.y_column!r} not found in handle {parsed.trend_handle!r}"
            )
        series.append(
            ChartSeries(
                name=spec.name,
                points=[float(v) for v in trend_df[spec.y_column].tolist()],
            )
        )

    x_labels = _format_x_labels(trend_df[parsed.x_column].tolist(), parsed.x_column)
    table_payload = df_to_table(
        _require_handle(state, parsed.table_handle).df if parsed.table_handle else trend_df,
        limit=50,
    )
    kpis = _derive_cohort_kpis(trend_df, series)
    return build_cohort_trend(
        title=parsed.title,
        subtitle=parsed.subtitle,
        kpis=kpis,
        chart_title=parsed.chart_title,
        chart_subtitle=parsed.chart_subtitle,
        x_labels=x_labels,
        y_label=parsed.y_label,
        series=series,
        table=table_payload,
    )


def _present_alerts_table(
    state: _AgentV2State,
    parsed: PresentAlertsTableInput,
) -> ChatArtifact:
    handle = _require_handle(state, parsed.table_handle)
    df = handle.df.copy()
    kpis = _derive_alert_kpis(df, parsed.severity_column, parsed.total_count)
    table = df_to_table(
        df,
        emphasis={parsed.severity_column} if parsed.severity_column in df.columns else None,
        align_overrides={"description": "left", "details": "left"},
        limit=50,
    )
    return build_alerts_table(
        title=parsed.title,
        subtitle=parsed.subtitle,
        kpis=kpis,
        table=table,
    )


def _present_fhir_bundle(
    repo: UnifiedDataRepository,
    parsed: PresentFhirBundleInput,
) -> ChatArtifact:
    payload = tool_build_fhir_bundle(repo, {"user_id": parsed.user_id})
    if "error" in payload:
        raise ChatToolError(str(payload["error"]))
    return build_fhir_bundle(
        title=parsed.title,
        subtitle=parsed.subtitle,
        bundle=payload["bundle"],
    )


def _present_patient_record(
    repo: UnifiedDataRepository,
    parsed: PresentPatientRecordInput,
) -> ChatArtifact:
    return build_patient_record(
        repo=repo,
        user_id=parsed.user_id,
        title=parsed.title,
        subtitle=parsed.subtitle,
    )


def _present_table(
    state: _AgentV2State,
    parsed: PresentTableInput,
) -> ChatArtifact:
    handle = _require_handle(state, parsed.table_handle)
    df = handle.df.copy()
    if df.empty:
        return build_empty_table(title=parsed.title, subtitle=parsed.subtitle)
    kpis = _derive_table_kpis(df)
    return build_table(
        title=parsed.title,
        subtitle=parsed.subtitle,
        kpis=kpis,
        table=df_to_table(df, limit=50),
    )


def _require_handle(state: _AgentV2State, handle: str | None) -> SqlHandleResult:
    if not handle:
        raise ChatToolError("A result handle is required for this present_* tool.")
    if handle not in state.handles:
        raise ChatToolError(
            f"Unknown handle {handle!r}. Available: {sorted(state.handles)}"
        )
    return state.handles[handle]


def _derive_cohort_kpis(trend_df: pd.DataFrame, series: list[ChartSeries]) -> list[Kpi]:
    kpis: list[Kpi] = []
    if "n_patients" in trend_df.columns and not trend_df["n_patients"].empty:
        n_patients = int(float(trend_df["n_patients"].max()))
        kpis.append(Kpi(label="Cohort size", value=f"{n_patients:,}"))

    if series and series[0].points:
        first = float(series[0].points[0])
        last = float(series[0].points[-1])
        delta = last - first
        kpis.append(Kpi(label="Baseline", value=f"{first:.1f}"))
        kpis.append(Kpi(label="Latest", value=f"{last:.1f}", delta=f"{delta:+.1f}"))
    elif not kpis:
        kpis.append(Kpi(label="Rows", value=f"{len(trend_df):,}"))
    return kpis[:3]


def _derive_alert_kpis(
    df: pd.DataFrame,
    severity_column: str,
    total_override: int | None = None,
) -> list[Kpi]:
    # `total_override` wins when provided so a `LIMIT 50` query no longer
    # under-reports the substrate — Claude feeds in the real `COUNT(*)`
    # via the `total_count` tool argument.
    rendered = len(df)
    total = int(total_override) if total_override is not None else rendered
    if severity_column not in df.columns:
        return [Kpi(label="Issues", value=f"{total:,}")]

    normalized = df[severity_column].astype(str).str.lower()
    errors = int((normalized == "error").sum())
    warnings = int((normalized == "warning").sum())
    # When we limited the rendered rows, the severity counts on this page
    # no longer equal the global counts. Suffix them with the visible
    # sample so the UI stays honest.
    suffix = f" of {rendered:,} shown" if total_override and total_override > rendered else ""
    return [
        Kpi(label="Total issues", value=f"{total:,}"),
        Kpi(
            label="Errors",
            value=f"{errors:,}{suffix}",
            delta_direction="up" if errors else "down",
        ),
        Kpi(
            label="Warnings",
            value=f"{warnings:,}{suffix}",
            delta_direction="neutral",
        ),
    ]


def _derive_table_kpis(df: pd.DataFrame) -> list[Kpi] | None:
    if df.empty:
        return None
    if len(df) == 1:
        row = df.iloc[0]
        kpis: list[Kpi] = []
        for col in df.columns[:3]:
            kpis.append(Kpi(label=humanise(str(col)), value=str(row[col])))
        return kpis or None
    return [Kpi(label="Rows", value=f"{len(df):,}")]


def _format_x_labels(values: list[Any], column_name: str) -> list[str]:
    lower = column_name.lower()
    labels: list[str] = []
    for value in values:
        if "visit" in lower and isinstance(value, (int, float)) and float(value).is_integer():
            labels.append(f"V{int(value)}")
        else:
            labels.append(str(value))
    return labels


def _degrade_terminal_failure(
    *,
    state: _AgentV2State,
    tool_name: str,
    reason: str,
    fallback_title: str,
) -> ChatArtifact | None:
    if state.last_df is None:
        return None
    return build_degraded_table_from_df(
        df=state.last_df.head(50),
        intent_label=fallback_title,
        reason=f"{tool_name}: {reason}",
    )


def _fallback_artifact_from_state(
    state: _AgentV2State,
    *,
    fallback_title: str,
) -> ChatArtifact | None:
    if state.last_df is None:
        return None
    if state.last_df.empty:
        return build_empty_table(title=fallback_title, subtitle="Query returned no rows")
    return build_table(
        title=fallback_title,
        subtitle=f"Table · {len(state.last_df):,} row(s)",
        kpis=_derive_table_kpis(state.last_df),
        table=df_to_table(state.last_df, limit=50),
    )


def _degraded_no_key_response_v2(query: DuckDBQueryService) -> ChatResponse:
    categories = query.list_categories()
    df = pd.DataFrame({"category": categories})
    artifact = build_table(
        title="Clinical categories",
        subtitle=f"{len(categories)} categories discovered",
        kpis=[Kpi(label="Categories", value=f"{len(categories):,}")],
        table=df_to_table(df, labels={"category": "Category"}),
    )
    return ChatResponse(
        steps=[
            "Answered in degraded mode · no LLM key",
            f"Listed · {len(categories)} categories",
            "Selected artifact · table",
        ],
        reply=(
            "The unified analyst is running without an ANTHROPIC_API_KEY, so I "
            "can only show the discovered category index right now."
        ),
        artifact=artifact,
        trace=ChatTrace(
            intent="degraded_no_key",
            recipe=None,
            agent_mode="v2",
            sql=[],
            row_counts=[len(categories)],
            artifact_kind="table",
            tool_log=[],
        ),
    )


def _degraded_api_error_response_v2(exc: Exception) -> ChatResponse:
    return ChatResponse(
        steps=["Unified agent unavailable · upstream LLM error"],
        reply=f"I could not reach the language model ({type(exc).__name__}: {exc}).",
        artifact=None,
        trace=ChatTrace(
            intent="degraded_api_error",
            recipe=None,
            agent_mode="v2",
            sql=[],
            row_counts=[],
            artifact_kind=None,
            tool_log=[],
        ),
    )


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "")))
    return "\n".join(p for p in parts if p).strip()


def _default_reply_from_state(state: _AgentV2State) -> str:
    if state.last_df is not None:
        return (
            f"Ran a query and returned {len(state.last_df):,} row(s). "
            "The table is open on the right."
        )
    return "I answered directly because this did not require data access."


def _coerce_reply_text(args: dict[str, Any]) -> str:
    reply = args.get("reply_text")
    return reply.strip() if isinstance(reply, str) else ""


def _fallback_title_from_args(args: dict[str, Any], tool_name: str) -> str:
    title = args.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return tool_name.replace("_", " ").title()


def _short_title(message: str, max_len: int = 70) -> str:
    clean = " ".join(message.split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "..."
