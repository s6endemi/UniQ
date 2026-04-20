"""UniQ Pipeline — CLI entry point.

Thin wrapper around `src.engine.run_pipeline`. All orchestration lives in the
engine module so the Streamlit demo and future consumers (FastAPI, chatbot)
share the same execution path.

Usage:
    python pipeline.py                  # run end-to-end
    python pipeline.py --raw path/to.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from src.engine import run_pipeline


def _print_banner() -> None:
    print("=" * 70)
    print("  UniQ Unified Data Pipeline")
    print("=" * 70)


def _cli_progress(msg: str) -> None:
    print(f"\n[>] {msg}...")


def main() -> int:
    parser = argparse.ArgumentParser(description="UniQ unified data pipeline")
    parser.add_argument(
        "--raw",
        type=Path,
        default=None,
        help=f"Path to raw CSV/TSV (default: {config.RAW_DATA_FILE})",
    )
    args = parser.parse_args()

    _print_banner()
    try:
        artifacts = run_pipeline(raw_path=args.raw, on_progress=_cli_progress)
    except FileNotFoundError as e:
        print(f"\n[ABORT] {e}")
        return 1

    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE")
    print(f"  Patients:    {len(artifacts.patients):>6,}")
    print(f"  Treatments:  {len(artifacts.episodes):>6,}")
    print(f"  BMI rows:    {len(artifacts.bmi_timeline):>6,}")
    print(f"  Quality:     {len(artifacts.quality_report):>6,} alerts")
    print(f"  Categories:  {len(artifacts.category_names()):>6,}")
    print(f"\n  Output files in {artifacts.output_dir}:")
    for f in sorted(artifacts.output_dir.glob("*.csv")):
        print(f"    {f.name}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
