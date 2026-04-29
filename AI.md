# AI Assistant Onboarding · UniQ

_For any AI assistant (Claude, Codex, Cursor, …) picking up this repo._
_Last updated: 2026-04-25_

If you can read 3 sentences before doing anything: read §1, §2, §6. The rest
sharpens the picture but those three keep you from doing damage.

---

## 1 · 30-Second Context

**Who you're working with**: Eren Demir, AI Engineer, founder/CEO of Previa
Health (€300K pre-seed, AI-powered MSK prevention). UniQ is a separate
project — a 4-week Spira Labs incubation track ending in an investor pitch
night late April 2026. **Default response language: German.**

**What UniQ is**, in one sentence:

> The **Clinical Truth Layer** — between chaotic source data and any
> downstream consumer (analytics, FHIR partners, AI agents, regulators) —
> turning raw input into clinician-signed, FHIR-native ground truth.
> Healthcare data, finally computable.

**Customer**: Wellster Healthtech (Germany's #1 D2P telehealth, 2M+
patients, 750K treatments, brands GoLighter / Spring / MySummer).

**Why now**: ePA sanctions active in DE, EHDS by 2029, GDNG enables
secondary use, GLP-1 explosion creates the data goldmine, AI agents need
trustable substrates. Four-force convergence — see `POSITIONING.md` §3.

---

## 2 · Mandatory Reading Order

**Stage 1 — what exists, code-wise (5 min):**

1. `README.md` — what UniQ is, repo structure, quick-start
2. `wellster-pipeline/STATUS.md` — what's on `main` today (Phase 8): six
   surfaces, v2 agent at 14/16 eval, full tech stack, test state

**Stage 2 — strategic identity (15 min):**

3. `POSITIONING.md` — the master strategy doc. Clinical Truth Layer
   frame, Hybrid Adaptive architecture, Onboarding-Operation duality,
   13 chapters, falsifiability tests, recent refinement log. **The
   single most important document — read all 580 lines.**
4. `MARTIN_BRIEFING.md` — the post-Martin-call frame evolution in
   ~100 lines. Useful as a digest of POSITIONING if you're short on time.
5. `PITCH_DECK.md` — how the strategy lands as a ~4:00 jury pitch
   (six slides + Q&A prep + soundbites).

**Stage 3 — operational targets (10 min):**

6. `WELLSTER_BRIEFING.md` — what we're offering Wellster operationally:
   four use cases (cross-brand cross-sell, ePA compliance, GDNG
   activation, quality signal) + 5-day onboarding plan + what to learn
   from them. **Read this before any Wellster-related work.**
7. `context.md` — older strategy snapshot. Some pricing-tier numbers
   are pre-revision and the 3-layer product framing has been replaced
   by Onboarding-Operation duality. **Treat as historical**, but the
   Wellster background section + judging criteria are still gold.

**Stage 4 — frontend-only work (skip otherwise):**

8. `frontend/AGENTS.md` + `frontend/CLAUDE.md` — **critical warning**:
   Next.js 16 has breaking changes vs your training data. Validate any
   new feature against `node_modules/next/dist/docs/` before writing it.
9. `frontend/DESIGN.md` — Clinical Ledger design tokens + conventions.
10. `frontend/README.md` — frontend quick-start.

---

## 3 · Code Orientation

You don't need to read these — you need to know they exist.

**Backend (`wellster-pipeline/`):**
- `src/api/main.py` — FastAPI entry with async lifespan
- `src/api/models.py` — every Pydantic response model, including the five
  artifact families (`CohortTrendArtifact`, `AlertsTableArtifact`,
  `TableArtifact`, `FhirBundleArtifact`, `PatientRecordArtifact`)
- `src/api/routers/` — `meta`, `mapping`, `patients`, `chat`
- `src/chat_agent_v2.py` — unified Sonnet tool-loop, the active runtime
  (`UNIQ_AGENT_MODE=v2`)
- `src/chat_prompts_v2.py` — system prompt + tool schemas + routing rules
- `src/chat_v2_models.py` — Pydantic input validators for every
  `present_*` tool
- `src/artifact_builders.py` — five builders (one per family),
  Pydantic-validated, with `build_degraded_table_from_df` fallback
- `src/datastore.py` — `UnifiedDataRepository` with typed per-patient reads
- `src/query_service.py` — DuckDB read-only SQL with guardrails

**Frontend (`frontend/`):**
- `src/app/analyst/page.tsx` — chat UI with thinking pacer
- `src/components/analyst/artifact-*.tsx` — five renderers, one per
  family. `artifact-patient-record.tsx` is the newest (Phase 8).
- `src/components/analyst/artifact-panel.tsx` — dispatch + fullscreen +
  FHIR download
- `src/lib/api.ts` — typed BFF client + every artifact type
- `src/lib/demo/recipes.ts` — scripted fallback for offline / wifi-fail demos
- `src/app/globals.css` — Clinical Ledger tokens + all component CSS
  (~3000 lines, organised by surface)

---

## 4 · Current State

