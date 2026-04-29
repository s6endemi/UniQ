"""Explicit guardrail tests for the analyst SQL runtime.

These duplicate the security-critical subset from `test_query_service.py`
under a dedicated filename so the Wellster technical follow-up can point
to a direct, reviewable test surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.query_service import DuckDBQueryService, QueryGuardrailViolation


_results: list[tuple[str, str, str]] = []


def _ok(name: str, detail: str = "") -> None:
    _results.append(("OK", name, detail))


def _fail(name: str, detail: str) -> None:
    _results.append(("FAIL", name, detail))


def _expect_blocked(service: DuckDBQueryService, name: str, sql: str) -> None:
    try:
        service.execute_sql(sql)
        _fail(name, "query was allowed")
    except QueryGuardrailViolation:
        _ok(name)


def _report_and_exit() -> int:
    icons = {"OK": "[OK]", "FAIL": "[X]"}
    for status, name, detail in _results:
        print(f"  {icons[status]} {name}" + (f" -- {detail}" if detail else ""))
    passes = sum(1 for s, *_ in _results if s == "OK")
    fails = sum(1 for s, *_ in _results if s == "FAIL")
    print(f"\n{passes} pass, {fails} fail")
    return 1 if fails else 0


def main() -> int:
    service = DuckDBQueryService.from_output_dir(max_rows=5)
    try:
        _expect_blocked(
            service,
            "read_csv_auto blocked",
            "SELECT * FROM read_csv_auto('output/patients.csv')",
        )
        _expect_blocked(service, "DROP TABLE blocked", "DROP TABLE patients")
        _expect_blocked(service, "stacked statements blocked", "SELECT 1; SELECT 2")
        _expect_blocked(service, "ATTACH blocked", "ATTACH DATABASE 'x'")
        _expect_blocked(service, "PRAGMA blocked", "PRAGMA version")
        _expect_blocked(service, "COPY blocked inside SELECT", "SELECT copy FROM patients")

        result = service.execute_sql("SELECT * FROM mapping_table")
        if result.row_count == 5 and result.truncated:
            _ok("row cap truncates long result", "max_rows=5")
        else:
            _fail(
                "row cap truncates long result",
                f"row_count={result.row_count}, truncated={result.truncated}",
            )
    finally:
        service.close()

    return _report_and_exit()


if __name__ == "__main__":
    raise SystemExit(main())
