"""Chat endpoint — stub for Phase 6.

The chatbot will introspect the schema, generate read-only SQL against the
unified data, execute through `query_service`, and return a text reply +
chart spec. For now this router only advertises the endpoint shape so the
UI scaffolding (Phase 5) can wire up against it.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.models import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        reply=(
            "Chat not wired up yet — this endpoint is stubbed. "
            "Phase 6 will implement the SQL-agent backend "
            f"(message received: {request.message!r})."
        ),
        sql=None,
        rows=None,
        chart_spec=None,
        truncated=False,
    )
