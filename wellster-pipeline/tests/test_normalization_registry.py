"""Tests for the normalization registry — record-list governance layer.

Covers the behaviours that justify the v2 record-list shape over the
legacy v1 map:

- Case-collision records survive separately (the v1 map silently lost one)
- v1 → v2 migration is non-destructive and idempotent
- The legacy-map view filters out non-validated states
- Per-record review state can be updated atomically

Tests run via the in-tree pytest-free runner pattern:
    cd wellster-pipeline
    python tests/test_normalization_registry.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.normalization_registry import (  # noqa: E402
    NormalizationRecord,
    NormalizationRegistry,
)


def _tmp(name: str) -> Path:
    return Path(tempfile.gettempdir()) / f"uniq-test-{name}-{id(name)}.json"


# ---------------------------------------------------------------------------
# Case-collision behaviour — the central reason this module exists
# ---------------------------------------------------------------------------


def test_case_variants_are_separate_records():
    reg = NormalizationRegistry()
    a = reg.upsert(
        category="CURRENT_MEDICATIONS",
        original_value="L-Thyroxin",
        canonical_label="LEVOTHYROXINE",
    )
    b = reg.upsert(
        category="CURRENT_MEDICATIONS",
        original_value="L-thyroxin",
        canonical_label="LEVOTHYROXINE",
    )
    assert a.id != b.id, "case variants must be distinct records"
    assert reg.lookup("CURRENT_MEDICATIONS", "L-Thyroxin").id == a.id
    assert reg.lookup("CURRENT_MEDICATIONS", "L-thyroxin").id == b.id


def test_case_insensitive_fallback_finds_either():
    reg = NormalizationRegistry()
    reg.upsert(
        category="CURRENT_MEDICATIONS",
        original_value="L-Thyroxin",
        canonical_label="LEVOTHYROXINE",
    )
    found = reg.lookup("CURRENT_MEDICATIONS", "L-THYROXIN", case_sensitive=False)
    assert found is not None
    assert found.canonical_label == "LEVOTHYROXINE"


def test_case_collisions_are_surfaced_for_review():
    reg = NormalizationRegistry()
    reg.upsert(category="CAT", original_value="Foo", canonical_label="FOO")
    reg.upsert(category="CAT", original_value="foo", canonical_label="FOO")
    reg.upsert(category="CAT", original_value="bar", canonical_label="BAR")
    collisions = reg.case_collisions()
    assert len(collisions) == 1, "exactly one case-colliding bucket"
    assert {r.original_value for r in collisions[0]} == {"Foo", "foo"}


# ---------------------------------------------------------------------------
# v1 -> v2 migration
# ---------------------------------------------------------------------------


def test_v1_legacy_map_loads_as_records():
    legacy = {
        "CURRENT_MEDICATIONS": {
            "L-Thyroxin": "LEVOTHYROXINE",
            "L-thyroxin": "LEVOTHYROXINE",
            "Symbicort": "BUDESONIDE_FORMOTEROL",
        },
        "BLOOD_PRESSURE_ASSESSMENT": {
            "Normal - 90/60 to 140/90": "NORMAL_BP",
        },
    }
    reg = NormalizationRegistry._from_v1_legacy(legacy)
    assert len(reg.records) == 4, "every legacy entry becomes a record"
    assert all(r.review_status == "approved" for r in reg.records), (
        "legacy entries import as approved (they were already in production)"
    )


def test_round_trip_v2_format():
    path = _tmp("roundtrip")
    reg = NormalizationRegistry()
    reg.upsert(
        category="CAT",
        original_value="orig",
        canonical_label="LABEL",
        review_status="overridden",
        reviewed_by="Dr. Test",
        review_note="merged duplicates",
    )
    reg.save(path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 2
    assert isinstance(raw["records"], list)
    assert len(raw["records"]) == 1

    loaded = NormalizationRegistry.from_disk(path)
    assert len(loaded.records) == 1
    rec = loaded.records[0]
    assert rec.canonical_label == "LABEL"
    assert rec.review_status == "overridden"
    assert rec.reviewed_by == "Dr. Test"
    path.unlink()


# ---------------------------------------------------------------------------
# Validated layer behaviour
# ---------------------------------------------------------------------------


def test_legacy_map_excludes_non_validated_records():
    reg = NormalizationRegistry()
    reg.upsert(category="CAT", original_value="ok1", canonical_label="OK", review_status="approved")
    reg.upsert(category="CAT", original_value="ok2", canonical_label="OK", review_status="overridden")
    reg.upsert(category="CAT", original_value="wait", canonical_label="WAIT", review_status="pending")
    reg.upsert(category="CAT", original_value="bad", canonical_label="BAD", review_status="rejected")

    legacy = reg.as_legacy_map()
    assert "CAT" in legacy
    cat = legacy["CAT"]
    assert "ok1" in cat and "ok2" in cat, "approved + overridden are exposed"
    assert "wait" not in cat, "pending records do NOT pass the gate"
    assert "bad" not in cat, "rejected records do NOT pass the gate"


def test_upsert_increments_source_count_for_known_records():
    reg = NormalizationRegistry()
    rec = reg.upsert(category="CAT", original_value="X", canonical_label="X_LABEL")
    assert rec.source_count == 1
    rec = reg.upsert(category="CAT", original_value="X", canonical_label="X_LABEL")
    assert rec.source_count == 2, "second occurrence bumps source_count"
    rec = reg.upsert(category="CAT", original_value="X", canonical_label="X_LABEL")
    assert rec.source_count == 3


def test_update_review_attaches_reviewer_identity():
    reg = NormalizationRegistry()
    rec = reg.upsert(category="CAT", original_value="x", canonical_label="X")
    updated = reg.update_review(
        rec.id,
        canonical_label="X_REVISED",
        review_status="overridden",
        reviewed_by="Dr. M. Hassan",
        review_note="merged with X_OLD",
    )
    assert updated is not None
    assert updated.canonical_label == "X_REVISED"
    assert updated.review_status == "overridden"
    assert updated.reviewed_by == "Dr. M. Hassan"
    assert updated.reviewed_at is not None, "reviewed_at auto-stamped"
    assert updated.review_note == "merged with X_OLD"


def test_coverage_stats_reflect_review_state():
    reg = NormalizationRegistry()
    reg.upsert(category="CAT", original_value="a", canonical_label="A", review_status="approved")
    reg.upsert(category="CAT", original_value="b", canonical_label="B", review_status="approved")
    reg.upsert(category="CAT", original_value="c", canonical_label="C", review_status="pending")
    reg.upsert(category="CAT", original_value="d", canonical_label="D", review_status="rejected")
    stats = reg.coverage_stats()
    assert stats["total_records"] == 4
    assert stats["by_status_approved"] == 2
    assert stats["by_status_pending"] == 1
    assert stats["by_status_rejected"] == 1


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_case_variants_are_separate_records,
        test_case_insensitive_fallback_finds_either,
        test_case_collisions_are_surfaced_for_review,
        test_v1_legacy_map_loads_as_records,
        test_round_trip_v2_format,
        test_legacy_map_excludes_non_validated_records,
        test_upsert_increments_source_count_for_known_records,
        test_update_review_attaches_reviewer_identity,
        test_coverage_stats_reflect_review_state,
    ]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")

    print()
    print(f"normalization_registry tests: {passed} pass, {failed} fail")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    raise SystemExit(main())
