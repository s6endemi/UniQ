"""AI-Generated Semantic Mapping — Phase 3A.

Takes the discovered `taxonomy.json` and proposes, per clinical category:
  - display_label     : a short human-readable name
  - standard_concept  : a canonical identifier (BMI, BLOOD_PRESSURE, ...) or null
  - fhir_resource_type: Observation | Condition | MedicationStatement | ...
  - fhir_category     : FHIR category code (vital-signs, encounter-diagnosis, ...)
  - codes             : suggested coding (LOINC / SNOMED / ICD-10 / RxNorm) or []
  - confidence        : high | medium | low
  - review_status     : pending (default) | approved | overridden | rejected
  - reasoning         : why the AI chose this mapping

Advisory-first: Downstream consumers (FHIR export, chatbot hints) only use
`high`-confidence entries automatically. `medium` and `low` entries require
human review before they influence the runtime path. This keeps the AI out
of unreviewed medical coding and preserves the human-in-the-loop story.

Incremental: if the cached mapping already covers every category in the
current taxonomy, no API call is made. Approved/overridden entries are
never regenerated — they are preserved verbatim across runs.

Output: `config.OUTPUT_DIR / "semantic_mapping.json"`
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.classify_ai import _call_api


SEMANTIC_MAPPING_FILE = config.OUTPUT_DIR / "semantic_mapping.json"


# Authoritative allow-list. Any value outside this set is rejected at validation
# time. The prompt and validator share this constant so the contract is
# unambiguous and enforced rather than just suggested.
ALLOWED_FHIR_RESOURCE_TYPES: frozenset[str] = frozenset({
    "Observation",
    "Condition",
    "MedicationStatement",
    "MedicationRequest",
    "AdverseEvent",
    "AllergyIntolerance",
    "Immunization",
    "Procedure",
    "FamilyMemberHistory",
    "Consent",
    "DocumentReference",
    "Media",
    "Patient",
    "QuestionnaireResponse",
})

ALLOWED_CONFIDENCE: frozenset[str] = frozenset({"high", "medium", "low"})
ALLOWED_REVIEW_STATUS: frozenset[str] = frozenset({
    "pending", "approved", "overridden", "rejected"
})


_ALLOWED_TYPES_LIST = ", ".join(sorted(ALLOWED_FHIR_RESOURCE_TYPES))

SEMANTIC_MAPPING_PROMPT = """You are a clinical informatics expert. You see a list of clinical
categories that an AI classifier discovered from a healthcare dataset. Your task: for each
category, propose a standardized mapping suitable for FHIR R4 export and for semantic
queries by a medical AI analyst.

For each category produce:
- display_label:      short human-readable name (e.g. "Body Mass Index")
- standard_concept:   a short canonical identifier if one clearly applies, else null.
                      Use UPPER_SNAKE_CASE. Examples: BMI, BLOOD_PRESSURE, SIDE_EFFECTS,
                      CONDITIONS, ADHERENCE, MEDICATIONS, DEMOGRAPHICS, CONSENT,
                      IDENTITY_DOCUMENT, PHOTO_EVIDENCE, LIFESTYLE, ALLERGY_INTOLERANCE.
- fhir_resource_type: MUST be exactly one of:
                      """ + _ALLOWED_TYPES_LIST + """.
                      Pick the most specific resource this category represents.
- fhir_category:      FHIR category code if applicable (vital-signs, laboratory,
                      encounter-diagnosis, medication, survey, social-history,
                      adverse-event, consent, etc.), else null.
- codes:              array of 0-3 suggested code entries, each with keys
                      "system", "code", "display". Prefer LOINC for observations/PROs,
                      SNOMED CT for conditions/findings, ICD-10 for diagnoses,
                      RxNorm for medications, ATC for drug classes. If no coding
                      system cleanly applies, return [].
- confidence:         "high" if you are confident this mapping would be accepted by
                      a clinical reviewer; "medium" if it is plausible but the
                      category may combine multiple concepts; "low" if the
                      category is administrative/composite/unclear.
- reasoning:          one sentence explaining the choice and any caveat.

Rules:
- Be conservative on codes. When unsure, return an empty `codes` list rather than
  a guess. Downstream systems only auto-use "high" confidence entries.
- Category names like PHOTO_UPLOAD, PATIENT_CONSENT, DEMOGRAPHIC_AND_IDENTITY
  typically map to non-clinical FHIR types (Media, Consent, Patient) and
  should have `standard_concept` set accordingly (e.g. PHOTO_EVIDENCE, CONSENT).
- If a category is clearly a composite (e.g. covering BMI + side-effects +
  adherence), mark `confidence: low` and explain in reasoning — downstream
  tooling will gate it until a human reviews.

