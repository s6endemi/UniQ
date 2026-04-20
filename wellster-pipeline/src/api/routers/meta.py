"""Meta endpoints: /health, /schema, /categories."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import AppState, get_query, get_state
from src.api.models import (
    CategoriesResponse,
    ColumnInfo,
    HealthResponse,
    SchemaResponse,
)
from src.query_service import DuckDBQueryService

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(state: AppState = Depends(get_state)) -> HealthResponse:
    """Liveness + artifact-readiness signal."""
    if not state.ready or state.repo is None:
        return HealthResponse(
            status="degraded",
            artifacts_loaded=False,
            patients=0,
            categories=0,
            mapping_entries=0,
        )
    mapping = state.read_mapping()
    return HealthResponse(
        status="ok",
        artifacts_loaded=True,
        patients=state.repo.count_patients(),
        categories=len(state.repo.categories()),
        mapping_entries=sum(1 for k in mapping if not k.startswith("__")),
    )


@router.get("/schema", response_model=SchemaResponse)
def schema(query: DuckDBQueryService = Depends(get_query)) -> SchemaResponse:
    """Full table+column map. Chatbot feeds this into its prompt as context."""
    raw = query.schema()
    return SchemaResponse(
        tables={
            table: [ColumnInfo(column=c["column"], type=c["type"]) for c in cols]
            for table, cols in raw.items()
        }
    )


@router.get("/categories", response_model=CategoriesResponse)
def categories(
    query: DuckDBQueryService = Depends(get_query),
) -> CategoriesResponse:
    """Distinct clinical_category values discovered by the AI classifier."""
    cats = query.list_categories()
    return CategoriesResponse(categories=cats, count=len(cats))
