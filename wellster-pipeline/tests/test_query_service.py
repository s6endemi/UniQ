"""Phase 3B smoke tests for `DuckDBQueryService`.

Verifies:
    - Schema introspection lists every registered table with columns.
    - Sample returns rows from a real table.
    - Parameterized SELECT returns expected shape.
    - Row cap wrapping truncates results and flags `truncated`.
    - Guardrails reject non-SELECT, stacked statements, unknown tables.

Prerequisites: `output/` populated (pipeline.py was run). Skips gracefully
otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.query_service import (
    DuckDBQueryService,
    QueryGuardrailViolation,
)


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

    svc = DuckDBQueryService.from_output_dir(max_rows=50)
    try:
        # 1. Schema introspection
        schema = svc.schema()
        # 8 tables since P0.4: raw `survey_unified` plus the validated layer
        # `survey_validated` which gates downstream consumers.
        expected_tables = {"survey_unified", "survey_validated",
                           "patients", "treatment_episodes",
                           "bmi_timeline", "medication_history",
                           "mapping_table", "quality_report"}
        if set(schema.keys()) == expected_tables:
            _ok("schema lists 8 tables", ", ".join(sorted(schema.keys())))
        else:
            _fail("schema lists 8 tables",
                  f"got {sorted(schema.keys())}")
            return _report_and_exit()

        for table, cols in schema.items():
            if len(cols) == 0:
                _fail(f"{table} has columns", "0 columns")
                return _report_and_exit()
        _ok("every table has columns",
            f"total {sum(len(c) for c in schema.values())} across 8 tables")

        # 2. Categories introspection
        cats = svc.list_categories()
        if len(cats) >= 10:
            _ok("list_categories returns distinct set", f"{len(cats)} categories")
        else:
            _fail("list_categories returns distinct set", f"only {len(cats)}")
            return _report_and_exit()

        # 3. Sample
        sample = svc.sample("patients", n=3)
        if len(sample) == 3 and "user_id" in sample[0]:
            _ok("sample('patients', 3)", f"{list(sample[0].keys())[:4]}")
        else:
            _fail("sample('patients', 3)", f"got {sample}")
            return _report_and_exit()

        # 4. sample rejects unknown table
        try:
            svc.sample("does_not_exist")
            _fail("sample rejects unknown table", "no exception raised")
            return _report_and_exit()
        except QueryGuardrailViolation:
            _ok("sample rejects unknown table")

        # 5. Parameterized SELECT
        result = svc.execute_sql(
            "SELECT clinical_category, COUNT(*) AS n FROM mapping_table "
            "WHERE clinical_category = ? GROUP BY 1",
            ["BMI_MEASUREMENT"],
        )
        if (result.row_count == 1
                and result.rows[0]["clinical_category"] == "BMI_MEASUREMENT"
                and result.rows[0]["n"] > 0):
            _ok("parameterized SELECT works",
                f"BMI_MEASUREMENT has {result.rows[0]['n']} question_ids")
        else:
            _fail("parameterized SELECT works", f"got {result.rows}")
            return _report_and_exit()

        # 6. Row cap + truncation flag
        # max_rows=50 was set at init; query that would return ~4500 rows.
        big = svc.execute_sql("SELECT * FROM mapping_table")
        if big.row_count == 50 and big.truncated:
            _ok("row cap + truncation flag", "returned 50, truncated=True")
        else:
            _fail("row cap + truncation flag",
                  f"row_count={big.row_count}, truncated={big.truncated}")
            return _report_and_exit()

        # 7. Guardrail: first-word allow-list
        blocked_queries = [
            "DROP TABLE patients",
            "INSERT INTO patients VALUES (1)",
            "UPDATE patients SET gender='x'",
            "DELETE FROM patients",
            "ATTACH DATABASE 'x'",
        ]
        all_blocked = True
        for q in blocked_queries:
            try:
                svc.execute_sql(q)
                _fail(f"guardrail blocks {q.split()[0]}", "query ran")
                all_blocked = False
                break
            except QueryGuardrailViolation:
                pass
        if all_blocked:
            _ok("first-word allow-list blocks DML/DDL",
                f"{len(blocked_queries)} statement types blocked")

        # 8. Guardrail: stacked statements
        try:
            svc.execute_sql("SELECT 1; SELECT 2")
            _fail("stacked-statements guardrail", "allowed through")
        except QueryGuardrailViolation:
            _ok("stacked-statements guardrail")

        # 9. Trailing-semicolon tolerated (common ergonomic)
        try:
            result = svc.execute_sql("SELECT 42 AS answer;")
            if result.rows and result.rows[0]["answer"] == 42:
                _ok("trailing semicolon tolerated")
            else:
                _fail("trailing semicolon tolerated", f"got {result.rows}")
        except QueryGuardrailViolation as e:
            _fail("trailing semicolon tolerated", f"rejected: {e}")

        # 10. Empty query rejected
        try:
            svc.execute_sql("   ")
            _fail("empty query rejected", "allowed")
        except QueryGuardrailViolation:
            _ok("empty query rejected")

        # 11. Codex finding 1: DuckDB file-read functions blocked
        file_read_queries = [
            "SELECT * FROM read_csv_auto('output/patients.csv') LIMIT 1",
            "SELECT * FROM read_csv('anywhere.csv')",
            "SELECT * FROM read_parquet('x.parquet')",
            "SELECT * FROM read_json('y.json')",
            "SELECT * FROM glob('*')",
        ]
        all_blocked = True
        for q in file_read_queries:
            try:
                svc.execute_sql(q)
                _fail(f"file-read blocked: {q.split('(')[0].split()[-1]}", "ran")
                all_blocked = False
                break
            except QueryGuardrailViolation:
                pass
        if all_blocked:
            _ok("file-read table functions blocked",
                f"{len(file_read_queries)} variants tested")

        # 12. Codex finding 2: PRAGMA no longer in allow-list
        try:
            svc.execute_sql("PRAGMA version")
            _fail("PRAGMA rejected", "allowed")
        except QueryGuardrailViolation:
            _ok("PRAGMA rejected (no longer in allow-list)")

        # 13. String literals don't trigger false positives
        try:
            # answer_canonical contains medication names like 'COPY_READY' or
            # arbitrary strings; a literal must not be mistaken for a keyword.
            result = svc.execute_sql(
                "SELECT ? AS label",
                ["please copy the form and insert it in the drop box"],
            )
            if result.row_count == 1:
                _ok("string literals don't trigger false positives",
                    "literal with forbidden words passed")
            else:
                _fail("string literals don't trigger false positives",
                      f"got {result.rows}")
        except QueryGuardrailViolation as e:
            _fail("string literals don't trigger false positives",
                  f"rejected: {e}")

        # 14. Ground-truth: DuckDB aggregates match Pandas aggregates
        # on the same data. If the zero-copy view ever stopped pointing at
        # our DataFrames (or coerced dtypes behind our back), this breaks.
        import pandas as pd
        raw_mapping = pd.read_csv(config.MAPPING_TABLE)
        pandas_bmi_count = int(
            (raw_mapping["clinical_category"] == "BMI_MEASUREMENT").sum()
        )
        duck = svc.execute_sql(
            "SELECT COUNT(*) AS n FROM mapping_table WHERE clinical_category = ?",
            ["BMI_MEASUREMENT"],
        )
        duck_bmi_count = int(duck.rows[0]["n"]) if duck.rows else -1
        if duck_bmi_count == pandas_bmi_count and duck_bmi_count > 0:
            _ok("DuckDB count matches Pandas count (BMI_MEASUREMENT mapping rows)",
                f"both={duck_bmi_count}")
        else:
            _fail("DuckDB count matches Pandas count (BMI_MEASUREMENT mapping rows)",
                  f"duckdb={duck_bmi_count}, pandas={pandas_bmi_count}")

        # 15. Ground-truth: DuckDB per-patient row count matches Pandas.
        raw_survey = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
        some_uid = int(raw_survey["user_id"].dropna().astype(int).iloc[0])
        pandas_row_count = int((raw_survey["user_id"] == some_uid).sum())
        duck = svc.execute_sql(
            "SELECT COUNT(*) AS n FROM survey_unified WHERE user_id = ?",
            [some_uid],
        )
        duck_row_count = int(duck.rows[0]["n"]) if duck.rows else -1
        if duck_row_count == pandas_row_count:
            _ok("DuckDB per-patient count matches Pandas",
                f"uid={some_uid}, both={duck_row_count}")
        else:
            _fail("DuckDB per-patient count matches Pandas",
                  f"uid={some_uid}, duck={duck_row_count}, pandas={pandas_row_count}")

    finally:
        svc.close()

    return _report_and_exit()


if __name__ == "__main__":
    sys.exit(main())
