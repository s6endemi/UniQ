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

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.classify_ai import _call_api

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


def _collect_unique_answers(survey: pd.DataFrame) -> dict[str, list[str]]:
    """Collect unique answer values per category that need normalization."""
    category_answers: dict[str, set[str]] = {}

    for _, row in survey.iterrows():
        cat = row.get("clinical_category", "")
        method = row.get("parse_method", "")
        if not cat or method in SKIP_PARSE_METHODS:
            continue

        try:
            parsed = json.loads(row["normalized_value"])
        except (json.JSONDecodeError, TypeError):
            continue

        vals = parsed.get("values", [])
        if not vals and "raw" in parsed and parsed["raw"]:
            vals = [str(parsed["raw"])[:80]]

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

    # Check for existing normalization
    norm_path = config.OUTPUT_DIR / "answer_normalization.json"
    if norm_path.exists():
        print("[AI] Loading existing answer normalization...")
        answer_map = json.loads(norm_path.read_text(encoding="utf-8"))
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

    # Validate and clean the result
    answer_map = {}
    for cat, mappings in result.items():
        if isinstance(mappings, dict):
            answer_map[cat] = mappings

    # Save artifact
    norm_path.write_text(json.dumps(answer_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[AI] Saved normalization map to {norm_path}")

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
    """Apply the canonical mapping to the survey dataframe."""
    canonicals = []

    for _, row in survey.iterrows():
        cat = row.get("clinical_category", "")
        cat_map = answer_map.get(cat, {})

        if not cat_map:
            canonicals.append(None)
            continue

        try:
            parsed = json.loads(row["normalized_value"])
        except (json.JSONDecodeError, TypeError):
            canonicals.append(None)
            continue

        vals = parsed.get("values", [])
        if not vals and "raw" in parsed:
            vals = [str(parsed["raw"])[:80]]

        mapped = []
        for v in vals:
            canonical = cat_map.get(str(v).strip())
            if canonical:
                mapped.append(canonical)

        canonicals.append(json.dumps(mapped) if mapped else None)

    survey["answer_canonical"] = canonicals
    filled = survey["answer_canonical"].notna().sum()
    print(f"[AI] Applied canonical labels to {filled:,} / {len(survey):,} rows")
    return survey


if __name__ == "__main__":
    survey = pd.read_csv(config.SURVEY_UNIFIED_TABLE, low_memory=False)
    survey, answer_map = normalize_answers_ai(survey)
    survey.to_csv(config.SURVEY_UNIFIED_TABLE, index=False, encoding="utf-8")
    print(f"\n[AI] Updated {config.SURVEY_UNIFIED_TABLE}")
