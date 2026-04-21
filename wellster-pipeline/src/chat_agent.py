"""Hybrid chat orchestrator.

Flow:

    message
      ├── try_match_recipe()  ─→  deterministic happy path, return artifact
      └── (miss)              ─→  Claude tool-use loop, build table artifact
                                    from the final SQL result
      ↓
    ChatResponse (steps, reply, artifact, trace)

The deterministic recipes are the demo-grade golden paths. The generic
agent is the open-ended analyst: it can answer arbitrary SQL questions,
but its artifact is always the generic `table` family (or `fhir_bundle`
if the agent explicitly called `build_fhir_bundle`). This matches the
plan: richer artifacts are gated by validated templates; the generic
path never improvises UI.

Failure modes:

    - No ANTHROPIC_API_KEY in env → we never attempt the tool-use loop
      and return a clear prose message plus a table artifact listing
      the categories. The UI still works; the user sees a degraded
      answer rather than a 500.
    - SQL error inside the loop → surfaced to Claude as a tool result
      with the error string, so it can retry with a fixed query.
    - Tool-iteration cap hit → we take whatever query result we have
      and wrap it as a table artifact.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.api.models import ChatArtifact, ChatResponse, ChatTrace
from src.artifact_builders import (
    build_degraded_table_from_df,
    build_empty_table,
    build_fhir_bundle,
    build_table,
    df_to_table,
)
from src.chat_prompts import (
    CHAT_MAX_TOKENS,
    CHAT_MAX_TOOL_ITERATIONS,
    CHAT_MODEL,
    GENERIC_TOOLS,
    system_prompt_with_cache,
)
from src.chat_recipes import try_match_recipe
from src.chat_tools import (
    ChatToolError,
    build_tool_registry,
    encode_tool_result,
)
from src.datastore import UnifiedDataRepository
from src.query_service import DuckDBQueryService


# ---- Public entry point --------------------------------------------------


def run_chat_agent(
    message: str,
    *,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> ChatResponse:
    """Single entry point invoked by the FastAPI /chat route."""
    # 1. Deterministic recipes first — these are the pitch golden paths.
    recipe_hit = try_match_recipe(message, query, repo)
    if recipe_hit is not None:
        return ChatResponse(
            steps=recipe_hit.steps,
            reply=recipe_hit.reply,
            artifact=recipe_hit.artifact,
            trace=ChatTrace(
                intent=recipe_hit.recipe,
                recipe=recipe_hit.recipe,
                agent_mode="v1",
                sql=recipe_hit.sql,
                row_counts=recipe_hit.row_counts,
                artifact_kind=recipe_hit.artifact.kind,
            ),
        )

    # 2. Degraded: no API key → safe prose + category overview table.
    if not config.ANTHROPIC_API_KEY:
        return _degraded_no_key_response(message, query)

    # 3. Generic Claude tool-use loop.
    return _run_generic_agent(message=message, query=query, repo=repo)


# ---- Generic agent (Claude tool-use loop) --------------------------------


@dataclass
class _AgentState:
    """Run-log from the tool-use loop.

    We capture full query results (not just the preview Claude sees) so
    the final artifact builder has the complete row set to render.
    """

    executed_sql: list[str] = field(default_factory=list)
    row_counts: list[int] = field(default_factory=list)
    last_df: pd.DataFrame | None = None
    last_sql: str | None = None
    last_columns: list[str] = field(default_factory=list)
    fhir_bundle: dict[str, Any] | None = None
    fhir_user_id: int | None = None
    sampled_tables: list[str] = field(default_factory=list)


def _run_generic_agent(
    *,
    message: str,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> ChatResponse:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    tool_registry = build_tool_registry(query, repo)

    system_blocks = system_prompt_with_cache(
        schema=query.schema(),
        categories=query.list_categories(),
    )

    state = _AgentState()
    steps: list[str] = ["Classified intent · generic analyst"]
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": message},
    ]

    final_text: str | None = None

    for _ in range(CHAT_MAX_TOOL_ITERATIONS):
        try:
            response = client.messages.create(
                model=CHAT_MODEL,
                max_tokens=CHAT_MAX_TOKENS,
                system=system_blocks,
                tools=GENERIC_TOOLS,
                messages=messages,
            )
        except anthropic.APIError as exc:
            return _degraded_api_error_response(message, query, exc)

        if response.stop_reason == "end_turn":
            final_text = _extract_text(response.content)
            break

        if response.stop_reason == "tool_use":
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                final_text = _extract_text(response.content)
                break

            tool_results: list[dict[str, Any]] = []
            for block in tool_uses:
                executor = tool_registry.get(block.name)
                if executor is None:
                    payload = {"error": f"Unknown tool {block.name!r}"}
                else:
                    try:
                        payload = executor(dict(block.input or {}))
                    except ChatToolError as exc:
                        payload = {"error": str(exc)}
                    except Exception as exc:  # noqa: BLE001
                        payload = {"error": f"{type(exc).__name__}: {exc}"}

                _absorb_tool_result(state, steps, block.name, block.input or {}, payload, query)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": encode_tool_result(payload),
                    }
                )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unknown stop reason — bail out gracefully.
        final_text = _extract_text(response.content)
        break

    artifact = _build_artifact_from_state(state, fallback_title=_short_title(message))
    if artifact is not None:
        steps.append(f"Selected artifact · {artifact.kind}")

    reply = (final_text or "").strip() or _default_reply(state)

    return ChatResponse(
        steps=steps,
        reply=reply,
        artifact=artifact,
        trace=ChatTrace(
            intent="generic_sql",
            recipe=None,
            agent_mode="v1",
            sql=state.executed_sql,
            row_counts=state.row_counts,
            artifact_kind=artifact.kind if artifact else None,
        ),
    )


# ---- State absorption & artifact assembly --------------------------------


def _absorb_tool_result(
    state: _AgentState,
    steps: list[str],
    tool_name: str,
    args: dict[str, Any],
    payload: dict[str, Any],
    query: DuckDBQueryService,
) -> None:
    """Mirror the tool's effect into local state and add a synthetic step."""
    if "error" in payload:
        steps.append(f"Tool error · {tool_name} · {payload['error'][:80]}")
        return

    if tool_name == "execute_sql":
        sql = str(payload.get("sql", args.get("sql", "")))
        state.executed_sql.append(sql)
        state.last_sql = sql
        state.last_columns = list(payload.get("columns", []))
        row_count = int(payload.get("row_count", 0))
        state.row_counts.append(row_count)
        # Re-run the same SQL to materialise the full (non-previewed) result
        # for the artifact. The query service already caps rows at 10k.
        try:
            full = query.execute_sql(sql)
            state.last_df = pd.DataFrame(full.rows, columns=full.columns)
        except Exception:
            # If the re-run fails we fall back to the preview; losing
            # 10k-vs-20 rows is still a valid artifact.
            state.last_df = pd.DataFrame(
                payload.get("preview", []), columns=state.last_columns
            )
        steps.append(f"Queried substrate · {row_count:,} row{'s' if row_count != 1 else ''}")
        return

    if tool_name == "sample_rows":
        table = str(args.get("table", "?"))
        state.sampled_tables.append(table)
        steps.append(f"Sampled · {table}")
        return

    if tool_name == "build_fhir_bundle":
        state.fhir_bundle = payload.get("bundle")
        state.fhir_user_id = payload.get("user_id")
        total = payload.get("resource_total", 0)
        steps.append(f"Assembled FHIR bundle · {total} resources")
        return

    steps.append(f"Tool · {tool_name}")


