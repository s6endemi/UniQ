"""Deterministic chat recipes — golden-path intents that skip the agent.

The hybrid-agent design from Phase 6 planning: a small set of known
intents bypass the Anthropic tool-use loop entirely and run a pinned SQL
template + validated builder. Everything else falls through to the
generic agent (chat_agent.py).

Why: pitch robustness. For the canonical demo questions (BMI cohort
dashboard, FHIR export, quality alerts), we cannot afford prompt
variance, Claude latency, or an unexpected tool choice. Deterministic =
sub-second, pixel-stable, provenance-clear.

Matching is keyword-based (case-insensitive, with small stemming) and
*must* be conservative. When a keyword overlap is ambiguous — e.g. the
user says "bmi" but asks about a single patient — we prefer to miss the
recipe and let the general agent handle it, rather than force a
dashboard on a patient lookup.

Each recipe function follows the same contract:

    def try_<name>(message, query, repo) -> RecipeResult | None:
        ...

Returning None means "this recipe does not apply"; the dispatcher moves
on to the next one. The first recipe to return a RecipeResult wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.api.models import ChartSeries, ChatArtifact, Kpi
from src.artifact_builders import (
    build_alerts_table,
    build_cohort_trend,
    build_empty_table,
    build_fhir_bundle,
    df_to_table,
)
from src.chat_tools import tool_build_fhir_bundle
from src.datastore import UnifiedDataRepository
from src.query_service import DuckDBQueryService


@dataclass
class RecipeResult:
    recipe: str  # recipe name for the trace
    steps: list[str]
    reply: str
    artifact: ChatArtifact
    sql: list[str]
    row_counts: list[int]


# ---- Keyword heuristics ---------------------------------------------------


_DRUG_PATTERNS: dict[str, list[str]] = {
    "Mounjaro": ["mounjaro", "tirzepatide"],
    "Wegovy": ["wegovy", "semaglutide"],
    "Ozempic": ["ozempic"],
    "Saxenda": ["saxenda", "liraglutide"],
}

_TREND_WORDS = (
    "trend",
    "trajectory",
    "over time",
    "weeks",
    "cohort",
    "bmi",
    "weight loss",
)

_ALERT_WORDS = (
    "alert",
    "quality",
    "issue",
    "problem",
    "gap",
    "flag",
    "missed",
    "spike",
)

_FHIR_WORDS = ("fhir", "bundle", "export")

_PATIENT_ID_RE = re.compile(r"\bPT[-\s]?(\d{3,6})\b", re.IGNORECASE)
_BARE_ID_RE = re.compile(r"\b(\d{3,6})\b")


def _any(words: tuple[str, ...], text: str) -> bool:
    return any(w in text for w in words)


def _detect_drug(text: str) -> str | None:
    for display, patterns in _DRUG_PATTERNS.items():
        if any(p in text for p in patterns):
            return display
    return None


def _count_drugs_mentioned(text: str) -> int:
    count = 0
    for patterns in _DRUG_PATTERNS.values():
        if any(p in text for p in patterns):
            count += 1
    return count


def _detect_patient_id(message: str) -> int | None:
    m = _PATIENT_ID_RE.search(message)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    # Bare integer, only if FHIR intent is already established — checked
    # by the caller.
    m = _BARE_ID_RE.search(message)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


# ---- Recipe 1 · cohort_trajectory ----------------------------------------


_COHORT_SQL = """
WITH cohort AS (
  SELECT DISTINCT user_id
  FROM medication_history
  WHERE LOWER(COALESCE(CAST(product AS VARCHAR), '')) LIKE ?
),
visits AS (
  SELECT
    b.user_id,
    b.bmi,
    b.date,
    ROW_NUMBER() OVER (PARTITION BY b.user_id ORDER BY b.date) AS visit_num
  FROM bmi_timeline b
  INNER JOIN cohort c ON b.user_id = c.user_id
  WHERE b.bmi IS NOT NULL
)
SELECT
  visit_num,
  COUNT(DISTINCT user_id) AS n_patients,
  ROUND(AVG(bmi), 2) AS mean_bmi,
  ROUND(MIN(bmi), 1) AS min_bmi,
  ROUND(MAX(bmi), 1) AS max_bmi
