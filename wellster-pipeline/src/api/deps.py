"""Dependency injection for the FastAPI app.

Holds the shared singletons (Repository, QueryService, mapping path) so each
request does not re-parse the artifact files. The objects are created at
app startup and reused for the lifetime of the process.

If the pipeline has not been run (output artifacts missing), startup still
succeeds but the state is marked `not ready` so `/health` can report it
honestly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from threading import Lock
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from src.datastore import UnifiedDataRepository
from src.query_service import DuckDBQueryService


SEMANTIC_MAPPING_PATH = config.OUTPUT_DIR / "semantic_mapping.json"


class AppState:
    """Lifetime-scoped singletons shared by every request."""

    def __init__(self) -> None:
        self.ready: bool = False
        self.repo: UnifiedDataRepository | None = None
        self.query: DuckDBQueryService | None = None
        self._mapping_lock = Lock()  # protects concurrent PATCH /mapping/{cat}

    def try_load(self) -> None:
        """Best-effort: load artifacts if present, otherwise stay 'not ready'.

        If any of the expected CSV artifacts is missing, malformed, or
        cannot be opened by DuckDB, we log the failure and leave the state
        as not-ready. The API then responds with 503 on all data
        endpoints but `/health` still works and reports the degraded state
        honestly.
        """
        if not config.MAPPING_TABLE.exists():
            return
        try:
            self.repo = UnifiedDataRepository.from_output_dir()
            self.query = DuckDBQueryService(self.repo)
            self.ready = True
        except Exception as exc:
            # Keep the app up even when artifacts are partial/corrupt.
            print(
                f"[API] Degraded startup: could not load artifacts "
                f"({type(exc).__name__}: {exc})"
            )
            if self.query is not None:
                try:
                    self.query.close()
                except Exception:
                    pass
            self.repo = None
            self.query = None
            self.ready = False

    def close(self) -> None:
        if self.query is not None:
            self.query.close()
        self.query = None
        self.repo = None
        self.ready = False

    # --- Mapping file helpers (atomic read/write under the lock) -----------

    def read_mapping(self) -> dict[str, Any]:
        if not SEMANTIC_MAPPING_PATH.exists():
            return {}
        return json.loads(SEMANTIC_MAPPING_PATH.read_text(encoding="utf-8"))

    def write_mapping(self, mapping: dict[str, Any]) -> None:
        SEMANTIC_MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEMANTIC_MAPPING_PATH.write_text(
            json.dumps(mapping, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def mapping_lock(self) -> Lock:
        return self._mapping_lock


# Module-level singleton. FastAPI will populate it on startup.
state = AppState()


# --- FastAPI dependency callables -----------------------------------------


def get_state() -> AppState:
    return state


def get_repo() -> UnifiedDataRepository:
    if state.repo is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Pipeline artifacts not loaded. Run `python pipeline.py` first.",
        )
    return state.repo


def get_query() -> DuckDBQueryService:
    if state.query is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Pipeline artifacts not loaded. Run `python pipeline.py` first.",
        )
    return state.query


def get_mapping_state() -> AppState:
    """Require both the unified artifacts AND semantic_mapping.json.

    Mapping endpoints depend on the AI-generated mapping existing — not just
    the pipeline CSVs. If someone ran the pipeline before the semantic
    mapping stage existed, this route family must degrade to 503 rather
    than silently returning an empty list.
    """
    from fastapi import HTTPException
    if state.repo is None:
        raise HTTPException(
            status_code=503,
            detail="Pipeline artifacts not loaded. Run `python pipeline.py` first.",
        )
    if not SEMANTIC_MAPPING_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "semantic_mapping.json missing — re-run pipeline.py so the "
                "AI mapping stage generates it."
            ),
        )
    return state
