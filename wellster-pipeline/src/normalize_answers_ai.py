"""
AI-Powered Answer Normalization

Same principle as question classification: one API call, full context, globally consistent.
The AI sees ALL unique answer values grouped by category and creates canonical mappings.

Example:
  BLOOD_PRESSURE_CHECK:
    "Normal - Between 90/60 - 140/90"  → NORMAL
    "Normal - Zwischen 90/60 - 140/90" → NORMAL  (German)
    "Normal 90/60 - 140/90"            → NORMAL  (v2)
    "High - Above 140/90"              → HIGH
    "Hoch - Über 140/90"               → HIGH    (German)
"""

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.classify_ai import _call_api
from src.normalization_queue import NormalizationQueue
from src.normalization_registry import NormalizationRegistry, migrate_legacy_to_v2

ANSWER_NORM_PROMPT = """You are a data normalization expert. Below are answer values from medical
questionnaires, grouped by clinical category. Many answers express the SAME meaning in different
words, languages (German/English), or survey versions.

YOUR TASK:
For each category, map every answer value to a short canonical label. Rules:
- Canonical labels should be UPPER_SNAKE_CASE, short, and descriptive
- Answers that mean the same thing (even across languages) get the SAME canonical label
- For yes/no answers: use YES / NO
- For "none of the above" / "keine der genannten": use NONE
- For medication names: normalize to the drug name (e.g., "0.5 mg Semaglutide" → "SEMAGLUTIDE_0.5MG")
- For free-text medical conditions: extract the primary condition
  (e.g., "Bluthochdruck, Ramipril 5 mg" → "HYPERTENSION")
- Keep it clinically meaningful — a doctor should understand the canonical label

Return valid JSON with this structure:
{
  "CATEGORY_NAME": {
    "original answer text": "CANONICAL_LABEL",
    "another answer text": "CANONICAL_LABEL",
    ...
  },
  ...
}

ANSWER VALUES BY CATEGORY:
"""


# Categories where answer normalization doesn't apply
SKIP_PARSE_METHODS = {"file_upload", "confirmation", "json_structured", "no_bmi_data"}

# Taxonomy names evolved after the first answer-normalization run. Preserve
# already reviewed labels when the observed answer text matches exactly
# under a known semantic rename; do not use fuzzy matching here.
CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "MEDICAL_HISTORY_AND_CONDITIONS": ("MEDICAL_HISTORY", "OBESITY_COMORBIDITIES"),
    "BLOOD_PRESSURE_AND_CARDIOVASCULAR": ("BLOOD_PRESSURE_ASSESSMENT",),
    "ED_TREATMENT_SATISFACTION": ("ED_TREATMENT_OUTCOMES",),
    "LIFESTYLE_AND_RISK_FACTORS": ("LIFESTYLE_RISK_FACTORS", "WEIGHT_LOSS_LIFESTYLE"),
    "PATIENT_DEMOGRAPHICS": ("DEMOGRAPHIC_AND_IDENTITY",),
    "ED_MEDICATION_HISTORY": ("ED_TREATMENT_HISTORY",),
    "OBESITY_PROFILE": ("OBESITY_COMORBIDITIES", "TREATMENT_PREFERENCE_AND_ELIGIBILITY"),
    "WEIGHT_LOSS_PROGRESS_AND_DOSING": ("WEIGHT_LOSS_TREATMENT_MONITORING",),
    "REORDER_AND_FOLLOW_UP_STATUS": ("WEIGHT_LOSS_TREATMENT_MONITORING",),
    "PATIENT_CONSENT_AND_CONFIRMATION": ("PATIENT_CONSENT_CONFIRMATION",),
    "ALLERGY_AND_CONTRAINDICATION_CHECK": ("TREATMENT_PREFERENCE_AND_ELIGIBILITY",),
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _extract_answer_values(normalized_value: Any) -> list[str]:
    """Return observed answer values from a normalized_value payload."""
    if _is_missing(normalized_value):
        return []

    if isinstance(normalized_value, dict):
        parsed = normalized_value
    else:
        try:
            parsed = json.loads(str(normalized_value))
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    if not isinstance(parsed, dict):
        return []

    vals = parsed.get("values", [])
    if not isinstance(vals, list):
        vals = [vals]
    if not vals and parsed.get("raw"):
        vals = [str(parsed["raw"])[:80]]

    out: list[str] = []
    for value in vals:
        stripped = str(value).strip()
        if stripped and stripped.lower() not in {"nan", "none", "null"}:
            out.append(stripped)
    return out


