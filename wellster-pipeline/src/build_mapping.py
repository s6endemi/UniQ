"""
Build the question → clinical_category mapping table deterministically.

This assigns each of the 84 unique question texts to a clinical category,
then expands to all 677 question_ids. Produces:
  - output/mapping_table.csv (the pipeline artifact)
  - output/mapping_review.txt (human-readable review document)
"""

import ast
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.load import load_raw_data

# ---------------------------------------------------------------------------
# Clinical taxonomy — 15 categories derived from manual review of 84 questions
# ---------------------------------------------------------------------------

CLINICAL_TAXONOMY = {
    "BMI_MEASUREMENT": "Height, weight, and BMI data collection for treatment eligibility",
    "PHOTO_UPLOAD_BODY": "Full-body photo for clinical assessment of body composition",
    "PHOTO_UPLOAD_ID": "Identity document photo for patient verification",
    "PHOTO_UPLOAD_COMBINED": "Combined body + ID photo upload prompt (upload now or later)",
    "COMORBIDITY_SCREENING": "Screening for pre-existing conditions relevant to GLP-1 treatment (dyslipidaemia, sleep apnoea, prediabetes, etc.)",
    "CONTRAINDICATION_CHECK": "Current medications or symptoms that may contraindicate treatment",
    "MEDICAL_HISTORY_FREE": "Free-text input of pre-existing conditions or medications",
    "PRIOR_GLP1_USE": "Previous use of GLP-1/GIP medications (liraglutide, semaglutide, tirzepatide) and outcomes",
    "PRIOR_WEIGHT_LOSS": "Non-medication weight loss attempts (diet, exercise, apps, counselling)",
    "WEIGHT_LOSS_GOAL": "Whether patient achieved weight loss goals through lifestyle changes",
    "WEIGHT_DURATION": "Duration of weight problems (childhood, 1-5 years, 5+ years)",
    "HUNGER_ASSESSMENT": "Subjective hunger and eating behavior patterns",
    "SIDE_EFFECT_REPORT": "Side effects experienced since starting/last prescription",
    "TREATMENT_PROGRESS": "Follow-up assessments: dosage, compliance, weight loss, new diagnoses, dose continuation",
    "TREATMENT_CONSENT": "Informed consent, treatment confirmations, disclaimers, safety acknowledgment",
    "BLOOD_PRESSURE": "Blood pressure readings for cardiovascular risk monitoring",
    "EXERCISE_FREQUENCY": "How often the patient exercises — lifestyle assessment",
}

# ---------------------------------------------------------------------------
# Mapping rules: question text substring → category
# Using substring matching on English text for robustness
# ---------------------------------------------------------------------------

