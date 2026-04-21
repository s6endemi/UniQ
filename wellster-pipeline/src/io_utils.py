"""Shared IO helpers.

Two public functions here, mirroring each other:

    atomic_write_json  — write through tempfile + os.replace
    atomic_read_json   — read with retry-on-PermissionError

Both need retry loops on Windows. The write path races because
`os.replace` can fail with `PermissionError` if *any* concurrent reader
has a share-incompatible handle on the target. The read path races
symmetrically: `open()` can fail with `PermissionError` in the brief
window between a writer's `mkstemp` and its `os.replace` when the OS
has not yet fully transitioned the handle. Both resolve within a few
ms, so short exponential-backoff handles them invisibly.

Why readers retry too (second Codex round-trip): if callers swallow
`OSError` on read — as `deps.read_mapping` does to degrade gracefully
on a truly broken file — then a transient `PermissionError` from
concurrent writes would be indistinguishable from genuine corruption.
Retrying below the caller distinguishes the two without forcing every
consumer to reimplement backoff.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class AtomicWriteError(Exception):
    """Raised when an atomic JSON write fails even after retries."""


class AtomicReadError(Exception):
    """Raised when an atomic JSON read fails even after retries.

    Only thrown for persistent permission / locking failures. Missing
    files and malformed JSON are re-raised as their original exceptions
    so callers can distinguish them — "file gone" and "file corrupt"
    are both legitimate, distinct error modes.
    """


def atomic_write_json(
    path: Path,
    data: Any,
    *,
    indent: int = 2,
    max_retries: int = 10,
    retry_base_delay: float = 0.02,  # 20 ms; scales 1.5x per retry
) -> None:
    """Write `data` to `path` as JSON via tempfile + os.replace.

    Args:
        path: Destination file. Parent directory is created if missing.
        data: JSON-serialisable Python object.
        indent: Pretty-print indent for the JSON output.
        max_retries: How many times to retry `os.replace` on Windows
            `PermissionError`. With base 20 ms and factor 1.5, the total
            worst-case wait is under ~1 second for 10 attempts.
        retry_base_delay: Initial sleep between retries, in seconds.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=indent, ensure_ascii=False)

    fd, tmp_path_str = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                os.replace(tmp_path, path)
                return
            except PermissionError as exc:
                last_error = exc
                if attempt == max_retries - 1:
                    break
                time.sleep(retry_base_delay * (1.5 ** attempt))
        raise AtomicWriteError(
            f"os.replace({tmp_path} -> {path}) failed after "
            f"{max_retries} attempts: {last_error}"
        ) from last_error
    except Exception:
        # Don't leak the temp file if anything above failed before or
        # during os.replace's final success.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def atomic_read_json(
    path: Path,
    *,
    max_retries: int = 10,
    retry_base_delay: float = 0.02,  # 20 ms; scales 1.5x per retry
) -> Any:
    """Read a JSON file with retry on Windows `PermissionError`.

    Behaviour:
        - Returns the parsed JSON on success.
        - Raises `FileNotFoundError` if the file does not exist (no
          retry — callers typically want to treat "missing" as a real
          signal, not mask it).
        - Raises `json.JSONDecodeError` if the file content is
          malformed (no retry — the content does not change by waiting).
        - Retries on `PermissionError` with the same exponential
          backoff as `atomic_write_json`. After `max_retries` attempts
          raises `AtomicReadError`.

    Note that the read is performed inside the retry loop too: each
    attempt opens the file fresh, so a transient lock that clears mid-
    attempt still succeeds on the next try.
    """
    if not path.exists():
        # Consistent with read_text's error surface; callers that want
        # to treat missing-as-empty should check existence first.
        raise FileNotFoundError(path)

    last_error: PermissionError | None = None
    for attempt in range(max_retries):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            time.sleep(retry_base_delay * (1.5 ** attempt))
    assert last_error is not None  # only reachable through the except branch
    raise AtomicReadError(
        f"read_text({path}) failed after {max_retries} attempts: {last_error}"
    ) from last_error
