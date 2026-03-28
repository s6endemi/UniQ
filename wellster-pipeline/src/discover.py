"""
Step 3 — Discovery: Extract Unique Questions & LLM-Powered Clustering

Clinical purpose: Survey questions change IDs over time (reworded, new versions, different
survey flows). A single clinical concept like "Do you have pre-existing conditions?" can
appear under 37 different question_ids. This step extracts all unique questions and uses
an LLM to propose clinical categories and identify semantic duplicates — turning 677
fragmented IDs into ~15-20 meaningful clinical groups.

Step 3a: Extract unique questions (deterministic, no LLM)
Step 3b: LLM discovery clustering (requires API key)
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.load import load_raw_data


# ---------------------------------------------------------------------------
# 3a — Extract unique questions
# ---------------------------------------------------------------------------

def extract_unique_questions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract all unique questions with their answer options.

    The answer options are critical context — they tell us what clinical concept a
    question actually captures. E.g. "Do you suffer from conditions?" is generic,
    but its answers (Dyslipidaemia, Sleep Apnoea, Prediabetes) reveal it's a
    comorbidity screening for GLP-1 eligibility.

    Returns:
        questions: one row per unique question_id, with answer options included
        answer_mapping: one row per unique (question_id, answer_id) pair
    """
    print(f"\n[Step 3a] Extracting unique questions + answer options from {len(df):,} rows...")

    # --- Question-level aggregation ---
    questions = (
        df.groupby("question_id")
        .agg(
            question_de=("question_de", "first"),
            question_en=("question_en", "first"),
            row_count=("question_id", "size"),
            survey_ids=("survey_id", lambda x: sorted(x.unique().tolist())),
            sample_answer_values=("answer_value", lambda x: list(x.dropna().unique()[:5])),
        )
        .reset_index()
        .sort_values("question_id")
    )

    # --- Collect answer options per question ---
    # answer_id can be null (free-text/JSON inputs like BMI), so we handle both
    answer_opts = (
        df.dropna(subset=["answer_id"])
        .groupby("question_id")
        .agg(
            answer_options_en=("answer_en", lambda x: sorted(x.dropna().unique().tolist())),
            answer_options_de=("answer_de", lambda x: sorted(x.dropna().unique().tolist())),
            n_answer_options=("answer_id", "nunique"),
        )
        .reset_index()
    )
    questions = questions.merge(answer_opts, on="question_id", how="left")
    questions["n_answer_options"] = questions["n_answer_options"].fillna(0).astype(int)
    questions["answer_options_en"] = questions["answer_options_en"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    questions["answer_options_de"] = questions["answer_options_de"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    print(f"[Step 3a] Found {len(questions)} unique question IDs from {len(df):,} rows")

    # --- Full answer mapping table (question_id + answer_id + texts) ---
    answer_mapping = (
        df.dropna(subset=["answer_id"])
        .groupby(["question_id", "answer_id"])
        .agg(
            answer_de=("answer_de", "first"),
            answer_en=("answer_en", "first"),
            row_count=("answer_id", "size"),
        )
        .reset_index()
        .sort_values(["question_id", "answer_id"])
    )
    answer_mapping["answer_id"] = answer_mapping["answer_id"].astype(int)

    # --- Identify semantic duplicates — same English text, different IDs ---
    text_groups = questions.groupby("question_en")["question_id"].apply(list).reset_index()
    text_groups.columns = ["question_en", "all_ids_with_same_text"]
    text_groups["id_count"] = text_groups["all_ids_with_same_text"].apply(len)
    duplicates = text_groups[text_groups["id_count"] > 1].sort_values("id_count", ascending=False)

    text_to_group = {}
    for _, row in text_groups.iterrows():
        for qid in row["all_ids_with_same_text"]:
            text_to_group[qid] = len(row["all_ids_with_same_text"])
    questions["duplicate_count"] = questions["question_id"].map(text_to_group)

    # --- Print summary ---
    unique_texts = questions["question_en"].nunique()
    print(f"[Step 3a] Unique question texts: {unique_texts} (from {len(questions)} IDs)")
    print(f"[Step 3a] Questions with duplicate IDs: {len(duplicates)} texts spanning {duplicates['id_count'].sum()} IDs")
    print(f"[Step 3a] Unique answer_id entries: {len(answer_mapping)}")

    with_opts = (questions["n_answer_options"] > 0).sum()
    without_opts = (questions["n_answer_options"] == 0).sum()
    print(f"[Step 3a] Questions with predefined answer options: {with_opts}")
    print(f"[Step 3a] Questions with free-form input (no answer_id): {without_opts}")

    print(f"\n[Step 3a] Top 10 most-duplicated questions:")
    for _, row in duplicates.head(10).iterrows():
        print(f"  [{row['id_count']:>2} IDs] {row['question_en'][:85]}...")

    # --- Save ---
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    questions.to_csv(config.UNIQUE_QUESTIONS_FILE, index=False, encoding="utf-8")
    print(f"\n[Step 3a] Saved {len(questions)} unique questions to {config.UNIQUE_QUESTIONS_FILE}")

    answer_map_path = config.OUTPUT_DIR / "answer_mapping_raw.csv"
    answer_mapping.to_csv(answer_map_path, index=False, encoding="utf-8")
    print(f"[Step 3a] Saved {len(answer_mapping)} answer mappings to {answer_map_path}")

    return questions, answer_mapping


# ---------------------------------------------------------------------------
# 3b — LLM Discovery Clustering (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

DISCOVERY_PROMPT = """You are a medical data engineer analyzing questionnaire data from a digital obesity
telehealth platform (GoLighter by Wellster). Patients use GLP-1/GIP medications
(Wegovy/semaglutide, Mounjaro/tirzepatide, Saxenda/liraglutide) for weight management.

Below are unique medical questionnaire questions. Each has:
- question_id and English text
- The predefined answer options (if any) — these reveal the clinical intent

YOUR TASKS:
1. Identify natural clinical groupings — questions that ask about the same clinical concept
   even if worded differently or having different IDs
2. Propose a taxonomy of clinical categories with short definitions
3. Flag questions that are duplicates (same intent, different wording/ID)
4. Note questions that cover multiple concepts

Return JSON:
{
  "proposed_categories": [
    {"name": "BMI_MEASUREMENT", "definition": "Questions collecting height, weight, or BMI data"},
    ...
  ],
  "question_assignments": [
    {"question_id": 37213, "proposed_category": "PHOTO_UPLOAD_ID", "reasoning": "Asks for ID document photo", "duplicate_of": null},
    {"question_id": 108865, "proposed_category": "PHOTO_UPLOAD_BODY", "reasoning": "Asks for full body photo", "duplicate_of": 37213},
    ...
  ],
  "notes": "any observations about the data structure"
}

QUESTIONS:
"""


def discover_with_llm(questions: pd.DataFrame) -> dict | None:
    """Send unique questions to Claude in batches for clinical clustering.

    Returns aggregated discovery results or None if API key is missing.
    """
    if not config.ANTHROPIC_API_KEY:
        print("\n[Step 3b] SKIPPED — ANTHROPIC_API_KEY not set.")
        print("         Set it with: export ANTHROPIC_API_KEY='sk-ant-...'")
        print("         Then re-run: python pipeline.py --step discover")
        return None

    try:
        import anthropic
    except ImportError:
        print("[Step 3b] SKIPPED — anthropic package not installed. Run: pip install anthropic")
        return None

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Deduplicate by question text — send each unique text only once, with one representative ID
    deduped = questions.drop_duplicates(subset="question_en").copy()
    print(f"\n[Step 3b] Sending {len(deduped)} unique question texts to LLM (batches of {config.LLM_BATCH_SIZE})...")

    all_categories: list[dict] = []
    all_assignments: list[dict] = []
    all_notes: list[str] = []

    batch_size = config.LLM_BATCH_SIZE
    batches = [deduped.iloc[i:i + batch_size] for i in range(0, len(deduped), batch_size)]

    for i, batch in enumerate(batches):
        # Format questions for the prompt — include answer options for clinical context
        q_lines = []
        for _, row in batch.iterrows():
            line = f"- question_id: {row['question_id']} | text: {row['question_en']}"
            opts = row.get("answer_options_en", [])
            if isinstance(opts, list) and len(opts) > 0:
                line += f"\n  answer options: {opts}"
            else:
                samples = row.get("sample_answer_values", [])
                if isinstance(samples, list) and len(samples) > 0:
                    line += f"\n  sample values: {[str(s)[:80] for s in samples[:3]]}"
            q_lines.append(line)
        prompt_body = DISCOVERY_PROMPT + "\n".join(q_lines)

        # Call LLM with retry logic
        result = _call_llm_with_retry(client, prompt_body, batch_num=i + 1, total=len(batches))
        if result is None:
            continue

        if "proposed_categories" in result:
            all_categories.extend(result["proposed_categories"])
        if "question_assignments" in result:
            all_assignments.extend(result["question_assignments"])
        if "notes" in result:
            all_notes.append(result["notes"])

    # Deduplicate proposed categories across batches
    seen_cats: dict[str, str] = {}
    for cat in all_categories:
        name = cat.get("name", "")
        if name not in seen_cats:
            seen_cats[name] = cat.get("definition", "")
    unique_categories = [{"name": k, "definition": v} for k, v in seen_cats.items()]

    # Now expand assignments to cover ALL question_ids (not just the deduped representative)
    # Map each question_en text to its assignment
    text_to_assignment: dict[str, dict] = {}
    for a in all_assignments:
        qid = a.get("question_id")
        matching = deduped[deduped["question_id"] == qid]
        if len(matching) > 0:
            text = matching.iloc[0]["question_en"]
            text_to_assignment[text] = a

    expanded_assignments: list[dict] = []
    for _, row in questions.iterrows():
        base = text_to_assignment.get(row["question_en"])
        if base:
            expanded_assignments.append({
                "question_id": row["question_id"],
                "proposed_category": base.get("proposed_category", "OTHER"),
                "reasoning": base.get("reasoning", ""),
                "duplicate_of": base.get("duplicate_of"),
            })
        else:
            expanded_assignments.append({
                "question_id": row["question_id"],
                "proposed_category": "UNCLASSIFIED",
                "reasoning": "Not processed by LLM",
                "duplicate_of": None,
            })

    discovery = {
        "proposed_categories": unique_categories,
        "question_assignments": expanded_assignments,
        "notes": " | ".join(all_notes),
        "stats": {
            "total_question_ids": len(questions),
            "unique_texts_sent": len(deduped),
            "categories_proposed": len(unique_categories),
            "batches_processed": len(batches),
        },
    }

    # Save results
    out_path = config.DISCOVERY_RESULTS_FILE
    out_path.write_text(json.dumps(discovery, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[Step 3b] Discovery complete!")
    print(f"  Categories proposed: {len(unique_categories)}")
    print(f"  Questions assigned:  {len(expanded_assignments)}")
    print(f"  Saved to: {out_path}")

    # Print proposed taxonomy
    print(f"\n[Step 3b] PROPOSED TAXONOMY:")
    for cat in sorted(unique_categories, key=lambda c: c["name"]):
        print(f"  {cat['name']:35s} — {cat['definition']}")

    return discovery


def _call_llm_with_retry(client: "anthropic.Anthropic", prompt: str, batch_num: int, total: int) -> dict | None:
    """Call Claude API with retry logic and JSON parsing."""
    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        try:
            print(f"  [Batch {batch_num}/{total}] Sending to {config.LLM_MODEL} (attempt {attempt})...", end=" ")
            response = client.messages.create(
                model=config.LLM_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            print(f"OK ({tokens_in} in / {tokens_out} out)")

            # Extract JSON from response (may be wrapped in ```json ... ```)
            json_str = raw
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            return json.loads(json_str.strip())

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            if attempt < config.LLM_MAX_RETRIES:
                delay = config.LLM_RETRY_BASE_DELAY ** attempt
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)
        except Exception as e:
            print(f"API error: {e}")
            if attempt < config.LLM_MAX_RETRIES:
                delay = config.LLM_RETRY_BASE_DELAY ** attempt
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)

    print(f"  [Batch {batch_num}] FAILED after {config.LLM_MAX_RETRIES} attempts")
    return None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_discover(df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict | None]:
    """Run the full discovery step (3a + 3b)."""
    if df is None:
        df = load_raw_data(config.RAW_DATA_FILE)
        if df is None:
            sys.exit(1)

    # 3a: Extract unique questions + answer mappings (always runs)
    questions, answer_mapping = extract_unique_questions(df)

    # 3b: LLM clustering (only if API key is set)
    discovery = discover_with_llm(questions)

    return questions, answer_mapping, discovery


if __name__ == "__main__":
    run_discover()