Return valid JSON: a top-level object whose keys are the category names and
whose values are objects with the fields above. Example for one category:

  "BMI_MEASUREMENT": {
    "display_label": "Body Mass Index",
    "standard_concept": "BMI",
    "fhir_resource_type": "Observation",
    "fhir_category": "vital-signs",
    "codes": [{"system": "http://loinc.org", "code": "39156-5", "display": "..."}],
    "confidence": "high",
    "reasoning": "..."
  }

CATEGORIES TO MAP:
"""


def _format_categories_for_prompt(taxonomy: list[dict]) -> str:
    lines: list[str] = []
    for entry in sorted(taxonomy, key=lambda e: e.get("category", "")):
        cat = entry.get("category", "")
        definition = entry.get("definition", "") or ""
        lines.append(f"- {cat}: {definition[:200]}")
    return "\n".join(lines)


def _taxonomy_fingerprint(taxonomy: list[dict]) -> str:
    """Stable hash of the taxonomy's prompt-relevant content.

    Includes both category name AND definition because both are sent to the
    AI in the prompt. If a human refines a category's definition without
    renaming it, the fingerprint changes and we regenerate the mapping —
    otherwise we'd silently keep stale semantics that don't match the new
    definition.
    """
    pairs = sorted(
        (e.get("category", ""), (e.get("definition", "") or "").strip())
        for e in taxonomy
    )
    blob = "\n".join(f"{name}\t{definition}" for name, definition in pairs)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_existing_mapping() -> dict:
    if SEMANTIC_MAPPING_FILE.exists():
        try:
            return json.loads(SEMANTIC_MAPPING_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[SEM] Existing {SEMANTIC_MAPPING_FILE.name} is malformed — regenerating")
    return {}


def _merge_with_cache(
    ai_entries: dict[str, dict],
    cached_entries: dict[str, dict],
) -> dict[str, dict]:
    """Preserve approved/overridden entries; overwrite everything else with AI output."""
    merged: dict[str, dict] = {}
    for cat, ai_entry in ai_entries.items():
        cached = cached_entries.get(cat, {})
        review_status = cached.get("review_status", "pending")
        if review_status in ("approved", "overridden"):
            # Human has signed off — do NOT overwrite with a fresh AI proposal.
            merged[cat] = cached
        else:
            merged[cat] = {
                **ai_entry,
                "review_status": "pending",
            }
    # Keep any cached entries for categories no longer in the taxonomy under a
    # separate key so review history is not silently lost — but don't surface
    # them as active mappings.
    orphan_cached = {c: e for c, e in cached_entries.items() if c not in ai_entries}
    if orphan_cached:
        merged["__archived__"] = orphan_cached
    return merged


def _validate_entry(cat: str, entry: Any) -> list[str]:
    """Enforce the semantic_mapping contract.

    Returns a list of error messages. Empty list = entry is valid.
    Checks: required fields present, fhir_resource_type in allow-list,
    confidence in allow-list, review_status in allow-list, codes is a list
    of well-shaped dicts.
    """
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{cat}: entry is not a dict"]

    for field in ("display_label", "fhir_resource_type", "confidence"):
        if field not in entry:
            errors.append(f"{cat}: missing required field {field!r}")

    fhir_type = entry.get("fhir_resource_type")
    if fhir_type is not None and fhir_type not in ALLOWED_FHIR_RESOURCE_TYPES:
        errors.append(
            f"{cat}: fhir_resource_type {fhir_type!r} not in allow-list "
            f"({len(ALLOWED_FHIR_RESOURCE_TYPES)} values)"
        )

    confidence = entry.get("confidence")
    if confidence is not None and confidence not in ALLOWED_CONFIDENCE:
        errors.append(f"{cat}: invalid confidence {confidence!r}")

    review_status = entry.get("review_status", "pending")
    if review_status not in ALLOWED_REVIEW_STATUS:
        errors.append(f"{cat}: invalid review_status {review_status!r}")

    codes = entry.get("codes", [])
    if not isinstance(codes, list):
        errors.append(f"{cat}: codes must be a list")
    else:
        for i, code in enumerate(codes):
            if not isinstance(code, dict):
                errors.append(f"{cat}: codes[{i}] is not a dict")
                continue
            for field in ("system", "code"):
                if field not in code:
                    errors.append(f"{cat}: codes[{i}] missing {field!r}")

    return errors


def _rejected_placeholder(cat: str, errors: list[str]) -> dict:
    """Build a safe placeholder entry for a category whose AI mapping failed.

    Downstream consumers must treat `review_status == "rejected"` as "do not
    auto-use this mapping". The placeholder keeps the category present so the
    mapping file always covers every taxonomy category — the failure is
    visible, not hidden as a silent drop.
    """
    return {
        "display_label": cat,
        "standard_concept": None,
        "fhir_resource_type": "QuestionnaireResponse",
        "fhir_category": None,
        "codes": [],
        "confidence": "low",
        "review_status": "rejected",
        "reasoning": "AI output failed validation; entry needs manual review",
        "validation_errors": errors,
    }


def generate_semantic_mapping(
    taxonomy: list[dict],
    *,
    force_regenerate: bool = False,
) -> dict[str, dict]:
    """Produce semantic_mapping.json for every category in the taxonomy.

    If a cached mapping covers every current category AND the taxonomy
    fingerprint matches, returns the cache unchanged (no API call).
    Otherwise calls the AI once, merges with preserved approved/overridden
    entries, and writes the result to disk.
    """
    print("\n[SEM] === SEMANTIC MAPPING ===")

    if not taxonomy:
        print("[SEM] Empty taxonomy — nothing to map")
        return {}

    cached = _load_existing_mapping()
    fingerprint = _taxonomy_fingerprint(taxonomy)
    cached_fingerprint = cached.get("__taxonomy_fingerprint__")
    current_categories = {e.get("category", "") for e in taxonomy}
    cached_categories = {k for k in cached if not k.startswith("__")}

    if (
        not force_regenerate
        and cached_fingerprint == fingerprint
        and current_categories <= cached_categories
    ):
        print(f"[SEM] Cached mapping covers all {len(current_categories)} categories "
              f"(fingerprint match) — skipping AI call")
        return cached

    print(f"[SEM] {len(current_categories)} categories to map. "
          f"{len(cached_categories & current_categories)} already cached, "
          f"{len(current_categories - cached_categories)} new.")

    prompt = SEMANTIC_MAPPING_PROMPT + _format_categories_for_prompt(taxonomy)
    result = _call_api(prompt, batch_label=f"{len(current_categories)} categories")

    if result is None:
        print("[SEM] API call failed — returning cached mapping unchanged")
        return cached

    # Flatten: the prompt asked for a flat dict keyed by category name.
    if not isinstance(result, dict):
        print(f"[SEM] Unexpected response shape {type(result).__name__} — aborting")
        return cached

    ai_entries: dict[str, dict] = {}
    rejected: dict[str, list[str]] = {}
    for cat, entry in result.items():
        if cat.startswith("__") or cat not in current_categories:
            continue
        entry_errors = _validate_entry(cat, entry)
        if entry_errors:
            rejected[cat] = entry_errors
        else:
            ai_entries[cat] = entry

    # Categories the AI didn't address at all → also rejected (can't auto-use)
    for cat in current_categories - set(ai_entries) - set(rejected):
        rejected[cat] = [f"{cat}: AI did not return an entry for this category"]

    # Replace silent drops with explicit rejected placeholders so the mapping
    # always covers every category. Downstream consumers see review_status
    # == "rejected" and skip the entry instead of finding it absent.
    for cat, entry_errors in rejected.items():
        ai_entries[cat] = _rejected_placeholder(cat, entry_errors)

    if rejected:
        print(f"[SEM] {len(rejected)} categories failed validation → rejected placeholders:")
        for cat, errs in list(rejected.items())[:10]:
            print(f"  - {cat}: {errs[0]}")

    merged = _merge_with_cache(ai_entries, {k: v for k, v in cached.items() if not k.startswith("__")})
    merged["__taxonomy_fingerprint__"] = fingerprint

    SEMANTIC_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEMANTIC_MAPPING_FILE.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[SEM] Saved mapping to {SEMANTIC_MAPPING_FILE}")

    # Summary
    counts = {"high": 0, "medium": 0, "low": 0, "other": 0}
    for cat, entry in merged.items():
        if cat.startswith("__"):
            continue
        counts[entry.get("confidence", "other")] = counts.get(
            entry.get("confidence", "other"), 0
        ) + 1
    print(f"[SEM] Confidence distribution: "
          f"high={counts.get('high', 0)}, "
          f"medium={counts.get('medium', 0)}, "
          f"low={counts.get('low', 0)}")

    return merged


def run_semantic_mapping() -> dict[str, dict]:
    """CLI-entry variant: loads taxonomy from disk and runs the mapper."""
    taxonomy_path = config.OUTPUT_DIR / "taxonomy.json"
    if not taxonomy_path.exists():
        print(f"[SEM] ERROR: {taxonomy_path} missing — run classification first")
        return {}
    taxonomy_doc = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    categories = taxonomy_doc.get("categories", [])
    return generate_semantic_mapping(categories)


if __name__ == "__main__":
    run_semantic_mapping()
