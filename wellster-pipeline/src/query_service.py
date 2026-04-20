"""UniQ Query Service — DuckDB-backed read-only SQL over the unified data.

Single entry point for anything that wants to ask SQL questions against the
pipeline artifacts: FastAPI routers, the chatbot tool-use agent, the
Streamlit query widget, downstream analytics. Repository DataFrames are
registered as DuckDB views (zero-copy) so queries run in-process without a
separate database server.

Phase 3B scope:
    - Schema introspection (`schema`, `list_categories`).
    - Read-only SQL execution with hard row cap + statement timeout.
    - Parameterized queries to avoid naive string interpolation.

Guardrails (demo-grade, not prod):
    - First-word allow-list: query must start with SELECT / WITH / PRAGMA /
      SHOW / DESCRIBE. Anything else rejected before DuckDB even sees it.
    - Semicolons forbidden — no stacked statements, no "SELECT 1; DROP ..."
      trickery.
    - Row cap via LIMIT wrap (primary runaway-query safeguard).

Not yet enforced (Phase 7 polish):
    - Query timeout. DuckDB 1.5 has no built-in `statement_timeout`; a
      thread-based `interrupt()` watchdog can be added before productionising.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.datastore import UnifiedDataRepository


_ALLOWED_FIRST_WORDS: frozenset[str] = frozenset({
    "select", "with", "show", "describe"
})

# Token-level denylist. Any of these as a bare word in the SQL triggers a
# guardrail violation, even inside SELECT/WITH queries. Covers:
#   - DuckDB filesystem/network table functions (read_csv, read_parquet, ...)
#   - DDL/DML verbs that could sneak in through subqueries or weird parses
#   - Database-level operations (attach, install, load, copy, export)
#   - Connection state mutation (set, reset, pragma)
#
# This is a blacklist, not an allowlist — false positives are possible if a
# user column is ever named exactly one of these words. None of our current
# tables have such columns, but if a future consumer hits this, the fix is to
# quote the identifier: `"copy"` instead of copy.
_FORBIDDEN_TOKENS: frozenset[str] = frozenset({
    # File / network table functions
    "read_csv", "read_csv_auto", "read_parquet", "read_json",
    "read_json_auto", "read_json_objects", "read_ndjson", "read_blob",
    "read_text", "read_xlsx", "glob",
    # DDL / DML
    "insert", "update", "delete", "drop", "truncate", "alter", "create",
    # Database-level operations
    "attach", "detach", "copy", "export", "import", "install", "load",
    "call", "vacuum",
    # Connection state
    "set", "reset", "pragma",
})

_TOKEN_RE = re.compile(r"\b\w+\b")
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")

DEFAULT_MAX_ROWS = 10_000
DEFAULT_TIMEOUT_SECONDS = 30


class QueryGuardrailViolation(Exception):
    """Raised when a query fails pre-execution safety checks."""


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    columns: list[str]
    row_count: int
    truncated: bool  # True if we hit the max_rows cap

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=self.columns)


# The tables registered as DuckDB views. Ordered to keep `survey_unified`
# first since that is the event-store other tables are ultimately derived
# from (and the primary target of chatbot queries).
_REGISTERED_TABLES: tuple[str, ...] = (
    "survey_unified",
    "patients",
    "treatment_episodes",
    "bmi_timeline",
    "medication_history",
    "mapping_table",
    "quality_report",
)


class DuckDBQueryService:
    """Read-only SQL interface over the unified pipeline artifacts."""

    def __init__(
        self,
        repo: UnifiedDataRepository,
        *,
        max_rows: int = DEFAULT_MAX_ROWS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._repo = repo
        self._max_rows = max_rows
        self._timeout_seconds = timeout_seconds
        self._con = duckdb.connect(database=":memory:")
        self._register_views()

    @classmethod
    def from_output_dir(
        cls,
        output_dir: Path | None = None,
        **kwargs: Any,
    ) -> DuckDBQueryService:
        return cls(UnifiedDataRepository.from_output_dir(output_dir), **kwargs)

    # ---- Wiring ----------------------------------------------------------

    def _register_views(self) -> None:
        name_to_df: dict[str, pd.DataFrame] = {
            "survey_unified": self._repo.survey,
            "patients": self._repo.patients,
            "treatment_episodes": self._repo.episodes,
            "bmi_timeline": self._repo.bmi_timeline,
            "medication_history": self._repo.medication_history,
            "mapping_table": self._repo.mapping,
            "quality_report": self._repo.quality_report,
        }
        for name, df in name_to_df.items():
            self._con.register(name, df)

    # ---- Introspection ---------------------------------------------------

    def schema(self) -> dict[str, list[dict[str, str]]]:
        """Return {table_name: [{column, type}, ...]} for every registered view."""
        schema: dict[str, list[dict[str, str]]] = {}
        for table in _REGISTERED_TABLES:
            rows = self._con.execute(f"DESCRIBE {table}").fetchall()
            schema[table] = [{"column": r[0], "type": r[1]} for r in rows]
        return schema

    def list_categories(self) -> list[str]:
        """Distinct clinical_category values from mapping_table — chatbot context."""
        sql = (
            "SELECT DISTINCT clinical_category FROM mapping_table "
            "WHERE clinical_category IS NOT NULL ORDER BY 1"
        )
        return [r[0] for r in self._con.execute(sql).fetchall()]

    def sample(self, table: str, n: int = 5) -> list[dict[str, Any]]:
        """First N rows of a registered table — helps an AI see data shape."""
        if table not in _REGISTERED_TABLES:
            raise QueryGuardrailViolation(
                f"Unknown table {table!r}. Known: {list(_REGISTERED_TABLES)}"
            )
        n = min(max(1, n), 100)
        cursor = self._con.execute(f"SELECT * FROM {table} LIMIT {n}")
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, r)) for r in rows]

    # ---- Execution -------------------------------------------------------

    def execute_sql(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> QueryResult:
        """Run a read-only SQL query with guardrails and row cap."""
        self._enforce_guardrails(sql)
        bounded_sql = self._wrap_with_row_cap(sql)

        cursor = self._con.execute(bounded_sql, params or [])
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []

        truncated = len(rows) > self._max_rows
        if truncated:
            rows = rows[: self._max_rows]

        dict_rows = [dict(zip(columns, r)) for r in rows]
        return QueryResult(
            rows=dict_rows,
            columns=columns,
            row_count=len(dict_rows),
            truncated=truncated,
        )

    # ---- Guardrails ------------------------------------------------------

    def _enforce_guardrails(self, sql: str) -> None:
        stripped = sql.strip()
        if not stripped:
            raise QueryGuardrailViolation("Empty query")

        first_word = stripped.split(None, 1)[0].lower()
        if first_word not in _ALLOWED_FIRST_WORDS:
            raise QueryGuardrailViolation(
                f"Query must start with one of {sorted(_ALLOWED_FIRST_WORDS)} "
                f"— got {first_word!r}"
            )

        # No stacked statements. A lone trailing semicolon is tolerated.
        body_without_trailing_semi = stripped.rstrip(";").rstrip()
        if ";" in body_without_trailing_semi:
            raise QueryGuardrailViolation(
                "Stacked statements are not allowed (extra semicolon found)"
            )

        # Token-level denylist. Scan after stripping string literals so a
        # harmless WHERE answer_value = 'please read_csv the form' does not
        # trigger the read_csv check.
        without_strings = _STRING_LITERAL_RE.sub("''", stripped.lower())
        bad_tokens = [
            tok for tok in _TOKEN_RE.findall(without_strings)
            if tok in _FORBIDDEN_TOKENS
        ]
        if bad_tokens:
            raise QueryGuardrailViolation(
                f"Forbidden token(s): {sorted(set(bad_tokens))}. "
                f"File/network readers, DDL, DML, and connection-state "
                f"statements are blocked on this endpoint."
            )

    def _wrap_with_row_cap(self, sql: str) -> str:
        """Enforce the row cap by wrapping the user's query in an outer LIMIT.

        We fetch `max_rows + 1` so we can detect truncation (caller sees
        `truncated=True` when the cap bites).
        """
        clean = sql.strip().rstrip(";").rstrip()
        return f"SELECT * FROM ({clean}) AS _user_query LIMIT {self._max_rows + 1}"

    # ---- Lifecycle -------------------------------------------------------

    def close(self) -> None:
        self._con.close()


if __name__ == "__main__":
    svc = DuckDBQueryService.from_output_dir()
    try:
        print("=== Schema ===")
        for table, cols in svc.schema().items():
            print(f"  {table}: {len(cols)} columns")

        print(f"\n=== Categories ({len(svc.list_categories())}) ===")
        for cat in svc.list_categories()[:5]:
            print(f"  - {cat}")
        print("  ...")

        print("\n=== Sample query: BMI row count per product ===")
        result = svc.execute_sql(
            """
            SELECT product, COUNT(*) AS rows
            FROM survey_unified
            WHERE clinical_category = ?
              AND product IS NOT NULL
            GROUP BY product
            ORDER BY rows DESC
            LIMIT 5
            """,
            ["BMI_MEASUREMENT"],
        )
        for row in result.rows:
            print(f"  {row}")
    finally:
        svc.close()
