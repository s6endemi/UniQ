"""Purge one patient from materialized UniQ outputs.

Usage:
    python scripts/purge_patient.py 383871 --deleted-by "ops@wellster"

This removes the patient from output CSV/JSON artifacts and writes a
non-identifying tombstone so subsequent materializations keep the same
patient suppressed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.materialization_manifest import write_manifest  # noqa: E402
from src.retractions import purge_patient_from_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge a patient from UniQ outputs.")
    parser.add_argument("user_id", type=int, help="Wellster user_id to purge")
    parser.add_argument("--deleted-by", default="scripts/purge_patient.py")
    parser.add_argument("--reason", default="patient erasure request")
    args = parser.parse_args()

    result = purge_patient_from_outputs(
        args.user_id,
        deleted_by=args.deleted_by,
        reason=args.reason,
    )
    write_manifest(save=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
