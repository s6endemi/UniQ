"""Materialization manifest — proof that an output set was produced from a known input.

Each pipeline run writes `output/materialization_manifest.json` with hashes
across every governance-relevant artifact:

- `run_id` and timestamp
- input file hash + row count
- taxonomy hash (the AI-discovered category set)
- semantic mapping hash + per-status counts
- normalization registry hash + coverage stats
- per-output-table row count + content hash
- normalization queue depth (open / promoted / dismissed)
- git commit (if available — best effort, non-blocking)

The point is enterprise-defensibility: when a clinician asks
*"can you reproduce the substrate state from last Tuesday?"*, the
manifest is the answer. Same input + same hashes = identical output.
The manifest itself is small (<5 KB), human-readable JSON, and
exposed in `/v1/substrate/manifest` so consumers can verify what
they're querying.

The module is intentionally non-invasive: failures during manifest
generation degrade gracefully (the substrate is still valid; the
manifest is just less complete).
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # type: ignore[import-not-found]

from src.io_utils import atomic_read_json, atomic_write_json


MANIFEST_FILE = Path(config.OUTPUT_DIR) / "materialization_manifest.json"
MANIFEST_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:10]}"


def _hash_file(path: Path) -> str | None:
    """SHA-256 of file content. None if file missing or unreadable."""
    if not path.exists() or not path.is_file():
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _hash_dataframe(df: pd.DataFrame) -> str | None:
    """Stable SHA-256 of a dataframe via deterministic CSV serialisation."""
    try:
        h = hashlib.sha256()
        # to_csv with deterministic row order + no index keeps the hash
        # reproducible across Pandas versions (within the same dtypes).
        h.update(df.to_csv(index=False).encode("utf-8"))
        return h.hexdigest()
    except Exception:
        return None


def _file_row_count_csv(path: Path) -> int | None:
    if not path.exists():
        return None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                sample = f.read(8192)
                f.seek(0)
                first_line = sample.splitlines()[0] if sample.splitlines() else ""
                delimiter = "\t" if first_line.count("\t") > first_line.count(",") else ","
                reader = csv.reader(f, delimiter=delimiter)
                return max(0, sum(1 for _ in reader) - 1)
        except UnicodeDecodeError:
            continue
        except (OSError, csv.Error):
            return None
    return None


def _git_commit() -> str | None:
    """Best-effort current git commit. None if not in a repo or git unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _semantic_mapping_stats() -> dict[str, Any]:
    path = Path(config.OUTPUT_DIR) / "semantic_mapping.json"
    if not path.exists():
        return {"file_hash": None, "categories": 0, "by_status": {}}
    try:
        data = atomic_read_json(path)
    except Exception:
        return {"file_hash": _hash_file(path), "categories": 0, "by_status": {}}
    if not isinstance(data, dict):
        return {"file_hash": _hash_file(path), "categories": 0, "by_status": {}}
    by_status: dict[str, int] = {}
    count = 0
    for category, entry in data.items():
        if category.startswith("__") or not isinstance(entry, dict):
            continue
        count += 1
        status = str(entry.get("review_status", "pending"))
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "file_hash": _hash_file(path),
        "categories": count,
        "by_status": by_status,
    }


def _normalization_stats() -> dict[str, Any]:
    """Pull coverage from the registry + queue without importing them
    eagerly (avoids circular-import risk if those modules ever grow)."""
    try:
        from src.normalization_registry import NormalizationRegistry

        reg = NormalizationRegistry.from_disk()
        registry_stats = reg.coverage_stats()
    except Exception:
        registry_stats = {}

    try:
        from src.normalization_queue import NormalizationQueue

        queue = NormalizationQueue.from_disk()
        queue_stats = queue.stats()
    except Exception:
        queue_stats = {}

    reg_path = Path(config.OUTPUT_DIR) / "answer_normalization.json"
    queue_path = Path(config.OUTPUT_DIR) / "normalization_queue.json"
    return {
        "registry_hash": _hash_file(reg_path),
        "registry_stats": registry_stats,
        "queue_hash": _hash_file(queue_path),
        "queue_stats": queue_stats,
    }


def _output_table_stats() -> dict[str, dict[str, Any]]:
    """Per-CSV row count + hash for every output table."""
    output_dir = Path(config.OUTPUT_DIR)
    files = [
        "patients.csv",
        "bmi_timeline.csv",
        "medication_history.csv",
        "treatment_episodes.csv",
        "quality_report.csv",
        "survey_unified.csv",
        "mapping_table.csv",
    ]
    out: dict[str, dict[str, Any]] = {}
    for filename in files:
        path = output_dir / filename
        out[filename] = {
            "row_count": _file_row_count_csv(path),
            "file_hash": _hash_file(path),
        }
    try:
        from src.datastore import UnifiedDataRepository

        repo = UnifiedDataRepository.from_output_dir()
        validated = repo.survey_validated
        out["survey_validated"] = {
            "row_count": len(validated),
            "file_hash": _hash_dataframe(validated),
        }
    except Exception:
        out["survey_validated"] = {
            "row_count": None,
            "file_hash": None,
        }
    return out


def _input_stats() -> dict[str, Any]:
    """Hash + row count of the raw input file (if locally available)."""
    raw = Path(config.RAW_DATA_FILE)
    return {
        "path": str(raw.relative_to(raw.parent.parent.parent))
        if raw.exists()
        else str(raw),
        "exists": raw.exists(),
        "file_hash": _hash_file(raw),
        "row_count": _file_row_count_csv(raw),
    }


def _taxonomy_stats() -> dict[str, Any]:
    path = Path(config.OUTPUT_DIR) / "taxonomy.json"
    return {
        "file_hash": _hash_file(path),
        "exists": path.exists(),
    }


def build_manifest() -> dict[str, Any]:
    """Compute the current manifest in memory. Idempotent."""
    return {
        "version": MANIFEST_VERSION,
        "run_id": _new_run_id(),
        "generated_at": _now_iso(),
        "git_commit": _git_commit(),
        "input": _input_stats(),
        "taxonomy": _taxonomy_stats(),
        "semantic_mapping": _semantic_mapping_stats(),
        "normalization": _normalization_stats(),
        "output_tables": _output_table_stats(),
    }


def write_manifest(*, save: bool = True) -> dict[str, Any]:
    """Generate + persist the manifest. Returns the manifest dict."""
    manifest = build_manifest()
    if save:
        atomic_write_json(MANIFEST_FILE, manifest)
    return manifest


def load_manifest() -> dict[str, Any] | None:
    """Read the most recently persisted manifest, if any."""
    if not MANIFEST_FILE.exists():
        return None
    try:
        data = atomic_read_json(MANIFEST_FILE)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    manifest = write_manifest(save=True)
    print(f"materialization manifest written | run_id={manifest['run_id']}")
    print()
    print(f"git commit          : {manifest['git_commit'] or '(unavailable)'}")
    print(f"input rows          : {manifest['input'].get('row_count')}")
    sm = manifest["semantic_mapping"]
    print(f"mapping categories  : {sm['categories']}  by_status={sm['by_status']}")
    nr = manifest["normalization"]
    print(f"normalization stats : {nr.get('registry_stats')}")
    print(f"queue stats         : {nr.get('queue_stats')}")
    print()
    print("output tables:")
    for fn, info in manifest["output_tables"].items():
        h = info.get("file_hash")
        h_short = (h[:12] + "…") if h else "(missing)"
        print(f"  {fn:<28} rows={info.get('row_count'):>8}  hash={h_short}")
