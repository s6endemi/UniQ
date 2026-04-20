"""Phase 3A smoke tests for `semantic_mapping_ai`.

Verifies:
    - semantic_mapping.json has the expected shape per category.
    - confidence values are within the allowed enum.
    - review_status defaults to "pending" on freshly generated entries.
    - approved/overridden entries are preserved across re-runs (no AI overwrite).
    - taxonomy fingerprint triggers skip when unchanged.
    - archived entries (categories no longer in taxonomy) land in __archived__.

Prerequisites:
    - A previous pipeline run (output/taxonomy.json + output/semantic_mapping.json).
    - Skips gracefully otherwise.

No API call is made here — we exercise the cache/merge path only, plus validate
whatever AI output already sits on disk from the most recent run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.semantic_mapping_ai import (
    ALLOWED_FHIR_RESOURCE_TYPES,
    SEMANTIC_MAPPING_FILE,
    _merge_with_cache,
    _rejected_placeholder,
    _taxonomy_fingerprint,
    _validate_entry,
    generate_semantic_mapping,
)


_results: list[tuple[str, str, str]] = []


def _ok(name: str, detail: str = "") -> None:
    _results.append(("OK", name, detail))


def _fail(name: str, detail: str) -> None:
    _results.append(("FAIL", name, detail))


def _report_and_exit() -> int:
    icons = {"OK": "[OK]", "FAIL": "[X]"}
    for status, name, detail in _results:
        print(f"  {icons[status]} {name}" + (f"  -- {detail}" if detail else ""))
    passes = sum(1 for s, *_ in _results if s == "OK")
    fails = sum(1 for s, *_ in _results if s == "FAIL")
    print(f"\n{passes} pass, {fails} fail")
    return 1 if fails else 0


def main() -> int:
    taxonomy_path = config.OUTPUT_DIR / "taxonomy.json"
    if not SEMANTIC_MAPPING_FILE.exists():
        print(f"SKIP: {SEMANTIC_MAPPING_FILE.name} missing — run pipeline first")
        return 0
    if not taxonomy_path.exists():
        print("SKIP: taxonomy.json missing — run pipeline first")
        return 0

    mapping = json.loads(SEMANTIC_MAPPING_FILE.read_text(encoding="utf-8"))
    taxonomy_doc = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    taxonomy_categories = taxonomy_doc.get("categories", [])
    taxonomy_names = {e.get("category", "") for e in taxonomy_categories}

    _ok(
        "semantic_mapping.json loads",
        f"{sum(1 for k in mapping if not k.startswith('__'))} mapped categories",
    )

    # 1. Fingerprint present and matches current taxonomy
    fingerprint = mapping.get("__taxonomy_fingerprint__")
    if fingerprint == _taxonomy_fingerprint(taxonomy_categories):
        _ok("taxonomy fingerprint matches")
    else:
        _fail(
            "taxonomy fingerprint matches",
            f"cached={fingerprint[:16] if fingerprint else 'None'} "
            f"vs current={_taxonomy_fingerprint(taxonomy_categories)[:16]}",
        )

    # 2. Coverage: every current category has an entry
    mapped_cats = {k for k in mapping if not k.startswith("__")}
    missing = taxonomy_names - mapped_cats
    if not missing:
        _ok("every taxonomy category is mapped")
    else:
        _fail("every taxonomy category is mapped", f"{len(missing)} missing: {list(missing)[:3]}")

    # 3. Per-entry validation: required fields, confidence enum
    validation_errors: list[str] = []
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    review_counts = {"pending": 0, "approved": 0, "overridden": 0, "rejected": 0}
    for cat, entry in mapping.items():
        if cat.startswith("__"):
            continue
        errors = _validate_entry(cat, entry)
        validation_errors.extend(errors)
        conf = entry.get("confidence")
        if conf in confidence_counts:
            confidence_counts[conf] += 1
        status = entry.get("review_status", "pending")
        review_counts[status] = review_counts.get(status, 0) + 1
    if not validation_errors:
        _ok(
            "every entry passes validation",
            f"high={confidence_counts['high']} "
            f"medium={confidence_counts['medium']} "
            f"low={confidence_counts['low']}",
        )
    else:
        _fail("every entry passes validation",
              f"{len(validation_errors)} errors, first: {validation_errors[0]}")

    # 4. Review status distribution
    _ok(
        "review_status distribution",
        f"pending={review_counts.get('pending', 0)} "
        f"approved={review_counts.get('approved', 0)} "
        f"overridden={review_counts.get('overridden', 0)} "
        f"rejected={review_counts.get('rejected', 0)}",
    )

    # 5. Merge preserves approved entries (unit-test on synthetic data)
    cached = {
        "CAT_APPROVED": {
            "display_label": "Old Label",
            "fhir_resource_type": "Observation",
            "confidence": "high",
            "review_status": "approved",
        },
        "CAT_PENDING": {
            "display_label": "Old Pending",
            "fhir_resource_type": "Observation",
            "confidence": "low",
            "review_status": "pending",
        },
        "CAT_ARCHIVED": {
            "display_label": "Gone",
            "fhir_resource_type": "Observation",
            "confidence": "high",
            "review_status": "approved",
        },
    }
    fresh = {
        "CAT_APPROVED": {
            "display_label": "New AI Label",
            "fhir_resource_type": "Condition",
            "confidence": "medium",
        },
        "CAT_PENDING": {
            "display_label": "New AI Pending",
            "fhir_resource_type": "Observation",
            "confidence": "high",
        },
        "CAT_NEW": {
            "display_label": "New Entry",
            "fhir_resource_type": "Observation",
            "confidence": "high",
        },
    }
    merged = _merge_with_cache(fresh, cached)

    if merged.get("CAT_APPROVED", {}).get("display_label") == "Old Label":
        _ok("approved entries are preserved verbatim")
    else:
        _fail("approved entries are preserved verbatim",
              f"got {merged.get('CAT_APPROVED')}")

    if (
        merged.get("CAT_PENDING", {}).get("display_label") == "New AI Pending"
        and merged.get("CAT_PENDING", {}).get("review_status") == "pending"
    ):
        _ok("pending entries are overwritten + stay pending")
    else:
        _fail("pending entries are overwritten + stay pending",
              f"got {merged.get('CAT_PENDING')}")

    archived = merged.get("__archived__", {})
    if "CAT_ARCHIVED" in archived:
        _ok("orphan cached entries land in __archived__")
    else:
        _fail("orphan cached entries land in __archived__",
              f"got archive keys: {list(archived.keys())}")

    # 6. Incremental skip: calling generate_semantic_mapping with unchanged
    # taxonomy must not alter the file.
    before_hash = SEMANTIC_MAPPING_FILE.stat().st_mtime
    result = generate_semantic_mapping(taxonomy_categories)
    after_hash = SEMANTIC_MAPPING_FILE.stat().st_mtime
    if before_hash == after_hash and result:
        _ok("incremental skip when taxonomy unchanged", "no API call, no write")
    else:
        _fail("incremental skip when taxonomy unchanged",
              "file was rewritten despite unchanged taxonomy")

    # 7. Codex finding 1: contract enforcement on fhir_resource_type
    bad_fhir = _validate_entry("X", {
        "display_label": "X",
        "fhir_resource_type": "TotallyMadeUpResource",
        "confidence": "high",
    })
    if any("not in allow-list" in e for e in bad_fhir):
        _ok("validator rejects unknown fhir_resource_type")
    else:
        _fail("validator rejects unknown fhir_resource_type",
              f"errors were: {bad_fhir}")

    good_fhir = _validate_entry("X", {
        "display_label": "X",
        "fhir_resource_type": "AllergyIntolerance",
        "confidence": "high",
    })
    if not good_fhir:
        _ok("AllergyIntolerance is in allow-list", "previously slipped silently")
    else:
        _fail("AllergyIntolerance is in allow-list", str(good_fhir))

    # 8. Codex finding 2: fingerprint reacts to definition changes
    tax_a = [{"category": "FOO", "definition": "first definition"}]
    tax_b = [{"category": "FOO", "definition": "refined definition"}]
    if _taxonomy_fingerprint(tax_a) != _taxonomy_fingerprint(tax_b):
        _ok("fingerprint changes when definitions change")
    else:
        _fail("fingerprint changes when definitions change",
              "fingerprint identical despite different definitions")

    # 9. Codex finding 3: rejected placeholders cover every category
    placeholder = _rejected_placeholder("BROKEN_CAT", ["fake error"])
    placeholder_errors = _validate_entry("BROKEN_CAT", placeholder)
    if not placeholder_errors and placeholder["review_status"] == "rejected":
        _ok("rejected placeholder is itself contract-valid",
            "downstream sees status=rejected and skips it")
    else:
        _fail("rejected placeholder is itself contract-valid",
              f"errors={placeholder_errors}, status={placeholder.get('review_status')}")

    # 10. Active mapping covers every taxonomy category (no silent drops)
    active_count = sum(
        1 for k in mapping
        if not k.startswith("__") and isinstance(mapping[k], dict)
    )
    if active_count == len(taxonomy_names):
        _ok(
            "active mapping covers every taxonomy category",
            f"{active_count}/{len(taxonomy_names)}",
        )
    else:
        _fail(
            "active mapping covers every taxonomy category",
            f"{active_count}/{len(taxonomy_names)} — silent drop suspected",
        )

    # ------------------------------------------------------------------
    # Semantic plausibility — for well-known clinical concepts, assert
    # the AI produced structurally sensible mappings. We check type +
    # coding-system, not exact codes, so natural AI variance is tolerated
    # but gross errors (e.g. BMI mapped to Condition instead of
    # Observation) are caught.
    # ------------------------------------------------------------------

    def _find_by_concept(target: str) -> dict | None:
        """Return the first entry whose category name or standard_concept looks like `target`."""
        target_up = target.upper()
        for cat, entry in mapping.items():
            if cat.startswith("__") or not isinstance(entry, dict):
                continue
            concept = (entry.get("standard_concept") or "").upper()
            if target_up in cat or target_up == concept:
                return entry
        return None

    # BMI should map to Observation with a LOINC code (if present).
    bmi_entry = _find_by_concept("BMI")
    if bmi_entry is None:
        _ok("BMI plausibility skipped", "no BMI-like category in taxonomy")
    elif bmi_entry["confidence"] != "high":
        _ok(
            "BMI plausibility lenient (low confidence entry not gated)",
            f"confidence={bmi_entry['confidence']}",
        )
    else:
        if bmi_entry["fhir_resource_type"] != "Observation":
            _fail(
                "BMI high-confidence entry maps to Observation",
                f"got {bmi_entry['fhir_resource_type']}",
            )
        else:
            loinc_codes = [
                c for c in bmi_entry.get("codes", [])
                if "loinc" in c.get("system", "").lower()
            ]
            if loinc_codes:
                _ok(
                    "BMI high-confidence entry has LOINC code",
                    f"codes={[c['code'] for c in loinc_codes]}",
                )
            else:
                _fail(
                    "BMI high-confidence entry has LOINC code",
                    f"systems={[c.get('system') for c in bmi_entry.get('codes', [])]}",
                )

    # Any CONDITIONS-like category should map to Condition resource.
    cond_entry = _find_by_concept("MEDICAL_HISTORY")
    if cond_entry is None:
        cond_entry = _find_by_concept("CONDITIONS")
    if cond_entry is not None and cond_entry.get("confidence") == "high":
        if cond_entry["fhir_resource_type"] != "Condition":
            _fail(
                "Conditions high-confidence entry maps to Condition",
                f"got {cond_entry['fhir_resource_type']}",
            )
        else:
            _ok(
                "Conditions high-confidence entry maps to Condition resource",
                f"concept={cond_entry.get('standard_concept')}",
            )

    # Any SIDE_EFFECTS category should map to AdverseEvent or Observation.
    se_entry = _find_by_concept("SIDE_EFFECTS")
    if se_entry is not None and se_entry.get("confidence") == "high":
        valid_types = {"AdverseEvent", "Observation"}
        if se_entry["fhir_resource_type"] in valid_types:
            _ok(
                "Side-effects high-confidence entry is AdverseEvent or Observation",
                f"got {se_entry['fhir_resource_type']}",
            )
        else:
            _fail(
                "Side-effects high-confidence entry is AdverseEvent or Observation",
                f"got {se_entry['fhir_resource_type']}",
            )

    return _report_and_exit()


if __name__ == "__main__":
    sys.exit(main())