FROM visits
WHERE visit_num BETWEEN 1 AND 8
GROUP BY visit_num
ORDER BY visit_num
""".strip()


_PATIENT_TABLE_SQL = """
WITH cohort AS (
  SELECT DISTINCT user_id
  FROM medication_history
  WHERE LOWER(COALESCE(CAST(product AS VARCHAR), '')) LIKE ?
),
ranked AS (
  SELECT
    b.user_id,
    b.bmi,
    b.date,
    ROW_NUMBER() OVER (PARTITION BY b.user_id ORDER BY b.date) AS asc_rank,
    ROW_NUMBER() OVER (PARTITION BY b.user_id ORDER BY b.date DESC) AS desc_rank
  FROM bmi_timeline b
  INNER JOIN cohort c ON b.user_id = c.user_id
  WHERE b.bmi IS NOT NULL
),
first_bmi AS (SELECT user_id, bmi AS bmi_first FROM ranked WHERE asc_rank = 1),
last_bmi AS (SELECT user_id, bmi AS bmi_last FROM ranked WHERE desc_rank = 1),
latest_med AS (
  SELECT user_id, MAX(dosage) AS dosage
  FROM medication_history
  WHERE LOWER(COALESCE(CAST(product AS VARCHAR), '')) LIKE ?
  GROUP BY user_id
)
SELECT
  f.user_id AS patient,
  COALESCE(m.dosage, '—') AS dose,
  f.bmi_first AS bmi_baseline,
  l.bmi_last AS bmi_latest,
  ROUND(l.bmi_last - f.bmi_first, 2) AS delta
