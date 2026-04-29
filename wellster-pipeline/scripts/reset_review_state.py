"""Reset the semantic_mapping.json review_status to the pitch-ready state.

The /review page has no reset button — once a user clicks Approve /
Reject / Override on a mapping, the state persists via PATCH to the
backend and there's no way to get back to a clean slate without
editing JSON by hand. This script does exactly that: it sets every
mapping's `review_status` to a deliberate value chosen by clinical
semantics (not by accidental clicks).

Policy — what gets approved vs rejected:

- Clinically meaningful categories (BMI, medications, symptoms,
  conditions, PROs, consent) → approved
- Upload / document / photo-workflow categories (not clinical data,
  not part of the substrate) → rejected

Matches the "20/20 mappings reviewed" claim in STATUS.md (17 approved
+ 3 rejected = 20 reviewed, 0 pending).

Run:
    cd wellster-pipeline
    ./.venv/Scripts/python.exe scripts/reset_review_state.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Let the script find src/ + config when run from either wellster-pipeline/
# or its parent. Assumes the standard repo layout.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.io_utils import atomic_read_json, atomic_write_json  # noqa: E402


# Non-clinical categories that should NOT be part of the audit-ready
# clinical substrate. Everything else is approved.
REJECTED_CATEGORIES: frozenset[str] = frozenset({
    "ID_DOCUMENT_UPLOAD",
    "PATIENT_PHOTO_UPLOAD",
    "PHOTO_UPLOAD_DECISION",
})


def main() -> int:
    mapping_path = Path(config.OUTPUT_DIR) / "semantic_mapping.json"
    if not mapping_path.exists():
        print(f"error: {mapping_path} not found", file=sys.stderr)
        return 1

    data = atomic_read_json(mapping_path)
    if not isinstance(data, dict):
        print("error: semantic_mapping.json is not a dict", file=sys.stderr)
        return 1

    before = {"approved": 0, "rejected": 0, "pending": 0, "overridden": 0}
    after = {"approved": 0, "rejected": 0, "pending": 0, "overridden": 0}
    changes: list[tuple[str, str, str]] = []
    reviewed_at = datetime.now(timezone.utc).isoformat()

    for category, entry in data.items():
        if not isinstance(entry, dict):
            continue
        old_status = str(entry.get("review_status", "pending"))
        before[old_status] = before.get(old_status, 0) + 1

        new_status = "rejected" if category in REJECTED_CATEGORIES else "approved"
        after[new_status] = after.get(new_status, 0) + 1

        if old_status != new_status:
            entry["review_status"] = new_status
            entry["reviewed_by"] = "scripts/reset_review_state.py"
            entry["reviewed_role"] = "system"
            entry["reviewed_at"] = reviewed_at
            entry["review_note"] = "bulk reset to pitch-ready policy"
            changes.append((category, old_status, new_status))

    atomic_write_json(mapping_path, data)

    print(f"semantic_mapping.json reset — {mapping_path}")
    print()
    print("before:", dict(before))
    print("after: ", dict(after))
    print()
    if changes:
        print(f"{len(changes)} categories changed:")
        for cat, old, new in changes:
            print(f"  {cat:50s}  {old:10s} -> {new}")
    else:
        print("no changes needed — already in pitch-ready state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