def classify_question(question_en: str, answer_options: list, sample_values: list) -> tuple[str, str]:
    """Classify a question into a clinical category based on text + answer context.

    Returns (category, answer_type).
    """
    q = question_en.lower()
    opts_str = " ".join(str(o).lower() for o in answer_options) if answer_options else ""
    samples_str = " ".join(str(s)[:50].lower() for s in sample_values) if sample_values else ""

    # --- Answer type detection (deterministic) ---
    if any(s.strip().startswith("{") for s in sample_values if isinstance(s, str)):
        answer_type = "json_structured"
    elif any("answerfile" in str(s).lower() for s in sample_values if isinstance(s, str)):
        answer_type = "file_upload"
    elif "später hochladen" in samples_str or "upload later" in opts_str or "upload photo" in opts_str:
        answer_type = "file_upload"
    elif "confirm" in opts_str or "verstehe" in opts_str or "bestätige" in opts_str:
        answer_type = "confirmation"
    elif len(answer_options) > 0:
        answer_type = "predefined"
    else:
        answer_type = "free_text"

    # For file_upload detection: raw hash strings (24 chars, alphanumeric) in sample_values
    # BUT only if no predefined answer options exist — avoids false positives
    if answer_type not in ("json_structured", "confirmation") and len(answer_options) == 0:
        if any(len(str(s).strip()) == 24 and str(s).strip().isalnum() for s in sample_values if isinstance(s, str)):
            answer_type = "file_upload"

    # --- Category assignment ---
    # Order matters: more specific rules first, general rules last.

    # ── BMI measurement — height/weight/BMI collection ──
    if ("height and weight" in q or "bmi" in q) and ("calculate" in q or "evaluate" in q or "check" in q or "assess" in q):
        return "BMI_MEASUREMENT", "json_structured"

    # ── Photo uploads — must match BEFORE consent rules ──
    # Combined upload prompts (body + ID in one question)
    if "following documents" in q and ("full body" in q or "identity" in q):
        return "PHOTO_UPLOAD_COMBINED", "file_upload"
    if "check your enquiry" in q and ("full body" in q or "full-body" in q or "photo" in q):
        return "PHOTO_UPLOAD_COMBINED", "file_upload"

    # Full body photo upload
    if ("full-body photo" in q or "full body photo" in q or "ganzkörperfoto" in q) and "upload" in q:
        return "PHOTO_UPLOAD_BODY", "file_upload"

    # ID photo upload
    if ("identity card" in q or "passport" in q or "upload id" in q) and ("photo" in q or "upload" in q):
        return "PHOTO_UPLOAD_ID", "file_upload"

    # ── Hunger assessment ──
    if "hunger" in q or "sense of hunger" in q or "feeling of hunger" in q:
        return "HUNGER_ASSESSMENT", answer_type

    # ── Weight duration ──
    if "how long have you had weight problems" in q:
        return "WEIGHT_DURATION", answer_type

    # ── Treatment consent — must match BEFORE drug-name rules to avoid ──
    # ── consent texts that mention liraglutide/semaglutide being misclassified ──
    if "please confirm" in q or "confirm that" in q or "confirm the following" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "truthfully" in q and "confirm" in q:
        return "TREATMENT_CONSENT", "confirmation"

    # ── Prior GLP-1 medication use (question about past usage, NOT consent) ──
    if ("liraglutide" in q or "semaglutide" in q or "tirzepatide" in q) and ("past" in q or "used" in q):
        return "PRIOR_GLP1_USE", answer_type
    # Side effect history with these specific medications (initial questionnaire)
    if "active ingredient" in q and ("effective" in q or "well tolerated" in q) and "side effects" in q:
        return "PRIOR_GLP1_USE", answer_type

    # ── Side effect reports (follow-up) ──
    if "side effects occurred" in q or "side effects since" in q:
        return "SIDE_EFFECT_REPORT", "predefined"

    # ── Prior weight loss attempts — includes follow-up variant ──
    if "weight loss measures" in q or "measures to lose weight" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type
    if "measures besides" in q and "lose weight" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type
    if "measures" in q and "lose weight" in q and "parallel" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type

    # ── Weight loss goal achievement ──
    if "weight loss goals" in q or "lost at least 5%" in q:
        return "WEIGHT_LOSS_GOAL", answer_type

    # ── Comorbidity screening — checklist of conditions ──
    if "following conditions" in q or "following diseases" in q or "following illnesses" in q:
        return "COMORBIDITY_SCREENING", answer_type
    if "following conditions apply" in q:
        return "COMORBIDITY_SCREENING", answer_type

    # ── Contraindication check — current medications ──
    if "currently taking" in q and "medication" in q:
        return "CONTRAINDICATION_CHECK", answer_type
    if "prescription medications are you currently" in q:
        return "CONTRAINDICATION_CHECK", answer_type
    if "prescription medication" in q and ("taking" in q or "are you" in q):
        return "CONTRAINDICATION_CHECK", answer_type

    # ── Medical history free text ──
    if "what other pre-existing conditions" in q or "what other prescription" in q:
        return "MEDICAL_HISTORY_FREE", "free_text"
    if "pre-existing conditions" in q and "suffering" in q:
        return "MEDICAL_HISTORY_FREE", answer_type

    # ── Treatment progress — follow-up assessments ──
    if "continue treatment" in q or "next medically recommended dose" in q:
        return "TREATMENT_PROGRESS", answer_type
    if ("dosage" in q or "dose" in q) and ("currently" in q or "taking" in q):
        return "TREATMENT_PROGRESS", answer_type
    if "lost body weight" in q and "treatment" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "without interruption" in q or "without gaps" in q or "regularly" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "how regularly" in q and "inject" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "new prescription medication" in q or "new prescription medicines" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "new health problems" in q or "new diagnoses" in q or "new disease" in q or "new illness" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "diagnosed with a new" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "following statements apply" in q and ("active" in opts_str or "fitter" in opts_str or "confident" in opts_str):
        return "TREATMENT_PROGRESS", answer_type
    if "following statements apply" in q:
        return "TREATMENT_PROGRESS", answer_type
    if "symptoms" in q and ("weight loss" in q or "past few weeks" in q or "last few weeks" in q):
        return "TREATMENT_PROGRESS", answer_type
    if "satisfied" in q and ("dose" in q or "weight development" in q):
        return "TREATMENT_PROGRESS", answer_type
    if "maintain your current" in q and "dose" in q:
        return "TREATMENT_PROGRESS", answer_type

    # ── Blood pressure (new in larger dataset) ──
    if "blood pressure" in q:
        return "BLOOD_PRESSURE", answer_type

    # ── Exercise / sports frequency (new in larger dataset) ──
    if "how often" in q and ("sport" in q or "exercise" in q):
        return "EXERCISE_FREQUENCY", answer_type

    # ── Side effects from new question patterns ──
    if "side effect" in q and ("experience" in q or "notice" in q or "during use" in q):
        return "SIDE_EFFECT_REPORT", "predefined"

    # ── Prior weight loss — additional patterns ──
    if "weight loss" in q and ("parallel" in q or "besides" in q or "other" in q):
        return "PRIOR_WEIGHT_LOSS", answer_type
    if "other measures" in q and "lose weight" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type
    if "other weight loss measures" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type
    if "done anything else" in q and "weight" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type
    if "tried other weight loss" in q:
        return "PRIOR_WEIGHT_LOSS", answer_type

    # ── Prior GLP-1 — additional patterns ──
    if "incretin-based" in q or ("taken" in q and ("saxenda" in q or "wegovy" in q or "mounjaro" in q)):
        return "PRIOR_GLP1_USE", answer_type

    # ── Medical history free text — additional patterns ──
    if "other illnesses" in q and ("taking" in q or "medication" in q):
        return "MEDICAL_HISTORY_FREE", answer_type

    # ── Comorbidity — additional patterns ──
    if "any of the following conditions" in q or "following illnesses" in q:
        return "COMORBIDITY_SCREENING", answer_type

    # ── Weight duration — additional patterns ──
    if "how long" in q and "weight problems" in q:
        return "WEIGHT_DURATION", answer_type

    # ── Photo uploads — additional patterns ──
    if "photo of" in q and ("id" in q or "identity" in q or "identification" in q or "passport" in q):
        return "PHOTO_UPLOAD_ID", "file_upload"
    if ("photo of you" in q or "full body photo" in q or "full-body photo" in q) and "upload" in q.lower():
        return "PHOTO_UPLOAD_BODY", "file_upload"
    if "medical team" in q and "photo" in q and ("check" in q or "review" in q):
        return "PHOTO_UPLOAD_BODY", "file_upload"
    if "following photos" in q:
        return "PHOTO_UPLOAD_COMBINED", "file_upload"

    # ── Treatment consent — remaining consent patterns ──
    if "i understand" in opts_str and "confirm" in opts_str:
        return "TREATMENT_CONSENT", "confirmation"
    if "drug treatment should not" in q or "first choice" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "gastrointestinal complaints" in q or "tips for side effects" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "forgot to inject" in q or "dose is skipped" in q or "dose is missed" in q or "missed dose" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "your health is our" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "important after" in q and ("break" in q or "interruption" in q):
        return "TREATMENT_CONSENT", "confirmation"
    if "note to doctor" in q or "special medical questionnaire" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "personal initiative" in q and "confirm" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "go on" in q and len(q) < 20:
        return "TREATMENT_CONSENT", "confirmation"
    if "attention" in q and "easy reorder" in q:
        return "TREATMENT_CONSENT", "confirmation"
    if "noticeable weight loss" in q and "together" in q:
        return "TREATMENT_CONSENT", "confirmation"

    # Fallback
    return "OTHER", answer_type


