# UniQ Wellster Pipeline Architecture

This document maps the current pilot architecture. It is meant for technical
review: what is live, where trust boundaries sit, and which files own which
runtime surface.

## System Shape

UniQ is a Clinical Truth Layer between Wellster survey exports and downstream
consumers. The pipeline turns column-coupled survey CSV/TSV data into a typed,
auditable substrate:

1. Load raw Wellster survey rows.
2. Discover and classify question semantics.
3. Normalize answer variants through a reviewable registry.
4. Apply clinician-reviewed semantic mappings.
5. Materialize typed tables and a validated clinical view.
6. Serve API, FHIR export, and analyst-chat consumers from the validated layer.

The current codebase is intentionally a single Python package under `src/`.
The split is modular by responsibility, not yet by sub-package. A package
refactor into `pipeline/`, `substrate/`, `governance/`, and `api/` would be
mechanical, but it is not needed before the Wellster pilot.

## Module Map

| Area | Files | Responsibility |
| --- | --- | --- |
| Pipeline orchestration | `pipeline.py`, `src/engine.py` | One end-to-end materialization run. |
| Input loading | `src/load.py`, `src/io_utils.py` | Read raw Wellster exports and safe JSON writes. |
| Discovery and mapping | `src/discover.py`, `src/classify_ai.py`, `src/semantic_mapping_ai.py`, `src/unify.py` | Question discovery, category classification, semantic mapping application. |
| Answer governance | `src/normalization_registry.py`, `src/normalization_queue.py`, `src/normalize_answers_ai.py`, `src/normalize.py` | Record-backed answer normalization, unknown queue, review state. |
| Validated substrate | `src/datastore.py`, `src/query_service.py` | Typed repository, `survey_validated`, read-only SQL guardrails. |
| Artifacts and API | `src/artifact_builders.py`, `src/api/*` | Patient record, cohort, opportunity, manifest, mapping, annotation, and normalization endpoints. |
| FHIR | `src/export_fhir.py`, `src/medical_codes.py` | Bundle export from validated substrate with existing value coding. |
| Analyst agent | `src/chat_agent_v2.py`, `src/chat_prompts_v2.py`, `src/chat_v2_models.py`, `src/chat_recipes.py` | Default chat runtime and typed tool loop. |
| Retraction | `src/retractions.py`, `scripts/purge_patient.py` | Patient erasure from materialized outputs, HMAC tombstones, runtime suppression. |
| Reproducibility | `src/materialization_manifest.py` | Per-run hashes, coverage stats, eval status, retraction stats. |
| Tests and eval | `tests/test_*.py`, `tests/run_chat_eval.py` | Unit/integration checks and chat behavior report. |

## Data Flow

```
data/raw/treatment_answer.csv
        |
        v
load + discovery + AI classification
        |
        v
taxonomy.json + mapping_table.csv + semantic_mapping.json
        |
        v
answer_normalization.json + normalization_queue.json
        |
        v
survey_unified.csv  (raw/staging, audit/debug surface)
        |
        v
survey_validated    (runtime view, approved semantic mappings + reviewed values)
        |
        +--> /patients/{id}
        +--> /v1/export/{id}/fhir
        +--> /chat via DuckDBQueryService
        +--> opportunity and cohort artifacts
```

`survey_unified` remains the staging surface. It can contain pending,
rejected, or unknown semantics for audit and debugging. Downstream clinical
consumers should use `survey_validated`, which filters to approved or
overridden categories and exposes `validation_completeness`.

## Trust Boundaries

Semantic category trust is held in `semantic_mapping.json`. Rejected categories
are excluded from the validated layer and therefore from FHIR, analyst queries,
and clinical artifacts.

Answer-value trust is held in `answer_normalization.json`. Unknown variants are
captured in `normalization_queue.json` instead of silently becoming trusted
clinical facts.

Reviewer identity is captured through governance write headers:
`X-Uniq-Reviewer` and `X-Uniq-Role`. If absent, the API falls back to demo
identity so local demos still work, but pilot operations should send explicit
headers.

Materialization trust is held in `output/materialization_manifest.json` and
surfaced through `/v1/substrate/manifest`. The manifest contains input,
taxonomy, mapping, normalization, output-table, retraction, git commit, and
chat-eval metadata.

Retraction trust is held in `retraction_tombstones.json`. Tombstones store a
server-secret HMAC of `user_id`, not the plain ID. This is pseudonymization,
not anonymization: the HMAC secret must be kept outside git and preserved for
the pilot environment.

## Runtime Consumers

The API exposes the substrate through FastAPI routers under `src/api/routers/`.
Clinical patient endpoints and FHIR export reject active retractions with 404.

The analyst runtime defaults to v2 (`UNIQ_AGENT_MODE=v2`). It uses typed
Pydantic tool inputs, read-only DuckDB guardrails, terminal presentation tools,
and handle-based artifact resolution. The v1 agent remains available for local
fallback only.

The query service registers `survey_validated` before `survey_unified`. This
nudges analyst queries to the validated layer while still allowing explicit
inspection of staging data when needed.

## Pilot Scope

Live for the pilot:

- Wellster survey CSV/TSV ingestion.
- Registry-backed answer normalization and unknown queue.
- Clinician review state for semantic mappings and answer values.
- Validated layer for downstream clinical consumers.
- Materialization manifest with hashes, eval status, and retraction stats.
- Patient retraction from materialized outputs with HMAC tombstones.
- Analyst guardrail tests and chat eval harness.

Not pilot scope yet:

- Multi-tenant isolation.
- Real SSO/RBAC beyond reviewer headers.
- Postgres-backed governance stores.
- Full observability stack.
- Partial re-materialization by category.
- Generic multimodal loaders.

These are enterprise scale-out work, not hidden dependencies for the first
Wellster pilot.

## Legacy Surfaces

`src/chat_agent.py` and `src/chat_prompts.py` are v1 fallback surfaces. The
default analyst is v2. `src/demo.py` is the old Streamlit demo and is not part
of the production API path. Historical eval JSON files under `tests/` are kept
for comparison; the current eval output is `output/chat_eval_report.json`.
