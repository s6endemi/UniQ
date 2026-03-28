"""
AI-Powered Question Classification Engine

This is the core of the product. No hardcoded rules, no predefined categories.
The AI analyzes all questions and:
  1. Discovers natural clinical groupings
  2. Proposes a taxonomy with definitions
  3. Classifies every question with confidence scores
  4. Outputs a draft mapping for human-in-the-loop validation

Two modes:
  - Discovery: First run on new data. AI proposes everything from scratch.
  - Incremental: New questions added to existing data. AI classifies against
    the validated taxonomy. Only truly novel questions trigger new categories.
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.load import load_raw_data


# ── Prompts ──────────────────────────────────────────────────────────────────

DISCOVERY_PROMPT = """You are a data classification expert. You are analyzing ALL unique questions
from a structured questionnaire/survey system in a SINGLE pass. You see every question at once,
so your categories must be globally consistent.

The questions come from a digital health platform, but your classification approach should
work for ANY domain with evolving questionnaire data.

Each question has:
- An ID number (representative — many IDs share the same text)
- The question text
- The available answer options (if predefined) or sample answer values (if free-form)

YOUR TASKS:
1. Read ALL questions first, then identify natural thematic groupings
2. Propose 10-20 categories (not more). Use UPPER_SNAKE_CASE names that are:
   - Domain-specific and descriptive (e.g., BMI_MEASUREMENT, not QUESTION_TYPE_1)
   - Granular enough to be useful (not just "MEDICAL" or "PERSONAL")
   - Broad enough that similar questions share one category
3. Assign each question to exactly one category
4. Rate your confidence: high (obvious fit), medium (reasonable), low (uncertain)

CATEGORY DESIGN RULES:
- Aim for 10-20 categories total. If you find yourself creating 25+, you are too granular.
- Merge related concepts: e.g. all side-effect questions → one SIDE_EFFECT_REPORT category,
  not separate ones for "monitoring" vs "assessment" vs "history"
- All consent/confirmation questions (where the answer is "I confirm/understand") → one category
- All photo/document upload questions → group by what's uploaded (body photo, ID photo)
- Questions asking about the same clinical concept with different wording → SAME category

Return valid JSON:
{
  "taxonomy": [
    {"category": "BMI_MEASUREMENT", "definition": "Questions collecting height, weight, or BMI data"},
    ...
  ],
  "classifications": [
    {"id": 37149, "category": "BMI_MEASUREMENT", "confidence": "high"},
    ...
  ]
}

QUESTIONS:
"""

INCREMENTAL_PROMPT = """You are a data classification expert. An existing taxonomy has been validated
by domain experts. New questions have appeared that need to be classified.

EXISTING VALIDATED TAXONOMY:
{taxonomy}

NEW QUESTIONS TO CLASSIFY:
{questions}

For each question, classify it into one of the existing categories.
Only propose a NEW category if the question truly doesn't fit any existing one.

