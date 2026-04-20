"""UniQ FastAPI application entry point.

Run locally:
    uvicorn src.api.main:app --reload --port 8000

Design summary:
    - Endpoints are generic (schema, categories, mapping, patients, export,
      chat). No domain-specific endpoints like `/bmi_trend` — customers
      adapt via the returned schema + mapping.
    - No public `/query` endpoint. SQL access lives behind the `/chat`
      agent which uses `query_service` as an internal Python dependency.
    - Review writes to semantic_mapping.json go through a lock; AI
      pipeline re-runs preserve approved/overridden entries.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.deps import state
from src.api.routers import chat, mapping, meta, patients


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.try_load()
    yield
    state.close()


app = FastAPI(
    title="UniQ API",
    version="0.1.0",
    summary="AI-powered healthcare data unification — platform API",
    lifespan=lifespan,
)


app.include_router(meta.router)
app.include_router(mapping.router)
app.include_router(patients.router)
app.include_router(chat.router)