def _classify_with_api(questions: list[dict]) -> dict[str, str]:
    """Use Claude API to classify questions that the rule-based classifier couldn't handle.

    This is the scalability layer — when new question types appear that don't match
    any existing rules, the API classifies them against the known taxonomy.
    """
    if not config.ANTHROPIC_API_KEY:
        print(f"[Mapping] {len(questions)} questions classified as OTHER (no API key for fallback)")
        return {}

    try:
        import anthropic
    except ImportError:
        print("[Mapping] anthropic package not installed — skipping API fallback")
        return {}

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    categories = sorted(CLINICAL_TAXONOMY.keys())
    taxonomy_str = "\n".join(f"- {k}: {v}" for k, v in sorted(CLINICAL_TAXONOMY.items()))

    print(f"\n[Mapping] Classifying {len(questions)} unmatched questions via Claude API...")

    # Build prompt with all unmatched questions
    q_lines = []
    for i, q in enumerate(questions, 1):
        line = f"{i}. {q['question_en'][:200]}"
        if q["answer_options"]:
            line += f"\n   Answer options: {q['answer_options'][:5]}"
        q_lines.append(line)

    prompt = f"""You are a medical data classifier for a digital obesity telehealth platform.

Classify each question into EXACTLY ONE of these clinical categories:

{taxonomy_str}

If none fits well, you may suggest a new category name in UPPER_SNAKE_CASE.

QUESTIONS:
{chr(10).join(q_lines)}

Return a JSON array, one object per question:
[{{"index": 1, "category": "CATEGORY_NAME", "confidence": "high|medium|low"}}]

Return ONLY the JSON array, no other text."""

    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.LLM_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            print(f"[Mapping] API response: {tokens_in} in / {tokens_out} out")

            # Parse JSON
            json_str = raw
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            results = json.loads(json_str.strip())
            mapping_out = {}
            for r in results:
                idx = r["index"] - 1
                if 0 <= idx < len(questions):
                    cat = r["category"]
                    # If API suggests a new category, add it to taxonomy
                    if cat not in CLINICAL_TAXONOMY:
                        CLINICAL_TAXONOMY[cat] = f"AI-proposed category for: {questions[idx]['question_en'][:50]}"
                        print(f"[Mapping] New category proposed by API: {cat}")
                    mapping_out[questions[idx]["question_en"]] = cat

            print(f"[Mapping] API classified {len(mapping_out)} questions")
            return mapping_out

        except Exception as e:
            print(f"[Mapping] API attempt {attempt} failed: {e}")
            if attempt < config.LLM_MAX_RETRIES:
                import time
                time.sleep(config.LLM_RETRY_BASE_DELAY ** attempt)

    print(f"[Mapping] API fallback failed after {config.LLM_MAX_RETRIES} attempts")
    return {}


