# UniQ · Status

_Last updated: 2026-04-23_

## In one sentence

**UniQ is a trusted clinical data substrate with human sign-off, FHIR
interoperability, and developer APIs. The Analyst is the first app
built on it — partners can configure their own.**

Nothing about that sentence is aspirational. Every clause corresponds
to a surface on `main`.

---

## The problem UniQ solves (McKinsey framing)

### Situation
Wellster Healthtech operates three telehealth brands (GoLighter /
obesity, Spring / sexual health, MySummer / contraception) serving
750,000+ treatments across 12 indications. Every brand collects patient
data through medical questionnaires at every touchpoint — initial
consultation, follow-ups, re-orders.

### Complication
Survey questions change constantly. New IDs, reworded text, different
answer formats, language variants. The same clinical question *"Do you
suffer from pre-existing conditions?"* exists under **67 different
question IDs**. *"Normal blood pressure"* is expressed in **9 different
text variants** across German, English, and survey versions.

Longitudinal patient analysis is impossible. Wellster cannot answer
basic clinical questions:
- *"Is Mounjaro more effective than Wegovy for patients aged 40–50?"*
- *"What's our side-effect profile across medications?"*
- *"Which patients are dropping off treatment?"*

### Resolution
UniQ automates the entire substrate layer:
1. AI discovers the clinical structure from the raw data (no
   hardcoded schema).
2. A clinician signs off on every semantic decision (HITL, non-
   negotiable for medical data).
3. The system normalises answers across languages and versions.
4. The result is a queryable FHIR-compliant substrate that any
   downstream system can consume directly — or that partners build
   their own AI agents on top of.

---

## Current surfaces (live on `main`)

| Route | Purpose | State |
|---|---|---|
| `/` | Story — Clinical Ledger hero, Lattice animation, pillars | live |
| `/start` | Intake Console — scripted processing trace showing the pipeline | live |
| `/review` | HITL sign-off — 20 mappings, A/O/R workflow, real backend PATCH | live |
| `/substrate-ready` | Transition view — materialising metrics, substrate preview, three unlock cards | live |
| `/analyst` | v2 hybrid AI analyst — natural language → validated artifacts | live |
| `/platform` | API + Agents tabs — live-runnable endpoints, interactive agent configurator | live |

Every route is backed by a real FastAPI endpoint. The guided demo runs
from Story → Start → Review → Substrate → Analyst → Platform in a
single linear journey with tab-pulse indicators marking each handoff.

---

## The v2 analyst in one paragraph

One unified Claude Sonnet tool-loop. The agent picks the artifact
family (`cohort_trend`, `alerts_table`, `table`, `fhir_bundle`) via a
terminal `present_*` tool. SQL results live in a handle registry that
the backend resolves; Claude never emits raw row data. Every args
payload is Pydantic-validated; anything that fails validation
degrades to `table`. Four families, bulletproof rendering, model-
picked template. Codex' *"governed agents on shared substrate"*
framing, built.

**Eval score: 14/16 on the 16-case harness** (v1 recipe baseline
was 11/16). v2 wins on paraphrase (German, generic drug names),
filter extraction, and self-correction; loses only on two hair-thin
latency budget misses and one genuine year-filter exploration edge
case.

**Latency**: p50 ≈ 10 s, p95 ≈ 26 s. FHIR export is ~3 s, cohort-
trend takes 10–15 s, generic agent 6–15 s. Scripted `/start` trace
is 7.6 s and deliberately paced.

**Default**: `UNIQ_AGENT_MODE=v2` from `config.py`. v1 (regex
recipes + Sonnet fallback) remains available via env flag for
latency-sensitive demos.

---

## Phase history