def _build_artifact_from_state(
    state: _AgentState,
    *,
    fallback_title: str,
) -> ChatArtifact | None:
    # FHIR bundle takes precedence — if the model explicitly built one,
    # that is the answer.
    if state.fhir_bundle is not None:
        uid = state.fhir_user_id
        subtitle_suffix = f" · PT-{uid}" if uid is not None else ""
        return build_fhir_bundle(
            title=f"FHIR Bundle{subtitle_suffix}",
            subtitle=f"Bundle · {len(state.fhir_bundle.get('entry', []))} resources",
            bundle=state.fhir_bundle,
        )

    if state.last_df is not None:
        if len(state.last_df) == 0:
            return build_empty_table(
                title=fallback_title,
                subtitle="Query returned no rows",
            )
        try:
            table = df_to_table(state.last_df)
            return build_table(
                title=fallback_title,
                subtitle=f"Table · {len(state.last_df):,} row(s)",
                table=table,
            )
        except Exception as exc:  # noqa: BLE001
            return build_degraded_table_from_df(
                df=state.last_df.head(50),
                intent_label=fallback_title,
                reason=f"builder error: {type(exc).__name__}",
            )

    return None


# ---- Degraded-path responses ---------------------------------------------


def _degraded_no_key_response(
    message: str,
    query: DuckDBQueryService,
) -> ChatResponse:
    categories = query.list_categories()
    df = pd.DataFrame({"category": categories})
    artifact = build_table(
        title="Clinical categories",
        subtitle=f"{len(categories)} categories discovered",
        table=df_to_table(df, labels={"category": "Category"}),
    )
    reply = (
        "The analyst is running without an ANTHROPIC_API_KEY — I can only "
        "show the category index for now. Set the key in the environment "
        "to unlock SQL answers."
    )
    return ChatResponse(
        steps=[
            "Classified intent · unknown (no LLM key)",
            f"Listed · {len(categories)} categories",
            "Selected artifact · table",
        ],
        reply=reply,
        artifact=artifact,
        trace=ChatTrace(
            intent="degraded_no_key",
            recipe=None,
            agent_mode="v1",
            sql=[],
            row_counts=[len(categories)],
            artifact_kind="table",
        ),
    )


def _degraded_api_error_response(
    message: str,
    query: DuckDBQueryService,
    exc: Exception,
) -> ChatResponse:
    reply = (
        "I could not reach the language model ("
        f"{type(exc).__name__}: {exc}"
        "). Try again in a moment — your question is unchanged."
    )
    return ChatResponse(
        steps=["Classified intent · generic analyst", "Upstream LLM error"],
        reply=reply,
        artifact=None,
        trace=ChatTrace(
            intent="degraded_api_error",
            recipe=None,
            agent_mode="v1",
            sql=[],
            row_counts=[],
            artifact_kind=None,
        ),
    )


# ---- Helpers --------------------------------------------------------------


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "")))
    return "\n".join(p for p in parts if p).strip()


def _default_reply(state: _AgentState) -> str:
    if state.last_df is not None:
        return (
            f"Ran a query and returned {len(state.last_df):,} row(s). "
            "Table is open on the right."
        )
    return (
        "I couldn't find a good answer in the substrate for that question. "
        "Try rephrasing or ask about cohorts, BMI, adherence, or FHIR bundles."
    )


def _short_title(message: str, max_len: int = 70) -> str:
    clean = " ".join(message.split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "…"
