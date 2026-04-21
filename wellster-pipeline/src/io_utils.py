"""Shared IO helpers.

`atomic_write_json` is the only public function right now. It writes a
JSON document to disk through a sibling temp-file + `os.replace`, which
is atomic on both POSIX and Windows. Concurrent readers of the target
file therefore observe either the previous complete version or the new
complete version — never a half-written state.

Windows-specific retry: on Windows, `os.replace` raises PermissionError
if another process holds the target file open for reading at the moment
of the rename. The OS typically releases the handle within a few
milliseconds, so a short exponential-backoff retry is all that is
needed. Without this, a writer thread can crash mid-rename while busy
API readers are polling the same file — which was the false-green
Codex flagged on the mapping PATCH path.
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
