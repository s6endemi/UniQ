"""Answer-normalization registry — record-list governance layer.

Replaces the legacy `{category: {original_text: canonical_label}}` map
with a record-list structure that supports per-record review state,
provenance, and the unknown-variant queue (separate file, see
`normalization_queue.py` once added).

Why a record list (not a nested map):
- Object-keyed JSON loses information when keys collide case-insensitively
  ("L-Thyroxin" vs "L-thyroxin" become one entry on some loaders, two on
  others — undefined behaviour for clinical data)
- Per-record metadata (review_status, source_count, timestamps,
  reviewer_id) doesn't fit naturally inside an inner map
- Queryable by every dimension (category, status, frequency) without
  flattening

Format on disk (`output/answer_normalization.json`):

    {
        "version": 2,
        "records": [
            {
                "id": "norm-{8-hex}",
                "category": "CURRENT_MEDICATIONS",
                "original_value": "L-thyroxin",
                "canonical_label": "LEVOTHYROXINE",
                "review_status": "approved",
                "source_count": 12,
                "first_seen": "2025-01-15T...",
                "last_seen": "2026-04-15T...",
                "reviewed_by": null,
                "reviewed_role": null,
                "reviewed_at": null,
                "review_note": null
            },
            ...
        ]
    }

The loader auto-detects v1 (legacy map) vs v2 (record list) so the
migration is transparent — first read after upgrade migrates in-place
and saves v2; subsequent reads use v2 directly.

Backward-compat is non-negotiable: the legacy `{category: {orig: label}}`
shape is still served via `as_legacy_map()` for any caller (today only
the unification stage of the pipeline) that hasn't been refactored yet.
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


REGISTRY_FILE = Path(config.OUTPUT_DIR) / "answer_normalization.json"
REGISTRY_VERSION = 2

ReviewStatus = Literal["pending", "approved", "overridden", "rejected"]


def _new_id() -> str:
    return f"norm-{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NormalizationRecord:
    """One reviewable normalization mapping for a single original→canonical pair."""

    id: str
    category: str
    original_value: str
    canonical_label: str
    review_status: ReviewStatus = "approved"
    source_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    reviewed_by: str | None = None
    reviewed_role: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizationRecord:
        # Tolerant of extra keys; future-version compatible
        return cls(
            id=str(data["id"]),
            category=str(data["category"]),
            original_value=str(data["original_value"]),
            canonical_label=str(data["canonical_label"]),
            review_status=str(data.get("review_status", "approved")),  # type: ignore[arg-type]
            source_count=int(data.get("source_count", 0)),
            first_seen=data.get("first_seen"),
            last_seen=data.get("last_seen"),
            reviewed_by=data.get("reviewed_by"),
            reviewed_role=data.get("reviewed_role"),
            reviewed_at=data.get("reviewed_at"),
            review_note=data.get("review_note"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "original_value": self.original_value,
            "canonical_label": self.canonical_label,
            "review_status": self.review_status,
            "source_count": self.source_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "reviewed_by": self.reviewed_by,
            "reviewed_role": self.reviewed_role,
            "reviewed_at": self.reviewed_at,
            "review_note": self.review_note,
        }


@dataclass
class NormalizationRegistry:
    """In-memory record-list with case-sensitive + insensitive lookup paths."""

    records: list[NormalizationRecord] = field(default_factory=list)

    # ---- Loading / saving -------------------------------------------------

    @classmethod
    def from_disk(cls, path: Path | None = None) -> NormalizationRegistry:
        target = path or REGISTRY_FILE
        if not target.exists():
            return cls()
        try:
            data = atomic_read_json(target)
        except AtomicReadError:
            return cls()
        if not isinstance(data, dict):
            return cls()

        if data.get("version") == REGISTRY_VERSION:
            return cls._from_v2(data)
        # v1 fallback: legacy {category: {original: canonical}} map.
        # Auto-migrate in memory; on the next save, v2 is written back.
        return cls._from_v1_legacy(data)

    @classmethod
    def _from_v2(cls, data: dict[str, Any]) -> NormalizationRegistry:
        raw_records = data.get("records") or []
        records = [
            NormalizationRecord.from_dict(r)
            for r in raw_records
            if isinstance(r, dict) and "original_value" in r and "canonical_label" in r
        ]
        return cls(records=records)

    @classmethod
    def _from_v1_legacy(cls, legacy_map: dict[str, Any]) -> NormalizationRegistry:
        """Migrate the {category: {original: canonical}} format to record list.

        Existing legacy entries are imported as `approved` because they
        were already in production use — treating them as `pending`
        would invalidate the working substrate. Reviewers can later
        override individual records.
        """
        now = _now_iso()
        records: list[NormalizationRecord] = []
        for category, mapping in legacy_map.items():
            if not isinstance(mapping, dict) or category.startswith("__"):
                continue
            for original, canonical in mapping.items():
                records.append(
                    NormalizationRecord(
                        id=_new_id(),
                        category=str(category),
                        original_value=str(original),
                        canonical_label=str(canonical),
                        review_status="approved",
                        source_count=0,  # legacy data: unknown
                        first_seen=None,
                        last_seen=None,
                    )
                )
        return cls(records=records)

    def save(self, path: Path | None = None) -> None:
        target = path or REGISTRY_FILE
        atomic_write_json(
            target,
            {
                "version": REGISTRY_VERSION,
                "records": [r.to_dict() for r in self.records],
            },
        )

    # ---- Lookup -----------------------------------------------------------

    def lookup(
        self,
        category: str,
        original_value: str,
        *,
        case_sensitive: bool = True,
    ) -> NormalizationRecord | None:
        """Find the canonical record for one original value.

        Case-sensitive match wins; if absent and `case_sensitive=False`,
        falls back to case-insensitive match. The case-sensitive path is
        the production default — case-insensitive lookup exists for the
        review surface so a clinician can see "did I miss a near-duplicate?"
        """
        target_value = original_value
        for record in self.records:
            if record.category == category and record.original_value == target_value:
                return record
        if not case_sensitive:
            lowered = original_value.lower()
            for record in self.records:
                if (
                    record.category == category
                    and record.original_value.lower() == lowered
                ):
                    return record
        return None

    def for_category(self, category: str) -> list[NormalizationRecord]:
        return [r for r in self.records if r.category == category]

    def by_status(self, status: ReviewStatus) -> list[NormalizationRecord]:
        return [r for r in self.records if r.review_status == status]

    def case_collisions(self) -> list[list[NormalizationRecord]]:
        """Return groups of records that match case-insensitively but not exactly.

        These are the records most likely to be duplicates introduced by
        loading the legacy map in a case-insensitive parser. A clinical
        reviewer would want to either merge them (same canonical) or keep
        them distinct (different intended meaning).
        """
        buckets: dict[tuple[str, str], list[NormalizationRecord]] = {}
        for record in self.records:
            key = (record.category, record.original_value.lower())
            buckets.setdefault(key, []).append(record)
        return [bucket for bucket in buckets.values() if len(bucket) > 1]

    # ---- Mutation ---------------------------------------------------------

    def upsert(
        self,
        *,
        category: str,
        original_value: str,
        canonical_label: str,
        review_status: ReviewStatus = "approved",
        source_count_delta: int = 1,
        seen_at: str | None = None,
        reviewed_by: str | None = None,
        reviewed_role: str | None = None,
        reviewed_at: str | None = None,
        review_note: str | None = None,
    ) -> NormalizationRecord:
        """Insert or update one record. Returns the resulting record.

        Used by both pipeline ingest (where source_count_delta is 1 per
        new occurrence) and by review actions (where the reviewer
        identity gets attached). Idempotent for known entries: re-running
        with the same key just bumps source_count and last_seen.
        """
        existing = self.lookup(category, original_value, case_sensitive=True)
        when = seen_at or _now_iso()
        if existing is None:
            record = NormalizationRecord(
                id=_new_id(),
                category=category,
                original_value=original_value,
                canonical_label=canonical_label,
                review_status=review_status,
                source_count=max(0, source_count_delta),
                first_seen=when,
                last_seen=when,
                reviewed_by=reviewed_by,
                reviewed_role=reviewed_role,
                reviewed_at=reviewed_at,
                review_note=review_note,
            )
            self.records.append(record)
            return record

        if canonical_label and canonical_label != existing.canonical_label:
            existing.canonical_label = canonical_label
        if review_status and review_status != existing.review_status:
            existing.review_status = review_status
        existing.source_count = max(0, existing.source_count + source_count_delta)
        existing.last_seen = when
        if existing.first_seen is None:
            existing.first_seen = when
        if reviewed_by:
            existing.reviewed_by = reviewed_by
        if reviewed_role:
            existing.reviewed_role = reviewed_role
        if reviewed_at:
            existing.reviewed_at = reviewed_at
        if review_note is not None:
            existing.review_note = review_note
        return existing

    def update_review(
        self,
        record_id: str,
        *,
        canonical_label: str | None = None,
        review_status: ReviewStatus | None = None,
        reviewed_by: str | None = None,
        reviewed_role: str | None = None,
        reviewed_at: str | None = None,
        review_note: str | None = None,
    ) -> NormalizationRecord | None:
        """Apply a clinician review action to one record by id."""
        for record in self.records:
            if record.id != record_id:
                continue
            if canonical_label is not None:
                record.canonical_label = canonical_label
            if review_status is not None:
                record.review_status = review_status
            if reviewed_by is not None:
                record.reviewed_by = reviewed_by
            if reviewed_role is not None:
                record.reviewed_role = reviewed_role
            record.reviewed_at = reviewed_at or _now_iso()
            if review_note is not None:
                record.review_note = review_note
            return record
        return None

    # ---- Backward compatibility -------------------------------------------

    def as_legacy_map(self) -> dict[str, dict[str, str]]:
        """Render the registry in the legacy `{category: {orig: canonical}}` shape.

        Existing pipeline code (`normalize_answers_ai._apply_normalization`)
        consumes the legacy shape. This method preserves that contract
        while we migrate consumers to the record-list API. Only entries
        with `review_status in {approved, overridden}` are returned —
        `pending` and `rejected` are filtered out so the validated
        downstream layer never picks them up by accident.
        """
        out: dict[str, dict[str, str]] = {}
        for record in self.records:
            if record.review_status not in {"approved", "overridden"}:
                continue
            out.setdefault(record.category, {})[record.original_value] = record.canonical_label
        return out

    # ---- Telemetry --------------------------------------------------------

    def coverage_stats(self) -> dict[str, int]:
        """Counts per review status and per category, for the manifest."""
        by_status: dict[str, int] = {}
        for record in self.records:
            by_status[record.review_status] = by_status.get(record.review_status, 0) + 1
        return {
            "total_records": len(self.records),
            "by_status_approved": by_status.get("approved", 0),
            "by_status_overridden": by_status.get("overridden", 0),
            "by_status_pending": by_status.get("pending", 0),
            "by_status_rejected": by_status.get("rejected", 0),
        }


# ---- Module-level convenience -------------------------------------------


def load() -> NormalizationRegistry:
    """Single entry point for callers that just want the registry."""
    return NormalizationRegistry.from_disk()


def migrate_legacy_to_v2() -> tuple[bool, int]:
    """Run the v1→v2 migration once. Idempotent.

    Returns (migrated_now, total_records). `migrated_now=False` means
    the file was already v2 — nothing to do. Safe to call repeatedly.
    """
    if not REGISTRY_FILE.exists():
        return False, 0
    raw = atomic_read_json(REGISTRY_FILE)
    if isinstance(raw, dict) and raw.get("version") == REGISTRY_VERSION:
        # already migrated
        existing = NormalizationRegistry._from_v2(raw)
        return False, len(existing.records)
    registry = NormalizationRegistry._from_v1_legacy(raw if isinstance(raw, dict) else {})
    registry.save()
    return True, len(registry.records)


if __name__ == "__main__":
    # CLI: `python -m src.normalization_registry` runs the migration.
    # sys.stdout.reconfigure for Windows cp1252 hosts so unicode prints
    # don't crash the CLI flow.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    migrated, count = migrate_legacy_to_v2()
    if migrated:
        print(f"migrated v1 -> v2 | {count} records")
    else:
        print(f"already v2 | {count} records")
    registry = load()
    print()
    print("coverage stats:", registry.coverage_stats())
    collisions = registry.case_collisions()
    if collisions:
        print(f"case collisions: {len(collisions)} buckets")
        for bucket in collisions[:5]:
            print(f"  {bucket[0].category} / {bucket[0].original_value.lower()!r}:")
            for r in bucket:
                print(f"    {r.original_value!r:<40}  -> {r.canonical_label}")
    else:
        print("case collisions: none")