_(Update this section after every commit that materially changes things.)_

**Live on `main`** — 6 surfaces:
`/` story · `/start` intake console · `/review` HITL sign-off ·
`/substrate-ready` clinical repository map · `/analyst` v2 chat with
6 artifact families · `/platform` API + Agents preview

**Current uncommitted work**:
- `opportunity_list` / screening-candidates artifact end-to-end
  (Spring → GoLighter · BMI ≥ 27 · no GoLighter history · 456 active
  candidates, 60 high priority)
- `/v1/substrate/manifest` + `/substrate-ready` repository map
  (resource cards, FK topology, API hooks, audit provenance)
- Analyst demo fallback now covers upstream LLM outage for golden prompts

**Most recent commits:**
- `acbc896` Add strategic positioning + pitch documents
- `4de0c39` Phase 8: patient_record artifact + /review reset utility
- `db9a21c` Phase 7: guided demo flow + Platform surface + Agents preview

**Calendar**:
- **This week**: Wellster intro mails to Irena Medlin + Maria Chernevich
  (drafted / awaiting send unless user says otherwise).
- **End of April**: Spira Labs pitch night.

**Open work items**:
- `#12` Clinician-annotation overlay on `patient_record` (Martin's
  "Living Substrate" demand · annotation + activity-feed)
- `#13` Multi-modal input roadmap visual (defensive Q&A slide · static,
  no code · ~30 min)
- `#14` Update strategic docs after the current uncommitted feature set is
  committed (`STATUS.md`, `POSITIONING.md`, `WELLSTER_BRIEFING.md`)

**Demo patient (Phase 8 anchor)**: PT-383871 — 44 y female, GoLighter
brand, Mounjaro cohort, BMI 30.35 → 26.47 over 423 days, dose escalation
2.5mg → 5mg, 11 BMI measurements, 11 medication segments, 169 source
fields collapsed.

**Canonical demo prompts (live-verified, always work):**
1. `Open patient 383871` → patient_record family
2. `Find GoLighter screening candidates from Spring` → opportunity_list
3. `Show BMI trends for the Mounjaro cohort` → cohort_trend family
4. `Which patients have data quality issues?` → alerts_table family
5. `Generate a FHIR bundle for patient 381119` → fhir_bundle family

---

## 5 · Repo Conventions & Gotchas

- **Default response language is German** unless the user writes English.
  Technical terms stay in their original form. Diacritics are mandatory
  (ä, ö, ü, ß — never substitute with ae, oe, ue, ss).
- **Bash on Windows host**: use `/c/Users/...` not `C:\Users\...` in shell;
  use forward slashes; PowerShell is also available via the PowerShell tool.
- **Git**: never `git status -uall` (memory issues on this repo). Stage
  files explicitly, never `git add -A`. Always create new commits, never
  amend. Always include the `Co-Authored-By: Claude Opus 4.7 (1M context)
  <noreply@anthropic.com>` trailer (or analogous for Codex). Use HEREDOC
  for multi-line commit messages.
- **`uniq-video/package-lock.json` drifts** — leave it as `M` in the
  working tree, never commit it.
- **`wellster-pipeline/output/`** is gitignored and contains real Wellster
  patient data (PHI). **Never commit it.** Never push it via any service
  that isn't end-to-end encrypted. The runtime zip mechanism on Eren's
  Desktop is the canonical transfer method between machines.
- **`wellster-pipeline/.env`** is gitignored and contains the
  `ANTHROPIC_API_KEY`. Never commit it. The same transfer caveat applies.
- **Next.js 16 in frontend/**: your training data is outdated. Read
  `node_modules/next/dist/docs/` before writing any new Next-specific
  feature. See `frontend/AGENTS.md`.
- **Auto-memory at `~/.claude/projects/C--Users-Eren-Uniq/memory/`** is
  loaded automatically into Claude Code sessions (if you are Claude). For
  Codex / other AIs, that directory is plain markdown — read it manually
  for user-preference context.

---

## 6 · How to Verify You're Set Up

Before making any change, run these in parallel:

```bash
git status --short                              # working tree clean?
git log --oneline -5                            # latest commit matches §4?
ls wellster-pipeline/.env                       # exists?
ls wellster-pipeline/output/semantic_mapping.json # exists?
curl -s http://127.0.0.1:8000/health            # backend up?
```

If `wellster-pipeline/output/` is empty or `.env` missing, the runtime is
not provisioned. The user has a `uniq-runtime.zip` mechanism on Desktop
(Windows) for cross-machine transfer — ask before regenerating from
scratch.

---

## 7 · How to Update This Document

Update §4 (Current State) after any of:
- a commit that ships a new surface, artifact, or material backend change
- a strategy meeting that shifts identity or priority
- an external date being scheduled or moved (Ansgar, Wellster, pitch night)
- a task in the open-items list being completed or replaced

Sections 1, 2, 3, 5, 6 only change rarely. Update them deliberately, not
opportunistically.

When in doubt: ask Eren before rewriting strategic framing here. Tactical
state is yours to keep current; identity is his to define.