FROM first_bmi f
INNER JOIN last_bmi l ON f.user_id = l.user_id
LEFT JOIN latest_med m ON f.user_id = m.user_id
ORDER BY delta ASC
LIMIT 7
""".strip()


def try_cohort_trajectory(
    message: str,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> RecipeResult | None:
    text = message.lower()
    drug = _detect_drug(text)
    # Allow the trend recipe to fire when the user clearly wants a cohort
    # trend even without a drug keyword — we default to Mounjaro since
    # that is the pitch's canonical example.
    if not _any(_TREND_WORDS, text) and drug is None:
        return None
    # Do not hijack clearly patient-scoped questions.
    if _PATIENT_ID_RE.search(message) and "cohort" not in text:
        return None
    # Do not hijack cross-cohort comparisons — those need 2+ series which
    # this single-drug recipe cannot produce. Let the generic agent plan
    # the join itself.
    if _count_drugs_mentioned(text) >= 2:
        return None

    drug = drug or "Mounjaro"
    like = f"%{drug.lower()}%"

    trend_result = query.execute_sql(_COHORT_SQL, [like])
    if trend_result.row_count == 0:
        # No data for this drug — let the generic agent take over; maybe
        # the user meant something different and Claude can clarify.
        return None
    trend_df = pd.DataFrame(trend_result.rows)

    table_result = query.execute_sql(_PATIENT_TABLE_SQL, [like, like])
    table_df = pd.DataFrame(table_result.rows)

    n_patients = int(trend_df["n_patients"].max())
    bmi_first = float(trend_df.iloc[0]["mean_bmi"])
    bmi_last = float(trend_df.iloc[-1]["mean_bmi"])
    delta = round(bmi_last - bmi_first, 2)
    delta_str = f"{delta:+.1f} pts"

    # Do not colour-code the BMI delta: a drop is *good* clinically, but
    # the UI's `is-down` treatment reads as "alarm". The string itself
    # ("−4.9 pts") carries the sign.
    kpis = [
        Kpi(label=f"Cohort · {drug}", value=str(n_patients), delta=f"visits 1–{len(trend_df)}"),
        Kpi(label="Mean BMI · baseline", value=f"{bmi_first:.1f}", delta=f"n = {n_patients}"),
        Kpi(
            label=f"Mean BMI · visit {len(trend_df)}",
            value=f"{bmi_last:.1f}",
            delta=delta_str,
        ),
    ]

    x_labels = [f"V{int(v)}" for v in trend_df["visit_num"]]
    series = [
        ChartSeries(
            name=f"{drug} · mean BMI",
            points=[float(v) for v in trend_df["mean_bmi"]],
        )
    ]

    table_payload = df_to_table(
        table_df,
        columns=["patient", "dose", "bmi_baseline", "bmi_latest", "delta"],
        labels={
            "patient": "Patient ID",
            "dose": "Dose",
            "bmi_baseline": "BMI · first",
            "bmi_latest": "BMI · latest",
            "delta": "Δ",
        },
        emphasis={"delta"},
        align_overrides={"patient": "left", "dose": "left"},
    )

    artifact = build_cohort_trend(
        title=f"{drug} cohort · BMI trajectory",
        subtitle=f"n = {n_patients} · visits 1–{len(trend_df)}",
        kpis=kpis,
        chart_title=f"BMI trajectory — {drug} cohort",
        chart_subtitle=f"visits 1–{len(trend_df)} · n = {n_patients}",
        x_labels=x_labels,
        y_label="mean BMI (kg/m²)",
        series=series,
        table=table_payload,
    )

    steps = [
        f"Classified intent · cohort trajectory ({drug})",
        f"Resolved cohort · {n_patients} patients on {drug}",
        f"Aggregated BMI across {len(trend_df)} visits",
        "Selected artifact · cohort_trend",
    ]
    reply = (
        f"Built a BMI trajectory for the {drug} cohort (n = {n_patients}). "
        f"Mean BMI moved from {bmi_first:.1f} at the first visit to "
        f"{bmi_last:.1f} at visit {len(trend_df)} — a {delta:+.1f}-point change. "
        f"Top responders are listed in the table."
    )

    return RecipeResult(
        recipe="cohort_trajectory",
        steps=steps,
        reply=reply,
        artifact=artifact,
        sql=[_COHORT_SQL, _PATIENT_TABLE_SQL],
        row_counts=[trend_result.row_count, table_result.row_count],
    )


# ---- Recipe 2 · patient_fhir_bundle --------------------------------------


def try_patient_fhir_bundle(
    message: str,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> RecipeResult | None:
    text = message.lower()
    if not _any(_FHIR_WORDS, text):
        return None
    user_id = _detect_patient_id(message)
    if user_id is None:
        return None

    tool_payload = tool_build_fhir_bundle(repo, {"user_id": user_id})
    if "error" in tool_payload:
        artifact = build_empty_table(
            title=f"FHIR Bundle · PT-{user_id}",
            subtitle=tool_payload["error"],
        )
        return RecipeResult(
            recipe="patient_fhir_bundle",
            steps=[
                "Classified intent · patient FHIR export",
                f"Resolved patient identifier · {user_id}",
                "Patient not found",
            ],
            reply=f"No patient with identifier PT-{user_id} is present in the substrate.",
            artifact=artifact,
            sql=[],
            row_counts=[],
        )

    counts = tool_payload["resource_counts"]
    total = tool_payload["resource_total"]
    counts_str = ", ".join(f"{n}×{t}" for t, n in counts.items())

    artifact = build_fhir_bundle(
        title=f"FHIR Bundle · PT-{user_id}",
        subtitle=f"Bundle · {total} resources",
        bundle=tool_payload["bundle"],
    )

    steps = [
        "Classified intent · patient FHIR export",
        f"Resolved patient identifier · {user_id}",
        "Queried FHIR substrate · Patient, Observation, MedicationStatement, Condition",
        f"Assembled Bundle · {total} resources ({counts_str})",
    ]
    reply = (
        f"Assembled a {total}-resource FHIR R4 bundle for PT-{user_id} "
        f"({counts_str}). Opening it in the canvas."
    )

    return RecipeResult(
        recipe="patient_fhir_bundle",
        steps=steps,
        reply=reply,
        artifact=artifact,
        sql=[],
        row_counts=[],
    )


# ---- Recipe 3 · ops_alerts -----------------------------------------------


_ALERTS_SQL = """
SELECT
  check_type,
  severity,
  user_id,
  treatment_id,
  description,
  details