| # | Name | What shipped |
|---|---|---|
| 1 | Pipeline core | load · classify_ai · normalize_answers_ai · unify · quality · export_fhir |
| 2 | Repository | `UnifiedDataRepository`, typed patient reads, preparsed answer_canonical |
| 3A | Semantic mapping | 20 clinical categories → FHIR resources + medical codes |
| 3B | Query service | DuckDB views, guardrailed read-only SQL |
| 4 | API · HITL | FastAPI routers: meta · mapping · patients · chat-stub · export |
| 5 | Frontend | Next.js 16 · Clinical Ledger design · three rooms (Story · Review · Analyst) |
| 5b | Atomic IO | Windows-safe `atomic_write_json` + `atomic_read_json` with retry |
| 6 | Chat agent v1 | 3 deterministic recipes + Sonnet fallback, hybrid routing |
| 6b | Codex follow-up | Tightened `cohort_trajectory` matcher (AND-gate, no Mounjaro default) |
| C | Chat agent v2 | Unified Sonnet tool-loop, handle-based, `present_*` tools, 14/16 eval |
| 7 | Guided demo | `/start` · `/substrate-ready` · `/platform` (API + Agents preview) |

---

## Numbers that are real

From the live Wellster substrate (as of `main`):

- **5,374 patients** across GoLighter + Spring
- **20 clinical categories** discovered + mapped
- **20 / 20 mappings** reviewed (single-run snapshot)
- **1,031 quality flags** surfaced by `quality_report`
- **3,731+ FHIR R4 resources** exportable (Patient,
  Observation with LOINC, MedicationStatement with RxNorm + ATC,
  Condition with ICD-10 + SNOMED CT, AdverseEvent)

Pipeline has been proven to scale: 12K → 23K → 134K rows across
three datasets with zero code changes.

---

## Current test state

| Suite | Result |
|---|---|
| `tests/test_api.py` | 32 pass · 0 fail (pinned to v1 mode) |
| `tests/test_query_service.py` | 16 pass · 0 fail |
| `tests/test_repository.py` | 14 pass · 0 fail |
| `tests/test_semantic_mapping.py` | 15 pass · 0 fail |
| `tests/test_incremental_mode.py` | PASS |
| `tests/smoke_demo_load.py` | 26 pass · 4 warn · 0 fail |
| `tests/test_chat_agent_v2.py` | 4 pass · 0 fail |
| `tests/run_chat_eval.py --agent-mode v2` | 14 / 16 (live Sonnet) |

**Frontend**: `npx tsc --noEmit` clean · `npx eslint src/` clean ·
`npm run build` clean.

---

## Pitch flow (live demo, ~3.5 minutes)

1. **Story** *(15 s)* — *"chaos in, structure out"* — Lattice
   animation, three pillars, skip to intake.
2. **Start → Intake Console** *(30 s)* — Wellster card with pulsing
   green *connected*, four planned adapters as dashed chips, click
   *Run intake*. 7.6 s scripted trace with count-up numbers and
   per-step progress bars. Completion banner hands off to Review.
3. **Review** *(30 s)* — *"Pipeline · Step 2 · Final clinical sign-
   off required"* banner. Pivot row (BMI_MEASUREMENT) has a pulsing
   *Final approval required* flag. Approve → ink-stamp animation →
   redirect to Substrate-Ready.
4. **Substrate-Ready** *(15 s)* — Headline materialises, metrics
   tick up from 0 (5,374 patients, 20 categories, 20/20 mappings,
   1,031 quality checks), 5-row substrate preview, three unlock
   cards framing Analyst / FHIR / Platform as **consequences of**
   the substrate, not alternatives to it.
5. **Analyst** *(90 s)* — Live v2 with the four canonical prompts:
   *"Show BMI trends for the Mounjaro cohort"*, *"Which patients
   have data quality issues?"*, *"Generate a FHIR bundle for
   patient 381119"*, *"What are the most common side effects
   reported?"*. Each produces a different artifact family. If the
   jury asks something unscripted, v2 handles paraphrase + German
   + generic drug names gracefully.
6. **Platform** *(30 s)* — `API` tab: auth/versioning strip,
   Resource Map with Available now / Next columns, three live-
   runnable examples. Switch to `Agents` tab: *"Custom clinical
   agents on shared substrate"* with four blueprint presets,
   toggleable pills for resources/tools/artifacts, live-updating
   JSON spec mirror. Close with *"Partner for early access"*.

**The implicit sentence the jury should walk away with**:
> *UniQ is the trusted clinical data substrate. Human sign-off is
> the trust mechanism. FHIR is the interoperability story. The
> Analyst is the first app. You build the next.*