def _row_seen_at(row: pd.Series) -> str | None:
    for column in ("created_at", "updated_at", "first_order_at"):
        if column not in row or _is_missing(row.get(column)):
            continue
        ts = pd.to_datetime(row.get(column), errors="coerce", utc=True)
        if not pd.isna(ts):
            return ts.isoformat()
    return None


def _refresh_registry_observation_stats(
    registry: NormalizationRegistry,
    survey: pd.DataFrame,
) -> None:
    """Recompute registry counts/timestamps from the current survey rows."""
    for record in registry.records:
        record.source_count = 0
        record.first_seen = None
        record.last_seen = None

    for _, row in survey.iterrows():
        category = str(row.get("clinical_category", "") or "")
        if not category:
            continue
        seen_at = _row_seen_at(row)
        for value in _extract_answer_values(row.get("normalized_value")):
            record = registry.lookup(category, value, case_sensitive=True)
            if record is None:
                continue
            record.source_count += 1
            if seen_at is None:
                continue
            if record.first_seen is None or seen_at < record.first_seen:
                record.first_seen = seen_at
            if record.last_seen is None or seen_at > record.last_seen:
                record.last_seen = seen_at


def _apply_category_alias_migrations(
    registry: NormalizationRegistry,
    survey: pd.DataFrame,
) -> int:
    """Copy reviewed records across known taxonomy renames by exact value.

    This repairs stale registries created before category names stabilised.
    It deliberately does not guess: a migration happens only when the exact
    original answer text exists in one alias source category and all matching
    source records agree on the same canonical label.
    """
    index = {
        (record.category, record.original_value): record
        for record in registry.records
    }
    created = 0

    for _, row in survey.iterrows():
        category = str(row.get("clinical_category", "") or "")
        aliases = CATEGORY_ALIASES.get(category)
        if not aliases:
            continue

        for value in _extract_answer_values(row.get("normalized_value")):
            if (category, value) in index:
                continue

            candidates = [
                index[(alias, value)]
                for alias in aliases
                if (alias, value) in index
                and index[(alias, value)].review_status in {"approved", "overridden"}
            ]
            labels = {candidate.canonical_label for candidate in candidates}
            if len(labels) != 1:
                continue

            source = candidates[0]
            migrated = registry.upsert(
                category=category,
                original_value=value,
                canonical_label=source.canonical_label,
                review_status=source.review_status,
                source_count_delta=0,
                reviewed_by="category_alias_migration",
                reviewed_role="system",
                reviewed_at=pd.Timestamp.now(tz="UTC").isoformat(),
                review_note=f"exact-value migration from {source.category}",
            )
            index[(category, value)] = migrated
            created += 1

    return created


def _collect_unique_answers(survey: pd.DataFrame) -> dict[str, list[str]]:
    """Collect unique answer values per category that need normalization."""
    category_answers: dict[str, set[str]] = {}

    for _, row in survey.iterrows():
        cat = row.get("clinical_category", "")
        method = row.get("parse_method", "")
        if not cat or method in SKIP_PARSE_METHODS:
            continue

        vals = _extract_answer_values(row.get("normalized_value"))
        if vals:
            if cat not in category_answers:
                category_answers[cat] = set()
            for v in vals:
                v = str(v).strip()
                if v and v.lower() not in ("nan", ""):
                    category_answers[cat].add(v)

    # Only include categories with >1 unique answer (no point normalizing single values)
    return {cat: sorted(vals) for cat, vals in category_answers.items() if len(vals) > 1}


def _build_prompt(category_answers: dict[str, list[str]]) -> str:
    """Build the prompt with all answers grouped by category."""
    lines = []
    for cat in sorted(category_answers.keys()):
        lines.append(f"\nCATEGORY: {cat}")
        for val in category_answers[cat]:
            lines.append(f"  - {val}")
    return ANSWER_NORM_PROMPT + "\n".join(lines)


