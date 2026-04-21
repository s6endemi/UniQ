"""Offline tests for the unified v2 chat agent.

These do not hit Anthropic. Instead they inject a tiny fake client that emits
pre-baked tool-use / end_turn sequences so we can verify the handle protocol,
terminal present_* tools, and fallback behaviour in a deterministic way.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chat_agent_v2 import run_chat_agent_v2
from src.datastore import UnifiedDataRepository
from src.query_service import DuckDBQueryService


_results: list[tuple[str, str, str]] = []


def _ok(name: str, detail: str = "") -> None:
    _results.append(("OK", name, detail))


def _fail(name: str, detail: str) -> None:
    _results.append(("FAIL", name, detail))


def _report_and_exit() -> int:
    for status, name, detail in _results:
        icon = {"OK": "[OK]", "FAIL": "[X]"}[status]
        suffix = f"  -- {detail}" if detail else ""
        print(f"  {icon} {name}{suffix}")
    passes = sum(1 for s, *_ in _results if s == "OK")
    fails = sum(1 for s, *_ in _results if s == "FAIL")
    print(f"\n{passes} pass, {fails} fail")
    return 1 if fails else 0


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_block(name: str, input: dict, block_id: str) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=input, id=block_id)


class FakeMessages:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = responses
        self.calls = 0

    def create(self, **_kwargs) -> SimpleNamespace:
        if self.calls >= len(self._responses):
            raise RuntimeError("Fake client exhausted responses")
        response = self._responses[self.calls]
        self.calls += 1
        return response


class FakeAnthropic:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.messages = FakeMessages(responses)


def main() -> int:
    repo = UnifiedDataRepository.from_output_dir()
    query = DuckDBQueryService(repo)

    try:
        # 1. Greeting / meta: no tools, no artifact.
        client = FakeAnthropic([
            SimpleNamespace(stop_reason="end_turn", content=[
                _text_block("I can help with cohorts, quality issues, demographics, and FHIR exports.")
            ])
        ])
        resp = run_chat_agent_v2("hello", query=query, repo=repo, client=client)
        if resp.artifact is None and not resp.trace.sql and resp.trace.agent_mode == "v2":
            _ok("meta greeting stays text-only", "no SQL, no artifact")
        else:
            _fail(
                "meta greeting stays text-only",
                f"artifact={getattr(resp.artifact, 'kind', None)!r}, sql={resp.trace.sql}",
            )

        # 2. Cohort trend through result handles + terminal present_cohort_trend.
        client = FakeAnthropic([
            SimpleNamespace(stop_reason="tool_use", content=[
                _tool_block(
                    "execute_sql",
                    {
                        "handle": "trend_data",
                        "sql": (
                            "WITH cohort AS ("
                            "  SELECT DISTINCT user_id FROM medication_history "
                            "  WHERE LOWER(COALESCE(CAST(product AS VARCHAR), '')) LIKE '%mounjaro%'"
                            "), visits AS ("
                            "  SELECT b.user_id, b.bmi, "
                            "         ROW_NUMBER() OVER (PARTITION BY b.user_id ORDER BY b.date) AS visit_num "
                            "  FROM bmi_timeline b INNER JOIN cohort c ON b.user_id = c.user_id "
                            "  WHERE b.bmi IS NOT NULL"
                            ") "
                            "SELECT visit_num, COUNT(DISTINCT user_id) AS n_patients, "
                            "ROUND(AVG(bmi), 2) AS mean_bmi "
                            "FROM visits WHERE visit_num BETWEEN 1 AND 8 "
                            "GROUP BY visit_num ORDER BY visit_num"
                        ),
                    },
                    "tool-1",
                ),
                _tool_block(
                    "execute_sql",
                    {
                        "handle": "top_patients",
                        "sql": (
                            "WITH cohort AS ("
                            "  SELECT DISTINCT user_id FROM medication_history "
                            "  WHERE LOWER(COALESCE(CAST(product AS VARCHAR), '')) LIKE '%mounjaro%'"
                            "), ranked AS ("
                            "  SELECT b.user_id, b.bmi, "
                            "         ROW_NUMBER() OVER (PARTITION BY b.user_id ORDER BY b.date) AS asc_rank, "
                            "         ROW_NUMBER() OVER (PARTITION BY b.user_id ORDER BY b.date DESC) AS desc_rank "
                            "  FROM bmi_timeline b INNER JOIN cohort c ON b.user_id = c.user_id "
                            "  WHERE b.bmi IS NOT NULL"
                            "), first_bmi AS (SELECT user_id, bmi AS bmi_first FROM ranked WHERE asc_rank = 1), "
                            "last_bmi AS (SELECT user_id, bmi AS bmi_last FROM ranked WHERE desc_rank = 1) "
                            "SELECT f.user_id AS patient, f.bmi_first, l.bmi_last, "
                            "ROUND(l.bmi_last - f.bmi_first, 2) AS delta "
                            "FROM first_bmi f INNER JOIN last_bmi l ON f.user_id = l.user_id "
                            "ORDER BY delta ASC LIMIT 5"
                        ),
                    },
                    "tool-2",
                ),
            ]),
            SimpleNamespace(stop_reason="tool_use", content=[
                _tool_block(
                    "present_cohort_trend",
                    {
                        "trend_handle": "trend_data",
                        "table_handle": "top_patients",
                        "x_column": "visit_num",
                        "series": [{"name": "Mounjaro · mean BMI", "y_column": "mean_bmi"}],
                        "title": "Mounjaro cohort · BMI trajectory",
                        "subtitle": "visits 1-8",
                        "chart_title": "BMI trajectory",
                        "chart_subtitle": "Mounjaro cohort",
                        "y_label": "mean BMI",
                        "reply_text": "Built a BMI trajectory for the Mounjaro cohort.",
                    },
                    "tool-3",
                ),
            ]),
        ])
        resp = run_chat_agent_v2(
            "Show BMI trends for Mounjaro patients over 24 weeks",
            query=query,
            repo=repo,
            client=client,
        )
        if resp.artifact and resp.artifact.kind == "cohort_trend" and len(resp.trace.sql) == 2:
            _ok("present_cohort_trend resolves SQL handles", "cohort_trend with 2 SQL queries")
        else:
            _fail(
                "present_cohort_trend resolves SQL handles",
                f"kind={getattr(resp.artifact, 'kind', None)!r}, sql={len(resp.trace.sql)}",
            )

        # 3. Direct FHIR present tool.
        client = FakeAnthropic([
            SimpleNamespace(stop_reason="tool_use", content=[
                _tool_block(
                    "present_fhir_bundle",
                    {
                        "user_id": 381119,
                        "title": "FHIR Bundle · PT-381119",
                        "subtitle": "Bundle · patient export",
                        "reply_text": "Assembled a FHIR bundle for patient 381119.",
                    },
                    "tool-4",
                )
            ])
        ])
        resp = run_chat_agent_v2(
            "Generate a FHIR bundle for patient 381119",
            query=query,
            repo=repo,
            client=client,
        )
        if resp.artifact and resp.artifact.kind == "fhir_bundle":
            _ok("present_fhir_bundle builds terminal artifact")
        else:
            _fail(
                "present_fhir_bundle builds terminal artifact",
                f"kind={getattr(resp.artifact, 'kind', None)!r}",
            )

        # 4. Bad terminal handle degrades honestly to a table artifact.
        client = FakeAnthropic([
            SimpleNamespace(stop_reason="tool_use", content=[
                _tool_block(
                    "execute_sql",
                    {
                        "handle": "avg_bmi",
                        "sql": "SELECT ROUND(AVG(bmi), 1) AS mean_bmi FROM bmi_timeline",
                    },
                    "tool-5",
                )
            ]),
            SimpleNamespace(stop_reason="tool_use", content=[
                _tool_block(
                    "present_cohort_trend",
                    {
                        "trend_handle": "missing_handle",
                        "x_column": "visit_num",
                        "series": [{"name": "BMI", "y_column": "mean_bmi"}],
                        "title": "Broken artifact",
                        "subtitle": "should degrade",
                        "chart_title": "Broken",
                        "reply_text": "Fallback if the rich artifact cannot be rendered.",
                    },
                    "tool-6",
                )
            ]),
        ])
        resp = run_chat_agent_v2(
            "What is the average BMI of all patients?",
            query=query,
            repo=repo,
            client=client,
        )
        if resp.artifact and resp.artifact.kind == "table":
            _ok("invalid terminal handles degrade to table")
        else:
            _fail(
                "invalid terminal handles degrade to table",
                f"kind={getattr(resp.artifact, 'kind', None)!r}",
            )

        return _report_and_exit()
    finally:
        query.close()


if __name__ == "__main__":
    raise SystemExit(main())