---

## Tech stack (current)

| Layer | Stack |
|---|---|
| Backend language | Python 3.11+ |
| API framework | FastAPI with async lifespan · Pydantic v2 models |
| Query engine | DuckDB (zero-copy views over Pandas DataFrames) |
| Data processing | Pandas |
| AI | Anthropic Claude — Sonnet 4.6 for analyst + classification |
| Atomic IO | Custom `io_utils` with Windows PermissionError retry |
| Frontend framework | Next.js 16 (App Router · Turbopack) |
| UI runtime | React 19 |
| Styling | Tailwind CSS 4 + hand-written Clinical Ledger tokens |
| State (server) | TanStack Query |
| Animation | React `<ViewTransition>` + CSS transitions |
| Typography | Newsreader (display) · IBM Plex Sans (body) · IBM Plex Mono (data) |
| Type safety | TypeScript 5 · discriminated-union artifact contract |
| Testing | Python: self-written runners (pytest-free) · FastAPI TestClient |

**AI cost discipline**: the pipeline itself is ~$0.10 per run
(2 API calls total: classification + answer normalisation).
Analyst chat turns are ~$0.02–0.10 each. A full 16-case v2 eval
costs ~€0.70. Prompt caching is on.

---

## What makes UniQ different (moat in four lines)

1. **Governed substrate, not raw access.** Every endpoint flows
   through a clinician sign-off gate. No raw LLM output reaches a
   user-facing surface.
2. **Template-bound artifacts.** Claude picks from four validated
   families, never emits free SVG / HTML / chart grammar.
   Pydantic validates every args payload; validation failures
   degrade to `table`.
3. **Primitive + packaged duality.** `/mapping`, `/patients/{id}`,
   `/export/{id}/fhir` are primitives. Chat + FHIR-export are
   packaged services. Partners mix them in their own agents via
   the (preview) configuration API.
4. **Honest roadmap.** The Platform Resource Map shows what is
   live vs planned side by side. The agent's JSON spec is a real
   preview shape, not a fake deploy button. Nothing overclaimed.

---

## Who pays

| Customer | Pain | Willingness to pay |
|---|---|---|
| **Telehealth platforms** (Wellster, Ro, Hims) | Can't track outcomes over time; data fragmented across versions | High — directly impacts clinical quality metrics |
| **Clinical-trial CROs** (IQVIA, Parexel) | Protocol amendments break eCRF continuity → FDA-submission delays | Very high — weeks of delay = millions |
| **Insurers / Krankenkassen** | Can't aggregate patient-reported outcomes across providers | High — reimbursement decisions ride on aggregates |
| **Hospital groups post-merger** | Incompatible intake forms → no unified patient record | Medium-high — compliance + clinical risk |

Three customer archetypes are visible in the Agents-tab blueprints:
**Weight-loss coach** (patient-facing), **Trial recruiter**
(cohort eligibility), **Care-pathway optimizer** (deviation
alerts). Each is a fork of the UniQ Analyst with different
resources / tools / review policies.

---

## Business model

SaaS with two revenue layers:

1. **Substrate access** — per-patient-record, tiered by volume.
   API consumption (mapping, patient, FHIR export, chat) metered.
2. **Agent configurations** — per-agent per-month, with enterprise
   tier for dedicated blueprints, custom tools, custom templates.

Enterprise sales: SOC 2 / HIPAA compliance path, HIPAA-compliant
hosting partner (Datica / Aptible), dedicated tenant isolation.

---

## Roadmap (post-pitch, honest)

### Platform Tier 1 (weeks 1–3)
- Version every endpoint under `/v1`
- Add `/v1/patients/{id}/observations` (BMI, vitals, labs)
- Add `/v1/cohorts` (define + query patient groups)
- Add `/v1/ingest/jobs` (async data intake with job status)
- OpenAPI export from FastAPI → real reference docs site
- Public status page (Vercel edge fn pinging `/health`)

### Platform Tier 2 (weeks 4–8)
- Python SDK (`pip install uniq`)
- TypeScript SDK (`npm install @uniq/client`)
- Webhook registry (`mapping.approved`, `ingest.completed`,
  `quality.flagged`)
