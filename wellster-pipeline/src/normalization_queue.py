"""Unknown-variant queue — answer values seen in data but not in the registry.

When the unification stage encounters an answer value that has no
matching record in the normalization registry (case-sensitive lookup),
the value is recorded here for later clinician review. The pipeline
continues with `answer_canonical = null` for that value, the
`normalization_status` on the survey row gets tagged accordingly, and
the queue grows.

A clinician later sweeps the queue, decides the canonical label, and
either:
- Promotes the queue entry into a registry record (then the next
  pipeline run picks it up via the registry), or
- Marks it as intentionally not-mappable (e.g. typos, garbled inputs)

The queue is intentionally a separate file from the registry to keep
the validated layer clean — a clinical reviewer should be able to
trust that everything in `answer_normalization.json` is signed.

Format on disk (`output/normalization_queue.json`):

    {
        "version": 1,
        "entries": [
            {
                "id": "unk-{8-hex}",
                "category": "CURRENT_MEDICATIONS",
                "original_value": "L-thyrokse 75",
                "first_seen": "2026-04-29T...",
                "last_seen": "2026-04-29T...",
                "occurrence_count": 3,
                "status": "open",
                "resolution": null,
                "resolved_by": null,
                "resolved_role": null,
                "resolved_at": null
            },
            ...
        ]
    }

Status transitions:
- `open`: awaiting clinician review (default)
- `promoted`: the clinician has promoted this into the registry; subsequent
  pipeline runs pick it up via the registry, no new queue entry needed
- `dismissed`: the clinician has decided this value should remain unmapped
  (typo / noise / non-clinical). Pipeline still tags rows as null but does
  not re-add to the queue.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # type: ignore[import-not-found]

from src.io_utils import AtomicReadError, atomic_read_json, atomic_write_json


QUEUE_FILE = Path(config.OUTPUT_DIR) / "normalization_queue.json"
QUEUE_VERSION = 1

QueueStatus = Literal["open", "promoted", "dismissed"]


def _new_id() -> str:
    return f"unk-{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UnknownEntry:
    id: str
    category: str
    original_value: str
    first_seen: str
    last_seen: str
    occurrence_count: int = 1
    status: QueueStatus = "open"
    resolution: str | None = None  # canonical label if promoted
    resolved_by: str | None = None
    resolved_role: str | None = None
    resolved_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnknownEntry:
        return cls(
            id=str(data["id"]),
            category=str(data["category"]),
            original_value=str(data["original_value"]),
            first_seen=str(data["first_seen"]),
            last_seen=str(data["last_seen"]),
            occurrence_count=int(data.get("occurrence_count", 1)),
            status=str(data.get("status", "open")),  # type: ignore[arg-type]
            resolution=data.get("resolution"),
            resolved_by=data.get("resolved_by"),
            resolved_role=data.get("resolved_role"),
            resolved_at=data.get("resolved_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "original_value": self.original_value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "occurrence_count": self.occurrence_count,
            "status": self.status,
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
            "resolved_role": self.resolved_role,
            "resolved_at": self.resolved_at,
        }


@dataclass
class NormalizationQueue:
    entries: list[UnknownEntry] = field(default_factory=list)

    # ---- Loading / saving -------------------------------------------------

    @classmethod
    def from_disk(cls, path: Path | None = None) -> NormalizationQueue:
        target = path or QUEUE_FILE
        if not target.exists():
            return cls()
        try:
            data = atomic_read_json(target)
        except AtomicReadError:
            return cls()
        if not isinstance(data, dict):
            return cls()
        raw_entries = data.get("entries") or []
        entries = [
            UnknownEntry.from_dict(e)
            for e in raw_entries
            if isinstance(e, dict)
            and "category" in e
            and "original_value" in e
        ]
        return cls(entries=entries)

    def save(self, path: Path | None = None) -> None:
        target = path or QUEUE_FILE
        atomic_write_json(
            target,
            {
                "version": QUEUE_VERSION,
                "entries": [e.to_dict() for e in self.entries],
            },
        )

    # ---- Mutation ---------------------------------------------------------

    def record_unknown(
        self,
        *,
        category: str,
        original_value: str,
        seen_at: str | None = None,
    ) -> UnknownEntry:
        """Append a new unknown variant or bump an existing one's count.

        If an entry with the same (category, original_value) already
        exists in `dismissed` state, we do NOT bump it — the clinician
        explicitly decided this value is noise. Re-bumping would just
        re-add work.
        """
        when = seen_at or _now_iso()
        for entry in self.entries:
            if (
                entry.category == category
                and entry.original_value == original_value
            ):
                if entry.status == "dismissed":
                    return entry
                entry.occurrence_count += 1
                entry.last_seen = when
                return entry
        entry = UnknownEntry(
            id=_new_id(),
            category=category,
            original_value=original_value,
            first_seen=when,
            last_seen=when,
            occurrence_count=1,
            status="open",
        )
        self.entries.append(entry)
        return entry

    def resolve(
        self,
        entry_id: str,
        *,
        canonical_label: str | None = None,
        status: QueueStatus = "promoted",
        resolved_by: str | None = None,
        resolved_role: str | None = None,
    ) -> UnknownEntry | None:
        """Apply a review action — typically called from the API."""
        for entry in self.entries:
            if entry.id != entry_id:
                continue
            entry.status = status
            entry.resolution = canonical_label if status == "promoted" else None
            entry.resolved_by = resolved_by
            entry.resolved_role = resolved_role
            entry.resolved_at = _now_iso()
            return entry
        return None

    # ---- Read --------------------------------------------------------------

    def open_entries(self) -> list[UnknownEntry]:
        return [e for e in self.entries if e.status == "open"]

    def by_category(self, category: str) -> list[UnknownEntry]:
        return [e for e in self.entries if e.category == category]

    # ---- Telemetry --------------------------------------------------------

    def stats(self) -> dict[str, int]:
        by_status: dict[str, int] = {}
        for entry in self.entries:
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
        return {
            "total_entries": len(self.entries),
            "open": by_status.get("open", 0),
            "promoted": by_status.get("promoted", 0),
            "dismissed": by_status.get("dismissed", 0),
        }


# ---- Module-level convenience -------------------------------------------


def load() -> NormalizationQueue:
    return NormalizationQueue.from_disk()