def build_mapping_table() -> pd.DataFrame:
    """Build the complete mapping table: question_id → clinical_category."""
    q = pd.read_csv(config.UNIQUE_QUESTIONS_FILE)
    df = load_raw_data(config.RAW_DATA_FILE)
    if df is None:
        sys.exit(1)

    print(f"\n[Mapping] Classifying {q['question_en'].nunique()} unique question texts...")

    # Classify each unique text
    deduped = q.drop_duplicates(subset="question_en").copy()
    text_to_category: dict[str, str] = {}
    text_to_answer_type: dict[str, str] = {}

    other_questions: list[dict] = []  # collect for batch API classification

    for _, row in deduped.iterrows():
        opts = row.get("answer_options_en", [])
        if isinstance(opts, str):
            try:
                opts = ast.literal_eval(opts)
            except:
                opts = []

        samples = row.get("sample_answer_values", [])
        if isinstance(samples, str):
            try:
                samples = ast.literal_eval(samples)
            except:
                samples = []

        cat, atype = classify_question(row["question_en"], opts, samples)
        text_to_category[row["question_en"]] = cat
        text_to_answer_type[row["question_en"]] = atype

        if cat == "OTHER":
            other_questions.append({
                "question_en": row["question_en"],
                "answer_options": opts,
                "sample_values": samples,
                "answer_type": atype,
            })

    # --- API fallback for unclassified questions ---
    if other_questions:
        api_results = _classify_with_api(other_questions)
        for text, cat in api_results.items():
            text_to_category[text] = cat
            print(f"  [API] {text[:60]}... → {cat}")

    # Expand to all 677 question_ids
    q["clinical_category"] = q["question_en"].map(text_to_category)
    q["answer_type"] = q["question_en"].map(text_to_answer_type)

    # Add duplicate group ID (questions with same text get same group)
    text_to_group = {text: i for i, text in enumerate(deduped["question_en"].unique(), 1)}
    q["duplicate_group_id"] = q["question_en"].map(text_to_group)

    # Canonical question_id = lowest ID per group
    canonical = q.groupby("duplicate_group_id")["question_id"].min().reset_index()
    canonical.columns = ["duplicate_group_id", "canonical_question_id"]
    q = q.merge(canonical, on="duplicate_group_id", how="left")

    # Select final columns
    mapping = q[[
        "question_id", "question_en", "question_de",
        "clinical_category", "answer_type",
        "duplicate_group_id", "canonical_question_id",
        "duplicate_count", "row_count",
    ]].copy()

    # Save
    mapping.to_csv(config.MAPPING_TABLE, index=False, encoding="utf-8")
    print(f"[Mapping] Saved {len(mapping)} entries to {config.MAPPING_TABLE}")

    # Print summary
    print(f"\n[Mapping] CATEGORY DISTRIBUTION:")
    cat_stats = mapping.drop_duplicates(subset="question_en").groupby("clinical_category").agg(
        unique_texts=("question_en", "nunique"),
        total_ids=("question_id", "count"),
    ).sort_values("total_ids", ascending=False)
    for cat, row in cat_stats.iterrows():
        # Count data rows covered
        data_rows = df[df["question_en"].isin(
            mapping[mapping["clinical_category"] == cat]["question_en"].unique()
        )].shape[0]
        print(f"  {cat:30s} {row['unique_texts']:>3} texts  {row['total_ids']:>4} IDs  {data_rows:>6,} rows")

    uncategorized = mapping[mapping["clinical_category"] == "OTHER"]
    if len(uncategorized) > 0:
        print(f"\n[WARNING] {len(uncategorized)} question IDs classified as OTHER:")
        for _, row in uncategorized.drop_duplicates(subset="question_en").iterrows():
            print(f"  [{row['question_id']}] {row['question_en'][:80]}...")

    return mapping