- Configuration API for agents (real deploy endpoint)
- Rate limiting + quota-based tiers

### Platform Tier 3 (months 2–6)
- SOC 2 audit path
- HIPAA-compliant hosting
- Enterprise SSO + audit logs
- Partner marketplace (custom adapters, custom taxonomies)
- Real-time FHIR proxy (not just batch export)

### Analyst improvements (ongoing)
- Close the two latency edge cases (pos_cohort_mounjaro,
  filt_year)
- German KPI / column labels in cohort_trend
- Streaming variant (SSE) for the generic path
- Cassette-based eval fixtures for offline CI

---

## Known unfinished

Intentionally not addressed, so we're honest about the state:

- `uniq-video/package-lock.json` has untracked modifications
  (from a Phase-5 experiment) that we deliberately leave out of
  commits.
- `/platform` and `/substrate-ready` cannot be linked from the
  nav in a way that makes deep-linking work outside the guided
  flow — that's by design for the transition, not by oversight.
- Story-page pillar stats (`94%`, `0.42s`) have been removed but
  some legacy copy in `page.tsx` could still read more honestly.
- No end-to-end browser tests; we rely on manual dry-runs +
  live backend + live Sonnet eval.

---

## Repo layout (current)

```
UniQ/
├── frontend/                        Next.js 16 · Clinical Ledger UI
│   ├── src/app/
│   │   ├── page.tsx                 Story (landing, Lattice, CTAs to /start)
│   │   ├── start/page.tsx           Intake Console
│   │   ├── review/page.tsx          HITL sign-off
│   │   ├── substrate-ready/page.tsx Transition state
│   │   ├── analyst/page.tsx         v2 chat UI
│   │   ├── platform/page.tsx        API + Agents tabs
│   │   └── api/uniq/*               BFF proxy to FastAPI
│   ├── src/components/              Nav · page-transition · providers
│   └── src/lib/                     Typed API client · demo recipes
│
├── wellster-pipeline/               Python backend
│   ├── config.py                    Env + agent-mode selector
│   ├── pipeline.py                  Orchestrator (CLI)
│   ├── src/
│   │   ├── load.py · normalize*.py  Stage 1 — ingest + canonicalisation
│   │   ├── classify_ai.py           Stage 2 — AI category discovery
│   │   ├── unify.py · quality.py    Stage 3 — unified tables + checks
│   │   ├── export_fhir.py           Stage 4 — FHIR R4 export
│   │   ├── datastore.py             Stage 5 — typed repository
│   │   ├── query_service.py         Stage 6 — DuckDB read-only SQL
│   │   ├── io_utils.py              Atomic write + read with Windows retry
│   │   ├── chat_prompts.py          v1 system prompt + tool schemas
│   │   ├── chat_tools.py            v1 tool implementations
│   │   ├── chat_recipes.py          v1 deterministic recipes
│   │   ├── chat_agent.py            v1 hybrid agent
│   │   ├── chat_prompts_v2.py       v2 system prompt + tools (imperative)
│   │   ├── chat_v2_models.py        v2 Pydantic tool-input validators
│   │   ├── chat_agent_v2.py         v2 unified tool-loop (handles, present_*)
│   │   ├── artifact_builders.py     4-family artifact builders
│   │   └── api/
│   │       ├── main.py              FastAPI app
│   │       ├── deps.py              DI (repo, query, state, atomic mapping)
│   │       ├── models.py            Pydantic response models
│   │       └── routers/             meta · mapping · patients · chat
│   ├── tests/                       self-written runners + eval harness
│   └── output/                      Generated substrate (gitignored)
│
├── uniq-video/                      Remotion video (separate, Phase 5 era)
├── README.md · context.md           Onboarding docs
└── wellster-pipeline/STATUS.md      This file
```

---

## Team

Built with Claude (Anthropic Sonnet 4.6 as analyst runtime · Opus 4.7 as
development pairing partner via Claude Code) and Codex as architecture
sparring partner. Both AI collaborators are credited in commit trailers.
