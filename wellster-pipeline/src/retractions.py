"""Patient retraction / erasure support for the materialized substrate.

This is the minimum compliance surface for a pilot: a patient can be
removed from every materialized output table, annotations are removed,
and a pseudonymized tombstone remains so future re-materializations do
not silently re-expose the same patient from raw source exports.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # type: ignore[import-not-found]

from src.io_utils import AtomicReadError, atomic_read_json, atomic_write_json


TOMBSTONE_FILE = Path(config.OUTPUT_DIR) / "retraction_tombstones.json"
TOMBSTONE_VERSION = 2

_HASH_PREFIX = "uniq-retraction-v2"
_HASH_SCHEME = "hmac-sha256-v2"
_MIN_SECRET_LENGTH = 32
_CSV_OUTPUTS_WITH_PATIENT_ID = (
    "patients.csv",
    "treatment_episodes.csv",
    "bmi_timeline.csv",
    "medication_history.csv",
    "quality_report.csv",
    "survey_unified.csv",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_secret() -> bytes:
    secret = os.environ.get("UNIQ_RETRACTION_HASH_SECRET") or getattr(
        config,
        "RETRACTION_HASH_SECRET",
        "",
    )
    if not secret:
        raise RuntimeError(
            "UNIQ_RETRACTION_HASH_SECRET is required for patient retraction "
            "tombstones. Set it in the environment or wellster-pipeline/.env."
        )
    if len(secret) < _MIN_SECRET_LENGTH:
        raise RuntimeError(
            "UNIQ_RETRACTION_HASH_SECRET must be at least "
            f"{_MIN_SECRET_LENGTH} characters."
        )
    return secret.encode("utf-8")


def patient_hash(user_id: int) -> str:
    """Deterministic HMAC tombstone key for a patient id.

    This is pseudonymization, not anonymization: the server-side secret is
    required to recompute the key. Never store the secret in git.
    """
    payload = f"{_HASH_PREFIX}:{int(user_id)}".encode("utf-8")
    return hmac.new(_hash_secret(), payload, hashlib.sha256).hexdigest()


def _empty_store() -> dict[str, Any]:
    return {"version": TOMBSTONE_VERSION, "tombstones": []}


def load_tombstones(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or TOMBSTONE_FILE
    if not target.exists():
        return []
    try:
        data = atomic_read_json(target)
    except AtomicReadError:
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("tombstones")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _active_tombstone_entries(path: Path | None = None) -> list[dict[str, Any]]:
    active = [
        entry
        for entry in load_tombstones(path)
        if entry.get("patient_hash")
        and str(entry.get("status", "active")) == "active"
    ]
    legacy = [
        entry for entry in active
        if str(entry.get("hash_scheme", "")) != _HASH_SCHEME
    ]
    if legacy:
        raise RuntimeError(
            "Active retraction tombstones use an unsupported legacy hash "
            "scheme. Restore or migrate them before serving patient data."
        )
    return active


def active_patient_hashes(path: Path | None = None) -> set[str]:
    return {
        str(entry.get("patient_hash"))
        for entry in _active_tombstone_entries(path)
    }


def is_patient_retracted(user_id: int, path: Path | None = None) -> bool:
    active_hashes = active_patient_hashes(path)
    if not active_hashes:
        return False
    return patient_hash(user_id) in active_hashes


def filter_retracted_dataframe(
    df: pd.DataFrame,
    *,
    user_id_column: str = "user_id",
    tombstone_path: Path | None = None,
) -> pd.DataFrame:
    """Return `df` without rows whose user_id is in the tombstone set."""
    hashes = active_patient_hashes(tombstone_path)
    if not hashes or user_id_column not in df.columns or df.empty:
        return df

    numeric_ids = pd.to_numeric(df[user_id_column], errors="coerce")

    def _is_retracted(value: Any) -> bool:
        if pd.isna(value):
            return False
        try:
            return patient_hash(int(value)) in hashes
        except (TypeError, ValueError):
            return False

    mask = numeric_ids.apply(_is_retracted)
    if not bool(mask.any()):
        return df
    return df[~mask].reset_index(drop=True)


def _atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, path)


def _purge_csv(path: Path, user_id: int) -> int:
    if not path.exists():
        return 0
    df = pd.read_csv(path, low_memory=False)
    if "user_id" not in df.columns:
        return 0
    before = len(df)
    numeric_ids = pd.to_numeric(df["user_id"], errors="coerce")
    filtered = df[(numeric_ids.isna()) | (numeric_ids != int(user_id))].reset_index(drop=True)
    removed = before - len(filtered)
    if removed:
        _atomic_write_csv(filtered, path)
    return int(removed)


def _purge_annotations(output_dir: Path, user_id: int) -> int:
    path = output_dir / "clinical_annotations.json"
    if not path.exists():
        return 0
    try:
        data = atomic_read_json(path)
    except Exception:
        return 0
    if not isinstance(data, dict) or not isinstance(data.get("annotations"), list):
        return 0
    annotations = [a for a in data["annotations"] if isinstance(a, dict)]
    before = len(annotations)
    kept = [
        ann
        for ann in annotations
        if int(ann.get("patient_id", -1)) != int(user_id)
    ]
    removed = before - len(kept)
    if removed:
        atomic_write_json(
            path,
            {
                **data,
                "annotations": kept,
            },
        )
    return int(removed)


def append_tombstone(
    *,
    user_id: int,
    deleted_by: str,
    reason: str,
    table_counts: dict[str, int],
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or TOMBSTONE_FILE
    store = _empty_store()
    existing = load_tombstones(target)
    store["tombstones"] = existing
    record = {
        "id": f"ret-{uuid.uuid4().hex[:10]}",
        "patient_hash": patient_hash(user_id),
        "hash_scheme": _HASH_SCHEME,
        "status": "active",
        "deleted_at": _now_iso(),
        "deleted_by": deleted_by,
        "reason": reason,
        "tables": table_counts,
        "total_rows_removed": int(sum(table_counts.values())),
    }
    store["tombstones"].append(record)
    atomic_write_json(target, store)
    return record


def purge_patient_from_outputs(
    user_id: int,
    *,
    output_dir: Path | None = None,
    deleted_by: str = "system",
    reason: str = "patient erasure request",
    write_tombstone: bool = True,
) -> dict[str, Any]:
    """Remove one patient from every materialized output surface."""
    target_dir = output_dir or Path(config.OUTPUT_DIR)
    counts: dict[str, int] = {}
    for filename in _CSV_OUTPUTS_WITH_PATIENT_ID:
        counts[filename] = _purge_csv(target_dir / filename, int(user_id))
    counts["clinical_annotations.json"] = _purge_annotations(target_dir, int(user_id))

    tombstone = None
    if write_tombstone:
        tombstone = append_tombstone(
            user_id=int(user_id),
            deleted_by=deleted_by,
            reason=reason,
            table_counts=counts,
            path=target_dir / TOMBSTONE_FILE.name,
        )
    return {
        "user_id": int(user_id),
        "patient_hash": patient_hash(user_id),
        "tables": counts,
        "total_rows_removed": int(sum(counts.values())),
        "tombstone": tombstone,
    }


def apply_active_retractions_to_outputs(
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Re-apply tombstones after a fresh pipeline materialization."""
    target_dir = output_dir or Path(config.OUTPUT_DIR)
    hashes = active_patient_hashes(target_dir / TOMBSTONE_FILE.name)
    counts: dict[str, int] = {}
    if not hashes:
        return {"active_tombstones": 0, "tables": counts, "total_rows_removed": 0}

    for filename in _CSV_OUTPUTS_WITH_PATIENT_ID:
        path = target_dir / filename
        if not path.exists():
            counts[filename] = 0
            continue
        df = pd.read_csv(path, low_memory=False)
        before = len(df)
        filtered = filter_retracted_dataframe(
            df,
            tombstone_path=target_dir / TOMBSTONE_FILE.name,
        )
        removed = before - len(filtered)
        counts[filename] = int(removed)
        if removed:
            _atomic_write_csv(filtered, path)

    return {
        "active_tombstones": len(hashes),
        "tables": counts,
        "total_rows_removed": int(sum(counts.values())),
    }
