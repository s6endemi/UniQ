"""Phase 1 ad-hoc test — validates the incremental-mode guarantee.

The pipeline's most important invariant: once a human has validated the
`taxonomy.json`, a re-run on the same (or overlapping) raw data must NOT
change the validated taxonomy or the mapping table. Otherwise the Concept-
Schicht (Phase 4) and every downstream consumer rebuilds against a new
vocabulary every run.

What this test does:
    1. Snapshot hashes of output/{taxonomy.json, mapping_table.csv,
       answer_normalization.json} from the previous run.
    2. Run engine.run_pipeline() on the same raw file.
    3. Assert the three files are byte-identical before and after.

Prerequisites:
    - A previous successful pipeline run (output/ populated).
    - data/raw/treatment_answer.csv present.

Skips gracefully if either is missing. Will be replaced by proper pytest
fixtures in Phase 5 (Packaging + formal test setup).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.engine import run_pipeline


GUARDED_ARTIFACTS = [
    config.OUTPUT_DIR / "taxonomy.json",
    config.MAPPING_TABLE,
    config.OUTPUT_DIR / "answer_normalization.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot() -> dict[str, str]:
    return {p.name: _sha256(p) for p in GUARDED_ARTIFACTS if p.exists()}


def main() -> int:
    # Preflight
    if not config.RAW_DATA_FILE.exists():
        print(f"SKIP: raw data file missing: {config.RAW_DATA_FILE}")
        return 0

    missing = [p for p in GUARDED_ARTIFACTS if not p.exists()]
    if missing:
        print("SKIP: previous pipeline run required (missing artifacts):")
        for p in missing:
            print(f"  - {p}")
        print("Run: PYTHONIOENCODING=utf-8 python pipeline.py")
        return 0

    print("[1/3] Snapshotting guarded artifacts...")
    before = _snapshot()
    for name, digest in before.items():
        print(f"  {name}: {digest[:16]}")

    print("\n[2/3] Running engine.run_pipeline() for second time...")
    artifacts = run_pipeline(on_progress=lambda m: print(f"  -> {m}"))
    print(f"  produced {len(artifacts.patients):,} patients, "
          f"{len(artifacts.category_names())} categories")

    print("\n[3/3] Verifying artifacts were not overwritten...")
    after = _snapshot()
    failures: list[str] = []
    for name, before_hash in before.items():
        after_hash = after.get(name)
        if after_hash != before_hash:
            failures.append(
                f"  [X] {name} CHANGED\n"
                f"      before: {before_hash}\n"
                f"      after:  {after_hash}"
            )
        else:
            print(f"  [OK] {name} unchanged ({before_hash[:16]})")

    if failures:
        print("\n[FAIL] Incremental-mode guarantee violated:")
        for f in failures:
            print(f)
        return 1

    print("\n[PASS] All guarded artifacts preserved across re-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