FROM quality_report
ORDER BY
  CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
  check_type,
  user_id
LIMIT 50
""".strip()


_ALERTS_SUMMARY_SQL = """
SELECT
  severity,
  COUNT(*) AS n
FROM quality_report
GROUP BY severity
""".strip()


def try_ops_alerts(
    message: str,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> RecipeResult | None:
    text = message.lower()
    if not _any(_ALERT_WORDS, text):
        return None
    # FHIR export questions sometimes say "flag" in passing; don't hijack.
    if _any(_FHIR_WORDS, text):
        return None

    alerts_result = query.execute_sql(_ALERTS_SQL)
    summary_result = query.execute_sql(_ALERTS_SUMMARY_SQL)

    if alerts_result.row_count == 0:
        artifact = build_empty_table(
            title="Data-quality alerts",
            subtitle="No issues flagged",
        )
        return RecipeResult(
            recipe="ops_alerts",
            steps=[
                "Classified intent · data-quality alerts",
                "Queried quality_report",
                "No issues found",
            ],
            reply="No data-quality issues are currently flagged on the substrate.",
            artifact=artifact,
            sql=[_ALERTS_SQL, _ALERTS_SUMMARY_SQL],
            row_counts=[0, summary_result.row_count],
        )

    alerts_df = pd.DataFrame(alerts_result.rows)
    summary_df = pd.DataFrame(summary_result.rows)

    severity_counts = {
        str(row["severity"]): int(row["n"]) for row in summary_result.rows
    }
    total = sum(severity_counts.values())
    errors = severity_counts.get("error", 0)
    warnings = severity_counts.get("warning", 0)

    kpis = [
        Kpi(label="Total issues", value=f"{total}"),
        Kpi(
            label="Errors",
            value=f"{errors}",
            delta_direction="down" if errors == 0 else "up",
        ),
        Kpi(
            label="Warnings",
            value=f"{warnings}",
            delta_direction="neutral",
        ),
    ]

    table = df_to_table(
        alerts_df,
        columns=["severity", "check_type", "user_id", "treatment_id", "description"],
        labels={
            "severity": "Severity",
            "check_type": "Check",
            "user_id": "Patient",
            "treatment_id": "Treatment",
            "description": "Finding",
        },
        emphasis={"severity"},
        align_overrides={"description": "left"},
    )

    artifact = build_alerts_table(
        title="Data-quality alerts",
        subtitle=f"{total} issues · {alerts_result.row_count} shown",
        kpis=kpis,
        table=table,
    )

    steps = [
        "Classified intent · data-quality alerts",
        f"Queried quality_report · {alerts_result.row_count} rows",
        f"Aggregated severity · {errors} errors / {warnings} warnings",
        "Selected artifact · alerts_table",
    ]
    reply = (
        f"Found {total} flagged issues across the substrate — "
        f"{errors} errors, {warnings} warnings. "
        f"Top {alerts_result.row_count} are listed in the table."
    )

    return RecipeResult(
        recipe="ops_alerts",
        steps=steps,
        reply=reply,
        artifact=artifact,
        sql=[_ALERTS_SQL, _ALERTS_SUMMARY_SQL],
        row_counts=[alerts_result.row_count, summary_result.row_count],
    )


# ---- Dispatcher -----------------------------------------------------------


_RECIPES = (
    try_patient_fhir_bundle,  # most specific first — a "FHIR PT-123" query is unambiguous
    try_cohort_trajectory,
    try_ops_alerts,
)


def try_match_recipe(
    message: str,
    query: DuckDBQueryService,
    repo: UnifiedDataRepository,
) -> RecipeResult | None:
    """Run each recipe's matcher in order; first hit wins.

    If every recipe returns None, the caller should fall back to the
    generic agent.
    """
    for recipe in _RECIPES:
        hit = recipe(message, query, repo)
        if hit is not None:
            return hit
    return None
