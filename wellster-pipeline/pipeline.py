"""
Wellster Unified Data Pipeline — Orchestrator

Runs the full pipeline end-to-end:
  load → mapping → normalize → unify → quality

Incremental logic: if mapping_table.csv exists, skips mapping.
If new question_ids are found, classifies only the new ones via API.

Usage:
    python pipeline.py                  # run full pipeline
    python pipeline.py --step load      # run a single step
    python pipeline.py --step normalize
    python pipeline.py --step unify
    python pipeline.py --step quality
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from src.load import run_load
from src.classify_ai import run_classification
from src.normalize import run_normalize
from src.normalize_answers_ai import normalize_answers_ai
from src.unify import run_unify
from src.quality import run_quality


def main() -> None:
    """Run the Wellster data pipeline."""
    parser = argparse.ArgumentParser(description="Wellster Unified Data Pipeline")
    parser.add_argument(
        "--step",
        choices=["load", "classify", "normalize", "unify", "quality", "all"],
        default="all",
        help="Which pipeline step to run (default: all)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  WELLSTER UNIFIED DATA PIPELINE")
    print("  GoLighter — Obesity Treatment Data")
    print("=" * 70)

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    step = args.step

    # --- Step 1-2: Load & Inspect ---
    df = None
    if step in ("all", "load"):
        df = run_load()
        if df is None:
            print("\n[ABORT] Data loading failed.")
            sys.exit(1)
        if step == "load":
            return

    # --- Step 3-4: AI Classification ---
    if step in ("all", "classify"):
        mapping = run_classification(df)
        if step == "classify":
            return

    # --- Step 5: Normalize (format) ---
    if step in ("all", "normalize"):
        survey = run_normalize(df)

    # --- Step 5b: Normalize (answers via AI) ---
    if step in ("all", "normalize"):
        survey, _ = normalize_answers_ai(survey)
        survey.to_csv(config.SURVEY_UNIFIED_TABLE, index=False, encoding="utf-8")
        if step == "normalize":
            return

    # --- Step 6: Unify ---
    if step in ("all", "unify"):
        if step == "unify":
            survey = None  # will load from file
        patients, episodes, bmi_df, med_hist = run_unify(survey if step == "all" else None)
        if step == "unify":
            return

    # --- Step 7: Quality ---
    if step in ("all", "quality"):
        if step == "quality":
            patients = episodes = bmi_df = med_hist = None  # will load from files
        run_quality(patients, bmi_df, episodes, med_hist)
        if step == "quality":
            return

    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE")
    print("  Output files:")
    for f in sorted(config.OUTPUT_DIR.glob("*.csv")):
        print(f"    {f.name}")
    print("=" * 70)


if __name__ == "__main__":
    main()
