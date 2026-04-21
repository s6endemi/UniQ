"""Chat endpoint — hybrid analyst agent (Phase 6).

Delegates to `src.chat_agent.run_chat_agent`. Deterministic recipes
short-circuit the pitch golden paths (cohort trajectory, patient FHIR
bundle, quality alerts); everything else goes through a Claude tool-use
loop that produces a table artifact.

Errors from the agent surface as honest 503/500s — we do not paper over
a missing API key or an unreachable Anthropic API with a fake "reply"
string, because the frontend shows a dedicated error surface that is
friendlier than pretending everything worked.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

import config
from src.api.deps import get_query, get_repo
from src.api.models import ChatRequest, ChatResponse
from src.chat_agent import run_chat_agent
from src.chat_agent_v2 import run_chat_agent_v2
from src.datastore import UnifiedDataRepository
from src.query_service import DuckDBQueryService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    query: DuckDBQueryService = Depends(get_query),
    repo: UnifiedDataRepository = Depends(get_repo),
) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="`message` must not be empty.")
    if config.get_agent_mode() == "v2":
        return run_chat_agent_v2(message, query=query, repo=repo)
    return run_chat_agent(message, query=query, repo=repo)