Return valid JSON:
{{
  "classifications": [
    {{"id": 12345, "category": "EXISTING_CATEGORY", "confidence": "high"}},
    ...
  ],
  "new_categories": [
    {{"category": "NEW_CATEGORY_NAME", "definition": "Why this is needed"}}
  ]
}}
"""


# ── API Call Logic ───────────────────────────────────────────────────────────

def _call_api(prompt: str, batch_label: str = "") -> dict | None:
    """Call Claude API with retry logic. Returns parsed JSON or None."""
    try:
        import anthropic
    except ImportError:
        print("[AI] ERROR: anthropic package not installed")
        return None

    if not config.ANTHROPIC_API_KEY:
        print("[AI] ERROR: ANTHROPIC_API_KEY not set")
        return None

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        try:
            label = f" ({batch_label})" if batch_label else ""
            print(f"  [AI] Calling {config.LLM_MODEL}{label} (attempt {attempt})...", end=" ", flush=True)

            response = client.messages.create(
                model=config.LLM_MODEL,
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text
            t_in = response.usage.input_tokens
            t_out = response.usage.output_tokens
            print(f"OK ({t_in:,} in / {t_out:,} out)")

            # Extract JSON
            json_str = raw
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            return json.loads(json_str.strip())

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
        except Exception as e:
            print(f"Error: {e}")

        if attempt < config.LLM_MAX_RETRIES:
            delay = config.LLM_RETRY_BASE_DELAY ** attempt
            print(f"  Retrying in {delay}s...")
            time.sleep(delay)

    print(f"  [AI] FAILED after {config.LLM_MAX_RETRIES} attempts")
    return None


# ── Format Questions for Prompt ──────────────────────────────────────────────

def _format_questions_for_prompt(questions_df: pd.DataFrame, raw_df: pd.DataFrame) -> str:
    """Format questions with their answer options for the AI prompt."""
    lines = []
    for _, row in questions_df.iterrows():
        qid = int(row["question_id"])
        text = row["question_en"]

        # Get answer options from the raw data
        q_rows = raw_df[raw_df["question_id"] == qid]
        answers = q_rows["answer_en"].dropna().unique()
        sample_vals = q_rows["answer_value"].dropna().unique()[:3]

        line = f"- ID: {qid} | {text}"

        if len(answers) > 0 and len(answers) <= 10:
            line += f"\n  Answers: {list(answers)}"
        elif len(sample_vals) > 0:
            line += f"\n  Sample values: {[str(v)[:60] for v in sample_vals]}"

        lines.append(line)

    return "\n".join(lines)


# ── Discovery Mode ───────────────────────────────────────────────────────────

def discover_taxonomy(df: pd.DataFrame) -> dict:
    """Run full discovery — AI proposes taxonomy from scratch in a SINGLE call.

    All unique question texts are sent together so the AI sees the full picture
    and produces globally consistent categories. No batching = no duplicates.
    """
    print("\n[AI] === DISCOVERY MODE ===")
    print("[AI] AI will analyze all questions and propose categories from scratch.")
    print("[AI] No hardcoded rules. No predefined categories.")
    print("[AI] Single API call — AI sees ALL questions at once for consistency.\n")

    # Get unique questions (one per text, using lowest ID as representative)
    deduped = (
        df.groupby("question_en")["question_id"]
        .min()
        .reset_index()
        .sort_values("question_id")
    )

    n = len(deduped)
    print(f"[AI] {n} unique question texts to classify in one call")

    # Format all questions
    questions_str = _format_questions_for_prompt(deduped, df)

    # Single API call with all questions
    prompt = DISCOVERY_PROMPT + questions_str
    result = _call_api(prompt, batch_label=f"all {n} questions")

    if result is None:
        print("[AI] API call failed — all questions will be UNCLASSIFIED")
        return {
            "taxonomy": [],
            "text_to_category": {t: {"category": "UNCLASSIFIED", "confidence": "none"}
                                  for t in deduped["question_en"]},
            "mode": "discovery",
        }

    taxonomy = result.get("taxonomy", [])
    classifications = result.get("classifications", [])

    print(f"\n[AI] Discovery complete:")
    print(f"  Categories proposed: {len(taxonomy)}")
    print(f"  Questions classified: {len(classifications)}")

    # Print taxonomy
    print(f"\n[AI] PROPOSED TAXONOMY:")
    for t in sorted(taxonomy, key=lambda x: x.get("category", "")):
        print(f"  {t['category']:40s} — {t.get('definition', '')[:60]}")

    # Build the mapping: expand from representative IDs to ALL IDs with same text
    text_to_cat = {}
    for c in classifications:
        rep_id = c["id"]
        match = deduped[deduped["question_id"] == rep_id]
        if len(match) > 0:
            text = match.iloc[0]["question_en"]
            text_to_cat[text] = {
                "category": c.get("category", "UNCLASSIFIED"),
                "confidence": c.get("confidence", "medium"),
            }

    # Check for missed questions — re-classify them with a focused follow-up call
    classified_texts = set(text_to_cat.keys())
    all_texts = set(deduped["question_en"])
    missed = all_texts - classified_texts
    if missed:
        print(f"\n[AI] {len(missed)} questions missed in initial response — running follow-up call...")
        missed_df = deduped[deduped["question_en"].isin(missed)]
        taxonomy_str = "\n".join(f"- {t['category']}: {t.get('definition','')}" for t in taxonomy)
        missed_prompt = INCREMENTAL_PROMPT.format(
            taxonomy=taxonomy_str,
            questions=_format_questions_for_prompt(missed_df, df),
        )
        followup = _call_api(missed_prompt, batch_label=f"{len(missed)} missed questions")
        if followup:
            for c in followup.get("classifications", []):
                rep_id = c["id"]
                match = missed_df[missed_df["question_id"] == rep_id]
                if len(match) > 0:
                    text = match.iloc[0]["question_en"]
                    text_to_cat[text] = {
                        "category": c.get("category", "UNCLASSIFIED"),
                        "confidence": c.get("confidence", "medium"),
                    }
                    print(f"  [AI] Recovered: {text[:60]}... → {c['category']}")

        # Anything still missed gets UNCLASSIFIED
        still_missed = all_texts - set(text_to_cat.keys())
        for t in still_missed:
            text_to_cat[t] = {"category": "UNCLASSIFIED", "confidence": "none"}

    return {
        "taxonomy": taxonomy,
        "text_to_category": text_to_cat,
        "mode": "discovery",
    }


# ── Incremental Mode ────────────────────────────────────────────────────────

def classify_new_questions(df: pd.DataFrame, existing_mapping: pd.DataFrame) -> dict:
    """Classify only NEW questions against an existing validated taxonomy.

    Questions whose text already exists in the mapping get their existing category.
    Only truly new texts go to the AI.
    """
    print("\n[AI] === INCREMENTAL MODE ===")

    # Find new question texts
    known_texts = set(existing_mapping["question_en"].unique())
    all_texts = df.drop_duplicates(subset="question_en")

    new_texts = all_texts[~all_texts["question_en"].isin(known_texts)]
    known_in_data = all_texts[all_texts["question_en"].isin(known_texts)]

    print(f"[AI] Known question texts (reusing mapping): {len(known_in_data)}")
    print(f"[AI] New question texts (need classification): {len(new_texts)}")

    if len(new_texts) == 0:
        print("[AI] No new questions — reusing existing mapping entirely.")
        return {"taxonomy": [], "text_to_category": {}, "mode": "incremental", "new_count": 0}

    # Build taxonomy string from existing mapping
    existing_cats = existing_mapping.drop_duplicates(subset="clinical_category")
    taxonomy_str = "\n".join(
        f"- {row['clinical_category']}"
        for _, row in existing_cats.iterrows()
    )

    # Batch new questions if > 200 (taxonomy is fixed, so batching is safe here)
    text_to_cat = {}
    new_taxonomy = []
    batch_size = 200

    batches = [new_texts.iloc[i:i + batch_size] for i in range(0, len(new_texts), batch_size)]

    for b_idx, batch in enumerate(batches):
        questions_str = _format_questions_for_prompt(batch, df)
        prompt = INCREMENTAL_PROMPT.format(taxonomy=taxonomy_str, questions=questions_str)
        label = f"{len(batch)} questions" if len(batches) == 1 else f"batch {b_idx+1}/{len(batches)}"
        result = _call_api(prompt, batch_label=label)

        if result:
            for c in result.get("classifications", []):
                rep_id = c["id"]
                match = batch[batch["question_id"] == rep_id]
                if len(match) > 0:
                    text = match.iloc[0]["question_en"]
                    text_to_cat[text] = {
                        "category": c.get("category", "UNCLASSIFIED"),
                        "confidence": c.get("confidence", "medium"),
                    }
            new_taxonomy.extend(result.get("new_categories", []))

    print(f"[AI] Classified {len(text_to_cat)} new question texts")
    if new_taxonomy:
        print(f"[AI] New categories proposed: {[c['category'] for c in new_taxonomy]}")

    return {
        "taxonomy": new_taxonomy,
        "text_to_category": text_to_cat,
        "mode": "incremental",
        "new_count": len(new_texts),
    }


# ── Build Mapping Table ─────────────────────────────────────────────────────

def _detect_answer_type(row: pd.Series, df: pd.DataFrame) -> str:
    """Detect the answer type for a question based on the actual data."""
    qid = row["question_id"]
    q_rows = df[df["question_id"] == qid]

    sample_vals = q_rows["answer_value"].dropna().unique()[:10]
    has_answer_id = q_rows["answer_id"].notna().any()
    has_height = q_rows["answer_value_height"].notna().any() if "answer_value_height" in q_rows.columns else False

    # JSON structured (BMI data)
    for v in sample_vals:
        v_str = str(v).strip()
        if v_str.startswith("{"):
            try:
                json.loads(v_str)
                return "json_structured"
            except (json.JSONDecodeError, ValueError):
                pass

    if has_height:
        return "json_structured"

    # File upload
    for v in sample_vals:
        v_str = str(v).strip()
        if "answerfile" in v_str.lower():
            return "file_upload"
        if len(v_str) == 24 and v_str.isalnum():
            return "file_upload"

    upload_words = ["später hochladen", "upload later", "upload photo"]
    for v in sample_vals:
        if any(w in str(v).lower() for w in upload_words):
            return "file_upload"

    # Confirmation
    confirm_words = ["verstehe und bestätige", "understand and confirm", "i confirm"]
    for v in sample_vals:
        if any(w in str(v).lower() for w in confirm_words):
            return "confirmation"

    if has_answer_id:
        return "predefined"

    return "free_text"


def build_mapping(df: pd.DataFrame, ai_result: dict, existing_mapping: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the mapping table from AI classification results.

    Combines:
    - AI-proposed categories for new/all questions
    - Existing mapping for known questions (incremental mode)
    - Deterministic answer_type detection
    """
    print("\n[Mapping] Building mapping table...")

    # Start with all unique question_id → question_en pairs
    all_questions = (
        df.groupby("question_id")
        .agg(
            question_en=("question_en", "first"),
            question_de=("question_de", "first"),
            row_count=("question_id", "size"),
        )
        .reset_index()
    )

    # Map categories
    text_to_cat = ai_result["text_to_category"]

    # For incremental mode, also include existing mapping
    if existing_mapping is not None:
        existing_text_cat = dict(zip(
            existing_mapping["question_en"],
            existing_mapping["clinical_category"],
        ))
        # Existing takes priority, AI fills gaps
        for text, info in text_to_cat.items():
            if text not in existing_text_cat:
                existing_text_cat[text] = info["category"]
        final_text_cat = existing_text_cat
    else:
        final_text_cat = {text: info["category"] for text, info in text_to_cat.items()}

    all_questions["clinical_category"] = all_questions["question_en"].map(final_text_cat)
    all_questions["clinical_category"] = all_questions["clinical_category"].fillna("UNCLASSIFIED")

    # Confidence
    confidence_map = {text: info.get("confidence", "medium") for text, info in text_to_cat.items()}
    all_questions["confidence"] = all_questions["question_en"].map(confidence_map).fillna("high")

    # Detect answer type deterministically
    print("[Mapping] Detecting answer types...")
    answer_types = []
    for _, row in all_questions.iterrows():
        answer_types.append(_detect_answer_type(row, df))
    all_questions["answer_type"] = answer_types

    # Duplicate group
    text_to_group = {}
    for i, text in enumerate(all_questions["question_en"].unique(), 1):
        text_to_group[text] = i
    all_questions["duplicate_group_id"] = all_questions["question_en"].map(text_to_group)

    dup_counts = all_questions.groupby("question_en")["question_id"].count()
    all_questions["duplicate_count"] = all_questions["question_en"].map(dup_counts)

    canonical = all_questions.groupby("duplicate_group_id")["question_id"].min().reset_index()
    canonical.columns = ["duplicate_group_id", "canonical_question_id"]
    all_questions = all_questions.merge(canonical, on="duplicate_group_id", how="left")

    # Save
    mapping = all_questions[[
        "question_id", "question_en", "question_de",
        "clinical_category", "answer_type", "confidence",
        "duplicate_group_id", "canonical_question_id",
        "duplicate_count", "row_count",
    ]]

    mapping.to_csv(config.MAPPING_TABLE, index=False, encoding="utf-8")

    # Save taxonomy
    taxonomy_path = config.OUTPUT_DIR / "taxonomy.json"
    taxonomy_data = {
        "categories": ai_result.get("taxonomy", []),
        "mode": ai_result.get("mode", "discovery"),
        "total_questions": len(mapping),
        "total_categories": mapping["clinical_category"].nunique(),
    }
    taxonomy_path.write_text(json.dumps(taxonomy_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print summary
    print(f"\n[Mapping] RESULTS:")
    cat_stats = mapping.drop_duplicates(subset="question_en").groupby("clinical_category").size().sort_values(ascending=False)
    for cat, count in cat_stats.items():
        total_ids = len(mapping[mapping["clinical_category"] == cat])
        data_rows = len(df[df["question_en"].isin(mapping[mapping["clinical_category"] == cat]["question_en"])])
        print(f"  {cat:35s} {count:>3} texts  {total_ids:>5} IDs  {data_rows:>6,} rows")

    unclassified = mapping[mapping["clinical_category"] == "UNCLASSIFIED"]
    if len(unclassified) > 0:
        print(f"\n[WARNING] {unclassified['question_en'].nunique()} texts UNCLASSIFIED:")
        for text in unclassified["question_en"].unique():
            print(f"  {text[:80]}...")

    print(f"\n[Mapping] Saved {len(mapping)} entries to {config.MAPPING_TABLE}")
    print(f"[Mapping] Taxonomy saved to {taxonomy_path}")

    return mapping


# ── Main Runner ──────────────────────────────────────────────────────────────

def _load_validated_taxonomy() -> list[dict] | None:
    """Load the validated taxonomy if it exists.

    The taxonomy is the human-approved category list. It persists across
    pipeline runs and new datasets. It only gets created from scratch on
    the very first run (discovery mode).
    """
    taxonomy_path = config.OUTPUT_DIR / "taxonomy.json"
    if taxonomy_path.exists():
        data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        cats = data.get("categories", [])
        if cats:
            return cats
    return None


def run_classification(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Run the full AI classification pipeline.

    Logic:
    1. taxonomy.json exists (human-validated)?
       → Incremental: classify all questions against it. Preserve categories.
       → Only new texts that don't match any existing mapping go to AI.
    2. No taxonomy?
       → Discovery: AI proposes everything from scratch.

    This ensures the validated taxonomy is NEVER destroyed by re-runs.
    """
    if df is None:
        df = load_raw_data(config.RAW_DATA_FILE)
        if df is None:
            sys.exit(1)

    # Check for existing taxonomy (the protected artifact)
    existing_taxonomy = _load_validated_taxonomy()
    existing_mapping = None
    if config.MAPPING_TABLE.exists():
        existing_mapping = pd.read_csv(config.MAPPING_TABLE)

    if existing_taxonomy and existing_mapping is not None:
        # Incremental mode — preserve validated taxonomy
        known_texts = set(existing_mapping["question_en"].unique())
        data_texts = set(df["question_en"].unique())
        new_texts = data_texts - known_texts

        if new_texts:
            print(f"[AI] Validated taxonomy found with {len(existing_taxonomy)} categories")
            print(f"[AI] Found {len(new_texts)} new question texts — running incremental classification")
            ai_result = classify_new_questions(df, existing_mapping)
            mapping = build_mapping(df, ai_result, existing_mapping)
        else:
            # All questions mapped — but rebuild mapping to include any new IDs for known texts
            known_ids = set(existing_mapping["question_id"].unique())
            data_ids = set(df["question_id"].dropna().astype(int).unique())
            new_ids = data_ids - known_ids

            if new_ids:
                print(f"[AI] All texts known. {len(new_ids)} new IDs for existing texts — expanding mapping")
                # Re-use existing text→category mapping, just expand to new IDs
                ai_result = {"taxonomy": existing_taxonomy, "text_to_category": {}, "mode": "incremental"}
                mapping = build_mapping(df, ai_result, existing_mapping)
            else:
                print(f"[AI] All questions and IDs already mapped — skipping classification")
                return existing_mapping
    elif existing_taxonomy:
        # Taxonomy exists but no mapping (e.g., mapping was deleted)
        # Classify all questions against the validated taxonomy
        print(f"[AI] Validated taxonomy found — classifying all questions against it")
        # Create a dummy mapping from taxonomy to trigger incremental mode
        dummy = pd.DataFrame({"question_en": [], "clinical_category": []})
        ai_result = classify_new_questions(df, dummy)
        mapping = build_mapping(df, ai_result, None)
    else:
        # No taxonomy at all — full discovery
        print("[AI] No existing taxonomy — running full discovery")
        ai_result = discover_taxonomy(df)
        mapping = build_mapping(df, ai_result, None)

    return mapping


if __name__ == "__main__":
    run_classification()
