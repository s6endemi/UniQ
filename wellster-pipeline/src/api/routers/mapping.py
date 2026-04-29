"""Mapping endpoints — review workflow for semantic_mapping.json.

Design choice: semantic_mapping.json is the single source of truth. The API
owns write access through the AppState lock so the Streamlit review UI and
any other client cannot race. AI regeneration (pipeline re-run) preserves
approved/overridden entries verbatim — the human decisions win.

Reviewer identity (P0.6): every governance write attaches the reviewing
clinician via the `X-Uniq-Reviewer` / `X-Uniq-Role` headers when present.
Falls back to a demo author for the showcase. The audit trail records
`reviewed_by`, `reviewed_at`, and the AI's pre-existing `reasoning` so a
clinical reviewer can always reconstruct who decided what when.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from src.api.deps import AppState, get_mapping_state
from src.api.models import MappingEntry, MappingUpdate
from src.semantic_mapping_ai import _validate_entry  # reuse the contract check

router = APIRouter(prefix="/mapping", tags=["mapping"])


_DEMO_REVIEWER = "Dr. M. Hassan"
_DEMO_ROLE = "Clinical Reviewer"


def _resolve_reviewer(
    reviewer_header: str | None,
    role_header: str | None,
) -> tuple[str, str]:
    return (
        reviewer_header.strip() if reviewer_header and reviewer_header.strip() else _DEMO_REVIEWER,
        role_header.strip() if role_header and role_header.strip() else _DEMO_ROLE,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Categories that should NOT be part of the audit-ready clinical substrate
# — they are operational uploads / documents, not clinical data. Everything
# else is flipped to approved on reset.
_RESET_REJECT_CATEGORIES: frozenset[str] = frozenset({
    "ID_DOCUMENT_UPLOAD",
    "PATIENT_PHOTO_UPLOAD",
    "PHOTO_UPLOAD_DECISION",
})


def _clear_runtime_caches(state: AppState) -> None:
    """Make mapping-review writes visible to artifacts and SQL immediately."""
    from src import artifact_builders

    if hasattr(artifact_builders._load_semantic_mapping, "_cache"):
        delattr(artifact_builders._load_semantic_mapping, "_cache")
    state.reload_artifacts()


class ResetResponse(BaseModel):
    approved: int
    rejected: int
    pending: int
    overridden: int
    changed: int


def _to_model(category: str, raw: dict) -> MappingEntry:
    """Convert a raw mapping dict to the typed MappingEntry response."""
    return MappingEntry(
        category=category,
        display_label=raw.get("display_label", category),
        standard_concept=raw.get("standard_concept"),
        fhir_resource_type=raw.get("fhir_resource_type", "QuestionnaireResponse"),
        fhir_category=raw.get("fhir_category"),
        codes=raw.get("codes", []),
        confidence=raw.get("confidence", "low"),
        review_status=raw.get("review_status", "pending"),
        reasoning=raw.get("reasoning"),
        validation_errors=raw.get("validation_errors"),
        reviewed_by=raw.get("reviewed_by"),
        reviewed_role=raw.get("reviewed_role"),
        reviewed_at=raw.get("reviewed_at"),
        review_note=raw.get("review_note"),
    )


@router.get("", response_model=list[MappingEntry])
def list_mapping(state: AppState = Depends(get_mapping_state)) -> list[MappingEntry]:
    """Return every active mapping entry (archived entries are hidden)."""
    mapping = state.read_mapping()
    return [
        _to_model(cat, entry)
        for cat, entry in mapping.items()
        if not cat.startswith("__") and isinstance(entry, dict)
    ]


@router.get("/{category}", response_model=MappingEntry)
def get_mapping(
    category: str,
    state: AppState = Depends(get_mapping_state),
) -> MappingEntry:
    mapping = state.read_mapping()
    entry = mapping.get(category)
    if not entry or not isinstance(entry, dict):
        raise HTTPException(status_code=404, detail=f"No mapping for {category!r}")
    return _to_model(category, entry)


@router.patch("/{category}", response_model=MappingEntry)
def update_mapping(
    category: str,
    update: MappingUpdate,
    state: AppState = Depends(get_mapping_state),
    x_uniq_reviewer: str | None = Header(None),
    x_uniq_role: str | None = Header(None),
) -> MappingEntry:
    """Apply a partial update + re-validate + persist atomically.

    Behaviour:
        - Any field-level edit without explicit `review_status` defaults to
          `overridden` (the reviewer changed something on purpose).
        - Explicit `review_status=approved` means the reviewer accepted the
          AI suggestion as-is — even if other fields were also sent.
        - `review_status=rejected` marks the entry as not safe to use; the
          fields are still written for audit.
        - Validation failure returns 422 with the contract errors.
    """
    with state.mapping_lock():
        mapping = state.read_mapping()
        if category not in mapping or category.startswith("__"):
            raise HTTPException(status_code=404, detail=f"No mapping for {category!r}")

        existing = dict(mapping[category])

        update_fields = update.model_dump(exclude_unset=True)
        incoming_status = update_fields.pop("review_status", None)

        # Structured fields → serialize CodeEntry sub-models to plain dicts
        if "codes" in update_fields and update_fields["codes"] is not None:
            update_fields["codes"] = [
                c if isinstance(c, dict) else c.model_dump()
                for c in update_fields["codes"]
            ]

        merged = {**existing, **{k: v for k, v in update_fields.items() if v is not None}}

        if incoming_status is not None:
            merged["review_status"] = incoming_status
        elif update_fields:
            # Reviewer edited fields without explicit status → overridden
            merged["review_status"] = "overridden"
        else:
            merged["review_status"] = existing.get("review_status", "pending")

        errors = _validate_entry(category, merged)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"errors": errors, "submitted": merged},
            )

        # Attach reviewer identity for the audit trail. Always set when
        # the entry is being modified (the alternative — leaving stale
        # reviewer attribution on overwritten content — would corrupt
        # the audit log).
        reviewer, role = _resolve_reviewer(x_uniq_reviewer, x_uniq_role)
        merged["reviewed_by"] = reviewer
        merged["reviewed_role"] = role
        merged["reviewed_at"] = _now_iso()

        mapping[category] = merged
        state.write_mapping(mapping)

    _clear_runtime_caches(state)
    return _to_model(category, merged)


@router.post("/reset", response_model=ResetResponse)
def reset_mapping(
    state: AppState = Depends(get_mapping_state),
    x_uniq_reviewer: str | None = Header(None),
    x_uniq_role: str | None = Header(None),
) -> ResetResponse:
    """Reset every mapping to its pitch-ready review_status.

    Policy:
        - Non-clinical categories (uploads, photos, workflow decisions)
          → rejected (they are intentionally not in the substrate).
        - Everything else → approved.

    This is a developer/demo convenience: the /review UI has no reset
    control, and accumulated click-through state from testing can make
    the substrate read inconsistently across the Analyst, patient_record
    artifacts, and lineage ribbons. After calling this, the
    semantic_mapping cache in `src.artifact_builders` is cleared so the
    next artifact build picks up the new state without a server restart.
    """
    reviewer, role = _resolve_reviewer(x_uniq_reviewer, x_uniq_role)
    when = _now_iso()

    with state.mapping_lock():
        mapping = state.read_mapping()
        changed = 0
        counts = {"approved": 0, "rejected": 0, "pending": 0, "overridden": 0}

        for category, entry in mapping.items():
            if category.startswith("__") or not isinstance(entry, dict):
                continue
            new_status = (
                "rejected"
                if category in _RESET_REJECT_CATEGORIES
                else "approved"
            )
            old_status = entry.get("review_status", "pending")
            if old_status != new_status:
                entry["review_status"] = new_status
                # Attribution attaches only on actual change so we don't
                # blanket-overwrite reviewer attribution from genuine
                # per-mapping clinician decisions with the bulk reset
                # actor every time the script runs.
                entry["reviewed_by"] = reviewer
                entry["reviewed_role"] = role
                entry["reviewed_at"] = when
                entry["review_note"] = "bulk reset to pitch-ready policy"
                changed += 1
            counts[new_status] = counts.get(new_status, 0) + 1

        state.write_mapping(mapping)

    _clear_runtime_caches(state)

    return ResetResponse(**counts, changed=changed)
