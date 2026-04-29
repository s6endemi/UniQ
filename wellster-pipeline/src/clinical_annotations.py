"""Clinical annotations store — first write-back resource on the substrate.

Data shape on disk (`output/clinical_annotations.json`):

    {
        "version": 1,
        "annotations": [
            {
                "id": "ann-...",
                "patient_id": 383871,
                "event_id": "med-3",
                "category": "clinical_note",
                "note": "...",
                "author": "Dr. M. Hassan",
                "role": "Clinical Reviewer",
                "created_at": "2026-04-25T12:34:56+00:00"
            },
            ...
        ]
    }

Why a flat JSON list and not a database: pitch-grade durability, atomic
write semantics, zero infra cost, easy to inspect by hand. If the substrate
grows past a few thousand annotations or sees concurrent multi-clinician
writes, we revisit. For now this matches the "next-to, not replacement-of"
positioning — the customer's operational DB stays the system of record.

Functions in this module are deliberately stateless. The router calls
`load_all_annotations()` on every request to pick up writes from concurrent
processes (e.g., a pre-seed script + the FastAPI worker).
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # type: ignore[import-not-found]

from src.io_utils import AtomicReadError, atomic_read_json, atomic_write_json


ANNOTATIONS_FILE = Path(config.OUTPUT_DIR) / "clinical_annotations.json"
STORE_VERSION = 1

# Default author / role for the demo. In production this would come from
# the authenticated session — for the showcase we attribute every write
# to a single demo clinician so the audit trail reads cleanly.
DEFAULT_AUTHOR = "Dr. M. Hassan"
DEFAULT_ROLE = "Clinical Reviewer"


def _new_id() -> str:
    return f"ann-{uuid.uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_store() -> dict[str, Any]:
    return {"version": STORE_VERSION, "annotations": []}


def load_all_annotations() -> list[dict[str, Any]]:
    """Read every annotation in the store, ordered as written.

    Missing file → empty list (not an error). The annotation surface
    is brand-new; consumers must tolerate zero entries gracefully.
    """
    if not ANNOTATIONS_FILE.exists():
        return []
    try:
        data = atomic_read_json(ANNOTATIONS_FILE)
    except AtomicReadError:
        return []
    if not isinstance(data, dict):
        return []
    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        return []
    return [a for a in annotations if isinstance(a, dict)]


def annotations_for_patient(patient_id: int) -> list[dict[str, Any]]:
    """All annotations attached to one patient, sorted oldest → newest."""
    pid = int(patient_id)
    matches = [a for a in load_all_annotations() if int(a.get("patient_id", -1)) == pid]
    matches.sort(key=lambda a: str(a.get("created_at", "")))
    return matches


def latest_annotation() -> dict[str, Any] | None:
    """Most recent annotation across all patients — used by audit strip."""
    all_ann = load_all_annotations()
    if not all_ann:
        return None
    return max(all_ann, key=lambda a: str(a.get("created_at", "")))


def annotation_count() -> int:
    return len(load_all_annotations())


def append_annotation(
    *,
    patient_id: int,
    note: str,
    event_id: str | None = None,
    category: str = "clinical_note",
    author: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    """Persist a new annotation atomically. Returns the inserted record.

    Author/role default to the demo clinician when not provided. The
    write goes through `atomic_write_json` — full file replace via
    tempfile + os.replace, with Windows PermissionError retry.
    """
    record = {
        "id": _new_id(),
        "patient_id": int(patient_id),
        "event_id": event_id,
        "category": category,
        "note": note.strip(),
        "author": author or DEFAULT_AUTHOR,
        "role": role or DEFAULT_ROLE,
        "created_at": _now_iso(),
    }
    existing = load_all_annotations()
    existing.append(record)
    atomic_write_json(
        ANNOTATIONS_FILE,
        {"version": STORE_VERSION, "annotations": existing},
    )
    return record


def seed_default_annotations(patient_id: int = 383871) -> int:
    """Idempotent pre-seed for the demo patient.

    Drops two clinically-plausible annotations on PT-383871 if the store
    has none for that patient. Safe to call repeatedly: re-runs are no-ops
    after the first successful seed. Returns the number of records
    inserted (0 or 2).
    """
    pid = int(patient_id)
    if any(int(a.get("patient_id", -1)) == pid for a in load_all_annotations()):
        return 0
    seeds = [
        {
            "patient_id": pid,
            "note": (
                "Dose escalation 2.5mg → 5mg reviewed at follow-up. "
                "Patient tolerated previous dose well, no GI side effects. "
                "Approved for next 12-week supply."
            ),
            "event_id": None,
            "category": "clinical_note",
        },
        {
            "patient_id": pid,
            "note": (
                "BMI plateau at week 18 noted. Discussed lifestyle factors, "
                "no titration needed yet — re-evaluate at next visit."
            ),
            "event_id": None,
            "category": "follow_up",
        },
    ]
    for seed in seeds:
        append_annotation(**seed)  # type: ignore[arg-type]
    return len(seeds)


if __name__ == "__main__":
    # CLI: `python -m src.clinical_annotations` seeds the demo annotations.
    inserted = seed_default_annotations()
    print(f"Inserted {inserted} pre-seed annotations.")
    print(f"Store now has {annotation_count()} total annotations.")
    latest = latest_annotation()
    if latest:
        print(f"Latest: {latest['author']} · {latest['created_at']}")
