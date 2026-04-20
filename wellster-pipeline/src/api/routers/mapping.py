"""Mapping endpoints — review workflow for semantic_mapping.json.

Design choice: semantic_mapping.json is the single source of truth. The API
owns write access through the AppState lock so the Streamlit review UI and
any other client cannot race. AI regeneration (pipeline re-run) preserves
approved/overridden entries verbatim — the human decisions win.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import AppState, get_mapping_state
from src.api.models import MappingEntry, MappingUpdate
from src.semantic_mapping_ai import _validate_entry  # reuse the contract check

router = APIRouter(prefix="/mapping", tags=["mapping"])


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

        mapping[category] = merged
        state.write_mapping(mapping)

    return _to_model(category, merged)
