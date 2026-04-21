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
from src.io_utils import AtomicReadError, atomic_read_json, atomic_write_json
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

    # --- Mapping file helpers ---------------------------------------------
    #
    # Writes go through `tempfile + os.replace` which is atomic on both
    # POSIX and Windows (documented since Python 3.3). Readers therefore
    # never see a half-written file — they observe either the previous
    # version or the new version in its entirety. This makes the
    # readers lock-free without risking partial-JSON 500s during PATCH.
    #
    # `read_mapping` additionally tolerates a malformed file (e.g. a
    # manual edit went wrong) by returning {} and logging. Callers must
    # treat an empty mapping as "degraded" rather than "no entries" when
    # they care about the distinction — `/health` does, `get_mapping_state`
    # enforces it.

    def read_mapping(self) -> dict[str, Any]:
        """Read semantic_mapping.json, retrying on Windows permission races.

        Returns `{}` only for genuine failures (missing file, malformed
        JSON, or an exhausted-retry permission error). A transient
        `PermissionError` caused by a concurrent `atomic_write_json`
        would previously flip this to `{}` and spuriously flag the
        system as degraded — we now retry through it before giving up.
        """
        if not SEMANTIC_MAPPING_PATH.exists():
            return {}
        try:
            return atomic_read_json(SEMANTIC_MAPPING_PATH)
        except json.JSONDecodeError as exc:
            print(
                f"[API] semantic_mapping.json is malformed "
                f"({type(exc).__name__}: {exc.msg} at line {exc.lineno}) — "
                f"serving as degraded until fixed"
            )
            return {}
        except AtomicReadError as exc:
            # All retries exhausted — the file is genuinely locked or
            # permissions are broken, not just racing with a PATCH.
            print(f"[API] Could not read semantic_mapping.json: {exc}")
            return {}
        except OSError as exc:
            # Anything else (ENOENT raced after exists(), I/O errors).
            print(f"[API] Could not read semantic_mapping.json: {exc}")
            return {}

    def write_mapping(self, mapping: dict[str, Any]) -> None:
        # Atomicity + Windows PermissionError retry live in the shared
        # util so pipeline-side writers (semantic_mapping_ai) share the
        # exact same write semantics as the API PATCH path.
        atomic_write_json(SEMANTIC_MAPPING_PATH, mapping)

    def mapping_file_is_healthy(self) -> bool:
        """True if semantic_mapping.json exists and parses as JSON.

        Uses the same retrying read as `read_mapping` so a health
        probe that races against a PATCH does not spuriously report
        the mapping as malformed.
        """
        if not SEMANTIC_MAPPING_PATH.exists():
            return False
        try:
            atomic_read_json(SEMANTIC_MAPPING_PATH)
        except (json.JSONDecodeError, AtomicReadError, OSError):
            return False
        return True

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
    """Require artifacts loaded AND semantic_mapping.json present and parseable.

    Three ways to degrade:
        1. Pipeline never ran → 503 with "run pipeline.py" message.
        2. semantic_mapping.json missing → 503 with "re-run pipeline" message.
        3. semantic_mapping.json malformed (JSON parse error) → 503 with
           "file corrupt" message, not a 500 surface. The Phase-5 review UI
           can have bugs that write broken JSON; we want to survive.
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
    if not state.mapping_file_is_healthy():
        raise HTTPException(
            status_code=503,
            detail=(
                "semantic_mapping.json exists but is malformed. "
                "Restore from backup or re-run the pipeline."
            ),
        )
    return state
