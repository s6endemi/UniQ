"""Normalization registry + unknown-variant queue endpoints.

Three surfaces:

- `GET /v1/normalization`              — full registry view + coverage
- `GET /v1/normalization/unknown`      — open / promoted / dismissed unknowns
- `PATCH /v1/normalization/{id}`       — clinician review action on a record
- `POST /v1/normalization/unknown/{id}/resolve`
                                       — promote or dismiss one unknown entry

Reviewer identity comes from the `X-Uniq-Reviewer` / `X-Uniq-Role`
headers when present (P0.6 wires this through every governance write).
Falls back to a demo author so existing tooling keeps working.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.deps import AppState, get_state
from src.api.models import (
    NormalizationCoverage,
    NormalizationListResponse,
    NormalizationRecordOut,
    NormalizationRecordPatch,
    UnknownEntryOut,
    UnknownQueueResponse,
    UnknownResolvePayload,
)
from src.normalization_queue import NormalizationQueue
from src.normalization_registry import NormalizationRegistry

router = APIRouter(tags=["normalization"])


DEMO_REVIEWER = "Dr. M. Hassan"
DEMO_ROLE = "Clinical Reviewer"


def _resolve_reviewer(
    reviewer_header: str | None,
    role_header: str | None,
) -> tuple[str, str]:
    """Pick reviewer identity: header if present, else demo defaults.

    The demo defaults are unmistakably labelled in `clinical_annotations.py`
    too — for the pilot, real auth replaces these. For now they make the
    audit trail readable without breaking when no header is sent.
    """
    return (
        reviewer_header.strip() if reviewer_header and reviewer_header.strip() else DEMO_REVIEWER,
        role_header.strip() if role_header and role_header.strip() else DEMO_ROLE,
    )


@router.get(
    "/v1/normalization",
    response_model=NormalizationListResponse,
)
def list_normalization_registry() -> NormalizationListResponse:
    """Full registry view, ordered by category then original_value.

    Returned shape:
    - `coverage` — counts per review status, the manifest's headline metric
    - `records`  — one entry per (category, original_value) — the per-label
                   reviewable surface that closes the §3.2 gap from the doc
    """
    registry = NormalizationRegistry.from_disk()
    sorted_records = sorted(
        registry.records,
        key=lambda r: (r.category, r.original_value.lower(), r.original_value),
    )
    return NormalizationListResponse(
        coverage=NormalizationCoverage(**registry.coverage_stats()),
        records=[
            NormalizationRecordOut(**r.to_dict())
            for r in sorted_records
        ],
    )


@router.get(
    "/v1/normalization/unknown",
    response_model=UnknownQueueResponse,
)
def list_unknown_queue() -> UnknownQueueResponse:
    """Unknown-variant queue: every value the pipeline saw but couldn't map.

    The queue is the primary clinician-review surface for new survey
    answer variants. Open entries are awaiting decision; promoted / dismissed
    entries are kept for audit but no longer block downstream consumers.
    """
    queue = NormalizationQueue.from_disk()
    sorted_entries = sorted(
        queue.entries,
        key=lambda e: (e.status != "open", -e.occurrence_count, e.last_seen),
    )
    return UnknownQueueResponse(
        stats=queue.stats(),
        entries=[
            UnknownEntryOut(**e.to_dict())
            for e in sorted_entries
        ],
    )


@router.patch(
    "/v1/normalization/{record_id}",
    response_model=NormalizationRecordOut,
)
def patch_normalization_record(
    record_id: str,
    payload: NormalizationRecordPatch,
    state: AppState = Depends(get_state),
    x_uniq_reviewer: str | None = Header(None),
    x_uniq_role: str | None = Header(None),
) -> NormalizationRecordOut:
    """Clinician review action on a single registry record.

    Used to: rename a canonical label, promote a `pending` record to
    `approved`, override a previous decision, or reject a record outright.
    Reviewer identity is captured for the audit trail.
    """
    reviewer, role = _resolve_reviewer(x_uniq_reviewer, x_uniq_role)
    registry = NormalizationRegistry.from_disk()
    updated = registry.update_review(
        record_id,
        canonical_label=payload.canonical_label,
        review_status=payload.review_status,
        reviewed_by=reviewer,
        reviewed_role=role,
        review_note=payload.review_note,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Normalization record {record_id!r} not found.",
        )
    registry.save()
    state.reload_artifacts()
    return NormalizationRecordOut(**updated.to_dict())


@router.post(
    "/v1/normalization/unknown/{entry_id}/resolve",
    response_model=UnknownEntryOut,
)
def resolve_unknown(
    entry_id: str,
    payload: UnknownResolvePayload,
    state: AppState = Depends(get_state),
    x_uniq_reviewer: str | None = Header(None),
    x_uniq_role: str | None = Header(None),
) -> UnknownEntryOut:
    """Promote or dismiss one queue entry.

    `promoted` requires `canonical_label` — the entry is moved into the
    registry as an approved record (the next pipeline run picks it up).
    `dismissed` records the clinician's decision to leave the value
    unmapped (typo / non-clinical / noise) so future occurrences are
    tagged but not re-queued.
    """
    reviewer, role = _resolve_reviewer(x_uniq_reviewer, x_uniq_role)

    queue = NormalizationQueue.from_disk()
    if payload.status == "promoted":
        if not payload.canonical_label:
            raise HTTPException(
                status_code=400,
                detail="canonical_label is required when promoting an unknown entry.",
            )
    entry = queue.resolve(
        entry_id,
        canonical_label=payload.canonical_label,
        status=payload.status,
        resolved_by=reviewer,
        resolved_role=role,
    )
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown queue entry {entry_id!r} not found.",
        )
    queue.save()

    # If promoted, also append the new record to the registry so the next
    # pipeline run uses it natively. Idempotent: if the same (category,
    # original_value) is already in the registry, the upsert just bumps
    # source_count.
    if payload.status == "promoted" and payload.canonical_label:
        registry = NormalizationRegistry.from_disk()
        registry.upsert(
            category=entry.category,
            original_value=entry.original_value,
            canonical_label=payload.canonical_label,
            review_status="approved",
            source_count_delta=entry.occurrence_count,
            reviewed_by=reviewer,
            reviewed_role=role,
        )
        registry.save()

    state.reload_artifacts()
    return UnknownEntryOut(**entry.to_dict())
