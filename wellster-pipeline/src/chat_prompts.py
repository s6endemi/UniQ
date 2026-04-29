"""Legacy v1 system prompt + tool schemas.

The production pilot default uses `chat_prompts_v2.py`. This file stays
in the tree only because `UNIQ_AGENT_MODE=v1` remains available as a
local fallback path.

Kept separate from the agent loop so the prompt can evolve (better
examples, refined guardrails) without touching orchestration code, and
so the tool schemas have one canonical home.

Design choices:

- **Schema is injected**, not fetched via tool. The DuckDB schema is
  small (~7 tables) and cheap to stringify, so we save one round-trip
  by including it up front. Claude still has `sample_rows` for peeking
  at data shape.
- **Sonnet 4.6**. The schema is small (~20 tables, well-named columns)
  so Sonnet writes reliable SQL without Opus-grade reasoning, and the
  latency gap (2-4s vs 5-10s) and cost difference (~5×) matter for a
  live-feeling pitch demo. If the model ever gets a column name wrong,
  the DuckDB error flows back as a `tool_result` and it self-corrects
  on the next turn.
- **No freeform UI generation**. The system prompt is explicit that the
  agent produces SQL + a short prose answer — the artifact is picked by
  the backend, not the model.
- **Prompt caching.** The system prompt + tool definitions are cached
  per Anthropic's ephemeral cache API so repeat turns in the same
  session pay only for the user delta.
"""

from __future__ import annotations

from typing import Any


CHAT_MODEL = "claude-sonnet-4-6"
CHAT_MAX_TOKENS = 2048
CHAT_MAX_TOOL_ITERATIONS = 6


# ---- Tool schemas --------------------------------------------------------


TOOL_EXECUTE_SQL = {
    "name": "execute_sql",
    "description": (
        "Run a read-only SELECT / WITH query against the DuckDB substrate. "
        "The query is guarded: only SELECT/WITH/SHOW/DESCRIBE are allowed, "
        "DDL/DML/file-IO tokens are rejected, and results are capped. "
        "Returns the column list, row count, truncation flag, and a "
        "20-row preview. Use this for aggregations, joins, and analytical "
        "questions. Prefer parameterised values in the SQL string itself "
        "(no parameter binding is exposed here)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A single SELECT or WITH statement. No semicolons.",
            }
        },
        "required": ["sql"],
    },
}


TOOL_SAMPLE_ROWS = {
    "name": "sample_rows",
    "description": (
        "Return the first N rows of a registered table so you can see the "
        "actual data shape before writing SQL. Use sparingly — prefer "
        "execute_sql once you know what to ask."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "table": {
                "type": "string",
                "description": "One of the registered tables.",
            },
            "n": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 5,
            },
        },
        "required": ["table"],
    },
}


TOOL_BUILD_FHIR_BUNDLE = {
    "name": "build_fhir_bundle",
    "description": (
        "Assemble a FHIR R4 Bundle for a specific patient — Patient, "
        "Observation (BMI), MedicationStatement, Condition, AdverseEvent. "
        "Use this when the user explicitly asks for a FHIR bundle or export "
        "tied to a single patient. Returns a resource-type summary; the "
        "full bundle becomes the artifact payload."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "Integer patient identifier (from patients.user_id).",
            }
        },
        "required": ["user_id"],
    },
}


GENERIC_TOOLS = [TOOL_EXECUTE_SQL, TOOL_SAMPLE_ROWS, TOOL_BUILD_FHIR_BUNDLE]


# ---- System prompt -------------------------------------------------------


def _format_schema(schema: dict[str, list[dict[str, str]]]) -> str:
    lines: list[str] = []
    for table, cols in schema.items():
        summary = ", ".join(f"{c['column']}:{c['type']}" for c in cols[:12])
        suffix = f", … +{len(cols) - 12} more" if len(cols) > 12 else ""
        lines.append(f"  {table}({summary}{suffix})")
    return "\n".join(lines)


def _format_categories(categories: list[str]) -> str:
    if not categories:
        return "  (no categories discovered yet)"
    preview = categories[:20]
    tail = f"  … +{len(categories) - 20} more" if len(categories) > 20 else ""
    return "\n".join(f"  · {c}" for c in preview) + (f"\n{tail}" if tail else "")


SYSTEM_PROMPT_TEMPLATE = """You are UniQ Analyst, the read-only SQL agent for the
Wellster obesity-treatment substrate. Your job is to answer a clinician
or operator's question by running SQL against DuckDB tables, then
writing one concise paragraph of prose that cites the numbers you found.

# Substrate

Tables (column:type, truncated at 12 cols):

{schema_block}

Primary keys follow the pattern `user_id` (patient) and `treatment_id`
(episode). The `survey_unified` table is the event store; `patients`,
`bmi_timeline`, `medication_history` are derived views. `clinical_category`
in `mapping_table` classifies survey questions (e.g. BMI_MEASUREMENT).

Categories observed in this dataset:

{categories_block}

# How you work

1. Think briefly about what the user is asking. Prefer the simplest SQL
   that answers it.
2. If you need to see a table's shape, call `sample_rows` with n=5.
3. Call `execute_sql` with one well-formed SELECT or WITH statement.
   Results are capped and previewed; you see the first 20 rows and the
   total row count.
4. If the user explicitly asks for a FHIR bundle for a single patient,
   call `build_fhir_bundle` with the integer user_id.
5. When you have enough to answer, stop calling tools and write a single
   short paragraph (2-4 sentences) with the concrete numbers.

# Non-negotiable rules

- Only read; never attempt DDL, DML, COPY, ATTACH, INSTALL, PRAGMA, or
  file/network reads. The guard will reject them anyway.
- Do not wrap SQL in markdown code fences when passing it as the `sql`
  argument — send raw SQL text.
- Do not invent column names. If unsure, sample a row first.
- Do not describe a chart or dashboard. The backend picks the artifact;
  you only supply the data and the prose.
- If the data does not support a confident answer, say so plainly in
  your final text. An honest empty answer beats a hallucinated number.

# Style

Write like a clinical operator's note: specific, short, numeric. Round
BMI to one decimal. Format counts with thousands separators. Never use
emojis. Never thank the user.
"""


def build_system_prompt(
    *,
    schema: dict[str, list[dict[str, str]]],
    categories: list[str],
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        schema_block=_format_schema(schema),
        categories_block=_format_categories(categories),
    )


def system_prompt_with_cache(
    *,
    schema: dict[str, list[dict[str, str]]],
    categories: list[str],
) -> list[dict[str, Any]]:
    """Return the system prompt as an ephemeral-cached content block.

    Anthropic's prompt-caching API caches up to the breakpoint; the
    static system + tool schemas are identical across turns, so caching
    here is worth the one extra field.
    """
    return [
        {
            "type": "text",
            "text": build_system_prompt(schema=schema, categories=categories),
            "cache_control": {"type": "ephemeral"},
        }
    ]