def normalize_answers_ai(survey: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Run AI-powered answer normalization in a single API call.

    Returns:
        survey: DataFrame with new 'answer_canonical' column
        answer_map: The full normalization mapping (saved as artifact)
    """
    print("\n[AI] === ANSWER NORMALIZATION ===")
    print("[AI] Single API call — AI sees ALL answer values across ALL categories.\n")

    # Check for existing normalization. We always go through the registry
    # so the on-disk format is normalised to v2 even when an older v1 file
    # is present (auto-migrates in-place). Downstream apply still consumes
    # the legacy `{category: {original: canonical}}` shape via
    # `as_legacy_map()` so this refactor is invisible to the rest of the
    # pipeline — but only approved/overridden records make it through, so
    # the validated layer is honest by construction.
    norm_path = config.OUTPUT_DIR / "answer_normalization.json"
    if norm_path.exists():
        print("[AI] Loading existing answer normalization (registry v2)...")
        migrated, count = migrate_legacy_to_v2()
        if migrated:
            print(f"[AI] Auto-migrated legacy v1 -> v2 ({count} records)")
        registry = NormalizationRegistry.from_disk()
        alias_count = _apply_category_alias_migrations(registry, survey)
        if alias_count:
            print(f"[AI] Migrated {alias_count} registry records across category aliases")
        _refresh_registry_observation_stats(registry, survey)
        registry.save()
        answer_map = registry.as_legacy_map()
        survey = _apply_normalization(survey, answer_map)
        return survey, answer_map

    # Collect unique answers
    category_answers = _collect_unique_answers(survey)
    total_values = sum(len(v) for v in category_answers.values())
    print(f"[AI] {len(category_answers)} categories, {total_values} unique answer values")

    if total_values == 0:
        print("[AI] No answers to normalize")
        survey["answer_canonical"] = None
        return survey, {}

    # Single API call
    prompt = _build_prompt(category_answers)
    result = _call_api(prompt, batch_label=f"all {total_values} answers across {len(category_answers)} categories")

    if result is None:
        print("[AI] API call failed — skipping answer normalization")
        survey["answer_canonical"] = None
        return survey, {}

    # Validate and clean the result. Cleaned dict is then upserted into
    # the registry as approved records (legacy AI output is treated as
    # production-ready because it was already in production use).
    answer_map = {}
    for cat, mappings in result.items():
        if isinstance(mappings, dict):
            answer_map[cat] = mappings

    registry = NormalizationRegistry.from_disk()
    for cat, mappings in answer_map.items():
        for original, canonical in mappings.items():
            registry.upsert(
                category=str(cat),
                original_value=str(original),
                canonical_label=str(canonical),
                review_status="approved",
                source_count_delta=0,
            )
    alias_count = _apply_category_alias_migrations(registry, survey)
    if alias_count:
        print(f"[AI] Migrated {alias_count} registry records across category aliases")
    _refresh_registry_observation_stats(registry, survey)
    registry.save()
    print(f"[AI] Saved normalization registry (v2) to {norm_path}")

    # Print summary
    total_mapped = sum(len(v) for v in answer_map.values())
    canonical_counts = {}
    for cat, mappings in answer_map.items():
        for original, canonical in mappings.items():
            canonical_counts[canonical] = canonical_counts.get(canonical, 0) + 1

    print(f"\n[AI] RESULTS:")
    print(f"  Answer values normalized: {total_mapped}")
    print(f"  Canonical labels created: {len(canonical_counts)}")
    for cat in sorted(answer_map.keys()):
        canonicals = set(answer_map[cat].values())
        print(f"  {cat:40s} {len(answer_map[cat]):>3} values → {len(canonicals):>3} canonical")

    # Apply to survey
    survey = _apply_normalization(survey, answer_map)
    return survey, answer_map


def _apply_normalization(survey: pd.DataFrame, answer_map: dict) -> pd.DataFrame:
    """Apply the canonical mapping to the survey dataframe.

    Side effects beyond the obvious `answer_canonical` column:
    - `normalization_status` column added with one of:
        `complete`     — every value resolved to a canonical label
        `partial`      — some values resolved, some did not (unknowns queued)
        `unknown`      — at least one value present but none resolved (queued)
        `no_mapping`   — the row's category has no registry entries at all
        `skipped`      — row had no parseable values (consent / file uploads / …)
    - Unknown answer values get appended to the normalization queue
      (`output/normalization_queue.json`) so a clinician can later review
      and either promote them into the registry or dismiss them.

    The queue write happens once at end-of-loop, not per-row, so a single
    unknown like "Yo" appearing 800 times bumps `occurrence_count` on a
    single queue entry rather than racing 800 file writes.
    """
    queue = NormalizationQueue.from_disk()
    for entry in queue.entries:
        if entry.status == "open":
            entry.occurrence_count = 0
    canonicals: list[str | None] = []
    statuses: list[str] = []
    queue_dirty = False

    for _, row in survey.iterrows():
        cat = str(row.get("clinical_category", "") or "")
        method = str(row.get("parse_method", "") or "")
        cat_map = answer_map.get(cat, {})

        if not cat:
            canonicals.append(None)
            statuses.append("skipped")
            continue

        if method in SKIP_PARSE_METHODS:
            canonicals.append(None)
            statuses.append("not_applicable")
            continue

        vals = _extract_answer_values(row.get("normalized_value"))
        if not vals:
            canonicals.append(None)
            statuses.append("skipped")
            continue

        seen_at = _row_seen_at(row)
        if not cat_map:
            for value in vals:
                queue.record_unknown(
                    category=cat,
                    original_value=value,
                    seen_at=seen_at,
                )
                queue_dirty = True
            canonicals.append(None)
            statuses.append("no_mapping")
            continue

        mapped: list[str] = []
        unknowns: list[str] = []
        for v in vals:
            stripped = str(v).strip()
            if not stripped:
                continue
            canonical = cat_map.get(stripped)
            if canonical:
                mapped.append(canonical)
            else:
                unknowns.append(stripped)

        for unk in unknowns:
            queue.record_unknown(category=cat, original_value=unk, seen_at=seen_at)
            queue_dirty = True

        if mapped and not unknowns:
            canonicals.append(json.dumps(mapped))
            statuses.append("complete")
        elif mapped and unknowns:
            canonicals.append(json.dumps(mapped))
            statuses.append("partial")
        else:
            canonicals.append(None)
            statuses.append("unknown")

    survey["answer_canonical"] = canonicals
    survey["normalization_status"] = statuses

    reconciled = 0
    for entry in list(queue.entries):
        if entry.status != "open":
            continue
        canonical = answer_map.get(entry.category, {}).get(entry.original_value)
        if not canonical:
            continue
        queue.resolve(
            entry.id,
            canonical_label=canonical,
            status="promoted",
            resolved_by="registry_reconciliation",
            resolved_role="system",
        )
        queue_dirty = True
        reconciled += 1

    before_prune = len(queue.entries)
    queue.entries = [
        entry
        for entry in queue.entries
        if entry.status != "open" or entry.occurrence_count > 0
    ]
    if len(queue.entries) != before_prune:
        queue_dirty = True

    if queue_dirty:
        queue.save()

    filled = survey["answer_canonical"].notna().sum()
    open_unknowns = sum(1 for e in queue.entries if e.status == "open")
    by_status: dict[str, int] = {}
    for s in statuses:
        by_status[s] = by_status.get(s, 0) + 1
    print(f"[AI] Applied canonical labels to {filled:,} / {len(survey):,} rows")
    print(f"[AI] Status distribution: {by_status}")
    if reconciled:
        print(f"[AI] Reconciled {reconciled} queue entries now covered by registry")
    if open_unknowns:
        print(f"[AI] Unknown queue: {open_unknowns} open entries awaiting review")
    return survey


if __name__ == "__main__":
    survey = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
    survey, answer_map = normalize_answers_ai(survey)
    survey.to_csv(config.SURVEY_UNIFIED_TABLE, index=False, encoding="utf-8")
    print(f"\n[AI] Updated {config.SURVEY_UNIFIED_TABLE}")