def generate_review_document(mapping: pd.DataFrame) -> str:
    """Generate a human-readable review document grouped by category.

    This is what the team reviews to validate the mapping.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("  MAPPING REVIEW — VALIDATE BEFORE PROCEEDING")
    lines.append("  Check each category: are all questions correctly assigned?")
    lines.append("=" * 70)

    deduped = mapping.drop_duplicates(subset="question_en")

    for cat in sorted(CLINICAL_TAXONOMY.keys()):
        cat_qs = deduped[deduped["clinical_category"] == cat]
        definition = CLINICAL_TAXONOMY.get(cat, "")
        lines.append(f"\n{'─' * 70}")
        lines.append(f"  {cat} ({len(cat_qs)} questions, {cat_qs['duplicate_count'].sum()} total IDs)")
        lines.append(f"  Definition: {definition}")
        lines.append(f"{'─' * 70}")

        for _, row in cat_qs.iterrows():
            text = row["question_en"][:120]
            atype = row["answer_type"]
            n_ids = row["duplicate_count"]
            lines.append(f"\n  [{atype:20s}] [{n_ids:>2} IDs] {text}...")

    # OTHER
    other_qs = deduped[deduped["clinical_category"] == "OTHER"]
    if len(other_qs) > 0:
        lines.append(f"\n{'─' * 70}")
        lines.append(f"  OTHER / UNCLASSIFIED ({len(other_qs)} questions)")
        lines.append(f"{'─' * 70}")
        for _, row in other_qs.iterrows():
            lines.append(f"\n  [{row['answer_type']:20s}] [{row['duplicate_count']:>2} IDs] {row['question_en'][:120]}...")

    lines.append(f"\n{'=' * 70}")
    lines.append("  END OF REVIEW")
    lines.append(f"{'=' * 70}")

    return "\n".join(lines)


if __name__ == "__main__":
    mapping = build_mapping_table()
    review = generate_review_document(mapping)
    print(review)

    review_path = config.OUTPUT_DIR / "mapping_review.txt"
    review_path.write_text(review, encoding="utf-8")
    print(f"\n[Mapping] Review document saved to {review_path}")
