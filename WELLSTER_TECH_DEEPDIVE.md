---
tags: [uniq, wellster, technical-deepdive, follow-up]
type: technical-doc
date: 2026-04-28
audience: Wellster Data Team + Product Owners
authored-by: Eren Demir (UniQ)
status: draft-v2
---

# UniQ · Technical Deep-Dive for Wellster

> [!info] Purpose
> Technical follow-up to the call on 2026-04-28. Direct answer to the questions your data team raised — about robustness, AI normalization trust, real-world deployment effort, HITL configurability, and how this would scale beyond a hackathon snapshot. Written to be read by engineers, not by procurement.

> [!warning] Honesty convention
> Every capability in this document is tagged with one of three states. Take them literally.
> - **Live** — running today on `main`, exercised by tests, used by the demo
> - **Workshop-time** — happens during the onboarding week, not as a productized surface
> - **Planned** — architecture supports it, code does not yet
>
> Anywhere a state isn't tagged, treat the claim as descriptive of intent, not of current code. We'd rather you find the gaps in this document than in your pilot.

---

## TL;DR

**What UniQ is, technically**: a three-stage pipeline (AI Discovery → Clinician HITL → Deterministic Unification) that produces a queryable substrate sitting *next to* your operational systems. Your databases stay where they are; UniQ materialises a clinician-reviewed clinical layer beside them on each pipeline run.

**What's robust today**: AI sees structure-not-volume so hallucination surface is bounded by ~228 unique question texts (not 134k rows); after the substrate is materialised, it's read by deterministic Pandas + DuckDB code; failure modes are surfaced via a `quality_report` table. The Analyst surface uses an LLM at query time, but constrained by read-only SQL guardrails, Pydantic-validated tool inputs, and template-bound artifact rendering.

**What's honestly not yet robust**: HITL is not enforced as a programmatic gate in the pipeline today (the demo flow presents it as one — the production pipeline currently runs Discovery → Normalize → Unify without a hard review block). Answer-value normalization runs without a per-label HITL surface. New unknown answer variants fall to `null` rather than into a queue. There is no versioning, no audit-grade RBAC, no GDPR-deletion workflow today.

**What's configurable in the pilot vs. what's production-grade**: the HITL spectrum below (§4) describes what we'd configure with you during onboarding — most positions on the spectrum are workshop-time today, not features in a UI. Productizing them is part of pilot deliverables.

---

## 1 · Three-Pillar Architecture

```
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│      LOADERS       │     │       ENGINE       │     │     CONSUMERS      │
│   (input adapters) │     │   (UniQ proper)    │     │   (downstream)     │
├────────────────────┤     ├────────────────────┤     ├────────────────────┤
│ Live:              │     │ Live:              │     │ Live:              │
│  ✓ Wellster survey │ ──► │  ✓ AI Discovery    │ ──► │  ✓ Analyst (NL+SQL)│
│    CSV/TSV         │     │  ✓ HITL surface    │     │  ✓ FHIR export     │
│    (column-coupled)│     │    (review-only)   │     │  ✓ Cohort lists    │
│                    │     │  ✓ Unification     │     │  ✓ Substrate API   │
│ Planned:           │     │  ✓ Quality monitor │     │  ✓ Annotations     │
│  ─ Generic tabular │     │                    │     │    (write-back)    │
│  ─ Clinical notes  │     │ Planned:           │     │                    │
│  ─ PDFs (OCR)      │     │  ─ Programmatic    │     │ Planned:           │
│  ─ Medical images  │     │    HITL gate       │     │  ─ Webhook events  │
│  ─ Wearables stream│     │  ─ Unknown queue   │     │  ─ Partner SDKs    │
│  ─ Realtime API    │     │  ─ Versioned state │     │                    │
│                    │     │         ▼          │     │                    │
└────────────────────┘     │     SUBSTRATE      │     └────────────────────┘
                           │  (clinical truth)  │
                           │   reviewed · queryable │
                           │   audit-trailed     │
                           └────────────────────┘
```

**The architectural commitment**: the engine is the stable centre. Loaders and consumers grow around it. The substrate is the contract. Adding a new loader does not require modifying the engine — but the loader itself, plus the entity-mapping for the new modality, is real engineering work each time.

---

## 2 · The Engine in Detail

### 2.1 · Stage 1 — AI Discovery (`classify_ai.py`, `semantic_mapping_ai.py`, `normalize_answers_ai.py`)

**What it does (Live)**: takes the raw input, finds unique patterns, proposes structure.

**Three sub-steps, three single API calls**:

1. **Question classification** (`classify_ai.py`)
   - Sees **228 unique English question texts** (deduped from 4,553 raw question_ids in your dataset)
   - Returns: each question_id → `clinical_category` (e.g. `BMI_MEASUREMENT`)
   - Persisted to `taxonomy.json`
   - **Cost discipline anchor**: hallucination surface is bounded by 228 unique items, not 134k rows

2. **Semantic mapping** (`semantic_mapping_ai.py`)
   - For each discovered category, proposes: `display_label`, `fhir_resource_type`, `codes` (LOINC / SNOMED / ICD-10 / RxNorm), `confidence` (`high` / `medium` / `low`), `reasoning`
   - File-level docstring is explicit: *"downstream consumers only use high-confidence entries automatically. Medium and low entries require human review before they influence the runtime path."* — this is the **intent**; see §3.1 for honest gating semantics today
   - Persisted to `semantic_mapping.json`
   - On re-runs: approved/overridden entries are preserved verbatim (incremental safety)

3. **Answer normalization** (`normalize_answers_ai.py`)
   - Sees all unique answer values per category at once (~416 → ~164 canonical labels)
   - Returns: each `original_text` → `CANONICAL_LABEL`
   - Persisted to `answer_normalization.json`
   - **Honest behaviour today**: on subsequent runs, the existing JSON is loaded and applied. New answer values that weren't in the original set fall to `None` in `survey_unified.answer_canonical`. There is no automatic re-routing back to the AI for unknown variants today, and no per-label HITL surface. See §3.2 for the gap and the closing plan.

**Cost discipline**: three API calls per full run, ~$0.10 in LLM cost on your dataset. AI never sees the 134k rows individually.

### 2.2 · Stage 2 — HITL Sign-Off (`/review` UI · `routers/mapping.py` · `semantic_mapping.json`)

**What it does today (Live, but not enforced)**: clinician reviews and modifies the AI's proposed semantic mappings. State is persisted on the mapping JSON.

**Today's surface**:
- 20 mappings shown on `/review`, one per discovered category
- Per-mapping actions: **Approve** · **Override** (inline editor for `display_label`, `fhir_resource_type`, reviewer note) · **Reject**
- State persisted via atomic JSON write to `semantic_mapping.json`
- Approved/overridden entries are preserved verbatim across re-runs

**Honest semantics — what `review_status` actually gates today**:
- `unify.py` reads `mapping_table.csv` (the AI-discovered category-per-question mapping) — it does **not** read `semantic_mapping.json`. The unification stage runs regardless of review state.
- The Analyst's prompt is built from `semantic_mapping.json` categories — it sees what's there but doesn't filter by review_status
- The patient_record artifact surfaces `review_status` per event in the audit trail (this is where it's visible to a user)
- FHIR export (`export_fhir.py`) currently uses hardcoded code tables for the obesity domain — it does not yet pull codes from the reviewed `semantic_mapping.json`

**What that means**: HITL is **a recorded decision** and is **visible in the audit trail**, but it does **not act as a programmatic downstream gate** in the current pipeline. The intent was always to gate, the implementation hasn't caught up.

**Planned (target for pilot)**:
- `unify.py` filters out rejected categories at materialisation time
- FHIR export reads codes from reviewed `semantic_mapping.json`, not hardcoded tables
- A blocking pipeline mode that refuses to materialise the substrate until every mapping has a non-`pending` status
- This is the kind of work that a Wellster-pilot would commit to early — closing the live-vs-intended gap is straightforward engineering

### 2.3 · Stage 3 — Continuous Unification (`unify.py` · `engine.py`)

**What it does today (Live)**: applies `mapping_table.csv` and `answer_normalization.json` to all rows, producing the substrate tables. Pure Pandas, no LLM in this stage.

**Resulting tables** (lives in `output/`, exposed via API):
| Table                    | Rows    | Endpoint                                          |
| ------------------------ | ------: | ------------------------------------------------- |
| `patients`               |   5,374 | `GET /patients/{id}`                              |
| `bmi_timeline`           |   5,705 | (via Analyst SQL today)                           |
| `medication_history`     |   8,835 | (via Analyst SQL today)                           |
| `treatment_episodes`     |   8,835 | (via Analyst SQL today)                           |
| `quality_report`         |   1,031 | (via Analyst SQL today)                           |
| `survey_unified`         | 133,996 | (via Analyst SQL today)                           |
| `semantic_mapping`       |      20 | `GET /mapping`, `PATCH /mapping/{category}`       |
| `clinical_annotations`   |       2 | `GET/POST /v1/patients/{id}/annotations`          |
| `fhir_bundle` (per-pat.) |       — | `GET /export/{id}/fhir`                           |
| Substrate manifest       |       — | `GET /v1/substrate/manifest`                      |
| Snapshot CSV exports     |       — | `GET /v1/substrate/resources/{name}/export.csv`   |

(The `/v1/` prefix is used for the new substrate-introspection routes; the per-patient and mapping routes were added earlier and don't carry the prefix yet. That's a versioning normalisation we'd do as part of pilot setup.)

**Snapshot CSV exports** are limited to a 6-resource whitelist: `patients`, `bmi_timeline`, `medication_history`, `treatment_episodes`, `quality_report`, `survey_unified`. `semantic_mapping` is served via `/mapping` (JSON, not CSV), `fhir_bundle` is per-patient via `/export/{id}/fhir`, `clinical_annotations` is JSON-only.

**Incremental mode** (`engine.py`): on subsequent runs, only NEW question_ids need a re-classify. Re-running on the same approved mapping produces identical output (idempotent at the unification stage). New rows with **unknown answer variants** fall to `null` in `answer_canonical` today (the gap from §2.1.3).

**Quality monitoring** (`quality.py`): runs every time. Today's checks (with real thresholds):
- BMI spike > **5 points** between consecutive measurements
- BMI gap > 90 days
- Undocumented medication switch
- Subscription lapse
- Suspicious BMI value

These flags are not warnings to the clinician — they are the substrate's own self-audit, surfaced as data in `quality_report`. Threshold values are hardcoded today; making them configurable is workshop-time.

---

## 3 · Robustness — Direct Answer to the Concerns You Raised

Per concern, we split into three honesty layers: **Live today**, **Workshop-time / Planned**, **Roadmap**.

### 3.1 · Concern: "How robust is AI category classification?"

**Live today**:
- AI sees only ~228 unique question texts at once (collapsed from 4,553 IDs)
- Each category gets a `confidence` score (`high` / `medium` / `low`)
- Clinician HITL records approve / override / reject decisions per category in `semantic_mapping.json`
- Approved categories are immutable across re-runs (preserved verbatim)
- Re-runs of `unify.py` on the same `mapping_table.csv` produce identical output (deterministic)
- Failure modes (BMI spikes, gaps, undocumented switches) surface as data via `quality_report`

**Workshop-time / Planned**:
- **HITL as enforced gate**: today `review_status` is recorded but does not filter `unify.py` output. Closing this is part of pilot scope — the change is small, the design discussion is the larger part
- **Confidence-gated auto-approve**: today every mapping requires manual sign-off in the demo flow but the pipeline doesn't enforce it. Auto-approving `high`-confidence mappings is a Wellster-side configuration choice we'd build into pilot
- **Re-classification on override**: when you override a category mid-operation, historical rows tagged under the old mapping are not automatically re-tagged. Today this requires a **full pipeline re-run**. A targeted re-materialisation flow is planned

**Roadmap**:
- **Active learning loop**: clinician overrides as fine-tuning signal back into the discovery prompt. Today the AI doesn't learn from your overrides between runs

### 3.2 · Concern: "How robust is AI answer-value normalization?" (the sharpest question)

**Live today**:
- All unique answer values per category go to AI in a single call (`normalize_answers_ai.py`)
- AI returns `original_text → CANONICAL_LABEL` mapping
- Mapping persisted to `answer_normalization.json`
- Applied deterministically across all rows by `unify.py`

**Honest gap (this is the real one)**:
- **No per-label HITL surface today.** Categories get HITL via `/review`. Canonical labels (the ~164 outputs from answer normalization) flow into `survey_unified.answer_canonical` without a clinician signing off on each label
- **No unknown-variant queue.** A new answer variant that wasn't in the original training set falls to `null` in `answer_canonical`. There's no automatic re-route back to the AI, no review queue, no `UNCATEGORIZED` placeholder
- **No confidence-per-label.** The category-level confidence exists; there's no equivalent for individual canonical labels
- **No "merge / split / rename" workflow on canonical labels.** Today you'd edit `answer_normalization.json` directly during onboarding, then re-run

**What we'd build with you during pilot (workshop-time → productized)**:
- **Per-label review surface**: a second HITL screen alongside `/review` that lets clinicians inspect the canonical-label set, merge / split / rename labels (workshop-time today via direct JSON edits; productized in pilot)
- **Unknown-bucket queue**: new variants get routed to a review queue with `UNCATEGORIZED` default until a clinician decides
- **Per-label confidence + auto-approve thresholds**: same idea as for categories
- **Coverage telemetry**: a stat showing what % of `survey_unified.answer_canonical` is non-null vs null today, to track normalization completeness over time

This is the area where Wellster's clinical input would shape architecture more than ours would. Co-design rather than fait-accompli.

### 3.3 · Concern: "Does the AI drift over time?"

**Live today, accurate framing**:
- **No LLM mutates the signed substrate after Stage 2.** Once `mapping_table.csv` and `answer_normalization.json` are written, all downstream materialisation is deterministic Pandas
- **The Analyst surface DOES use an LLM at query time.** Sonnet is invoked via `chat_agent_v2.py::run_chat_agent_v2` for every analyst chat turn. This is bounded by three guardrails:
    1. **Read-only SQL with denylist**: `query_service.py` rejects DDL/DML, file/network table functions, stacked statements, semicolons
    2. **Tool-bound output**: Claude can only emit artifacts via Pydantic-validated `present_*` tools — six families (`cohort_trend`, `alerts_table`, `table`, `fhir_bundle`, `patient_record`, `opportunity_list`). Failed validation degrades to a generic `table` artifact, never raw output
    3. **Handle-based result resolution**: the agent never emits raw row data — it references SQL result handles, the backend resolves them

**Where drift can manifest (honest)**:
1. **In Discovery**: a new question_id triggers a fresh classification. If the AI classifies it differently than a similar existing one, you'd see a divergent category for a near-duplicate. HITL catches this — workshop-time today, intended-as-gate planned
2. **In Answer normalization**: a new answer variant falls to `null` or to whatever the existing map contains. No automatic re-routing → no automatic drift, but also no automatic correctness
3. **In Analyst behaviour**: Sonnet picks routing per question. Behaviour is stable for canonical questions (we have an eval harness with 14/16 cases passing); it can vary for paraphrased or out-of-distribution questions. Failure mode is degraded output, not silent wrong output

**What's NOT a drift surface**:
- The substrate itself once materialised — deterministic
- Approved category mappings — frozen across runs
- The audit trail per data point — immutable record of what was approved when

### 3.4 · Concern: "The pitch shows fully-automated. Real-world is messier."

You're right. The pitch demos the *operational* phase. Real deployment has two distinct phases:

**Onboarding phase** (days 1-5+, human-led):
- Wellster shares a snapshot of your data (CSV is fine for the first round)
- AI runs Stage 1 — produces draft mappings
- Wellster clinician + Wellster data team + UniQ team work through the output together
- **Concretely workshop-time**: walk the `semantic_mapping.json` and `answer_normalization.json` files together; merge / split / rename categories and labels; agree on FHIR codes; agree on quality thresholds
- Configurable HITL depth chosen per category
- Output: a Wellster-specific signed-off mapping set you have inspected end-to-end

**Operational phase** (day 5+, mostly autonomous):
- Substrate updates incrementally as new data arrives
- Only NEW unknown patterns surface for review
- Quality flags surface in `quality_report` for periodic clinician scan
- Audit cadence: weekly review queue rather than per-event

The pitch shows the operational phase because that's where the magic is visible. The onboarding phase is where Wellster gets the most value from collaborating with us — it's where the substrate is shaped to your reality.

---

## 4 · The HITL Spectrum

The text below describes the **target operating model**. Today's state is marked per axis. Wellster picks where on each spectrum to operate, per category if needed.

### Per-mapping review (categories)

```
LOOSE                                                              TIGHT
  │                                                                   │
  │   [auto-approve high-conf]    [review every mapping]              │
  │            ▲                          ▲                           │
  │  ── planned for pilot ──   ── workshop-time today ──              │
```

### Per-label review (canonical answer labels)

```
LOOSE                                                              TIGHT
  │                                                                   │
  │  [no review surface]   [review label set]   [review each label]   │
  │         ▲                                                         │
  │   ── today (gap §3.2) ──                                          │
  │                              ▲                                    │
  │                       ── planned for pilot ──                     │
```

### Unknown-pattern handling (answer variants)

```
LOOSE                                                              TIGHT
  │                                                                   │
  │  [fall to null]   [queue for review]   [hard-stop ingest]         │
  │      ▲                                                            │
  │   ── today ──                                                     │
  │                        ▲                                          │
  │              ── planned for pilot ──                              │
```

### Audit cadence

```
LOOSE                                                              TIGHT
  │                                                                   │
  │  [quarterly]   [monthly]   [weekly]   [daily]   [live queue]      │
  │                                ▲                                  │
  │                ── recommended for Wellster pilot ──               │
```

The point: HITL isn't a single story. It's a configurable surface, picked per-category, per-deployment. Today some positions on the spectrum are workshop-time (you'd configure them by editing the JSON files during onboarding); productizing each into a UI surface is part of pilot scope.

---

## 5 · Onboarding-Phase vs Operational-Phase

| Aspect                | Onboarding (days 1-5+)                              | Operational (day 5+)                                |
| --------------------- | --------------------------------------------------- | --------------------------------------------------- |
| Human involvement     | High — clinician + data team active daily           | Low — periodic review (weekly default)              |
| AI runs               | Full discovery on all data                          | Only on new unknown patterns (incremental)          |
| HITL surface          | Direct JSON inspection + `/review` for categories   | Auto-apply at chosen confidence threshold (planned) |
| Iterations            | Many — refine mapping based on clinical input       | Rare — only when surveys change or new brand added  |
| UniQ team             | Embedded with you, daily check-ins                  | Async — alerts + monthly sync                       |
| Output                | Signed-off `semantic_mapping.json` + `answer_normalization.json` + threshold config | Continuous, incremental substrate updates |

**Concrete onboarding workshop sketch**:
- **Day 1**: ingest a current snapshot · run Stage 1 discovery · share draft mappings
- **Day 2**: walk through categories together · clinician approves / overrides via `/review`
- **Day 3**: walk through canonical labels together · agree on splits / merges (direct JSON edits today)
- **Day 4**: configure quality_report thresholds for your tolerances · validate against known-good patients
- **Day 5**: run full pipeline end-to-end · sign off · hand-off to operational mode

---

## 6 · Extensibility — Honest Reading

The engine's three stages (discovery, HITL, unification) describe a **governance pattern**. The pattern is generic. The current code that implements it is **not generic** — it's coupled to Wellster's survey-table column names (`question_id`, `answer_value`, `product`, `brand`, `answer_value_height`, `answer_value_weight`, etc.).

So extending to a new modality (notes, images, PDFs, wearables) is **not a no-op**. What's required per modality:

1. A **new loader** that reads the source format
2. A **new entity-mapping** that translates the source into the engine's expected record shape
3. A **modality-aware Discovery prompt** — for free text, "what categories" looks different than for survey questions
4. **HITL surfaces** appropriate to the modality (e.g. for image-derived findings, the review may need to show the image alongside the proposed code)
5. **Unification logic** for how the modality joins with the existing substrate

What stays unchanged:
- The *idea* that AI proposes structure, clinician validates, deterministic code applies
- The substrate's join-on-`user_id` topology
- The audit-trail-per-data-point requirement

So multi-modal is **architecturally defensible** — the same governance pattern works. But each new modality is **real engineering work**, not a config flag.

**Honest framing**: today UniQ handles tabular survey data. Adding clinical notes is a project; adding images is another. We're upfront about that rather than promising plug-and-play.

---

## 7 · Scalability — How This Scales Past Wellster's Current Volume

You'd want to know this if Wellster grows, or if a future enterprise customer pulls the same architecture.

### 7.1 · Where the architecture scales linearly with data volume

- **Storage**: substrate output is ~100MB at 134k rows. Linear with row count
- **Unification**: deterministic Pandas operations, O(n) over rows
- **DuckDB query layer**: handles tens of millions of rows on a single host without performance issues
- **Per-patient API reads**: O(1) via the typed repository's user_id index

### 7.2 · Where the architecture scales sub-linearly (the AI cost story)

- **AI Discovery**: scales with the number of *unique patterns*, not row count
- Wellster's 134k rows have 228 unique question texts. A 10x larger dataset typically has only ~2-3x the unique patterns, because most of the variety is captured in the first generation of surveys
- **AI cost**: ~$0.10 per full run today, projected ~$0.30 at 10x data volume
- This is the architectural reason UniQ scales — not by throwing more LLM at more data, but by separating "what does the data mean" (AI, infrequent) from "apply that meaning to volume" (deterministic code)

### 7.3 · Where the architecture currently has bottlenecks

- **HITL review surfaces**: today shows all 20 mappings on a single scrollable page. Doesn't paginate. At 200 categories (large enterprise dataset) this would need pagination + filtering
- **Atomic JSON write contention**: the mapping JSON store is a single file. Two concurrent writers would race (mitigated by retry but not elegant). For multi-clinician concurrent review at scale, a real database backend is needed
- **Threshold tuning**: quality thresholds are hardcoded today. At enterprise scale you want per-cohort thresholds (different for obesity vs sexual health vs paediatric)
- **Mapping registry growth**: 20 categories today, comfortably 200 categories. Past 1,000 you'd want hierarchical organisation

### 7.4 · Iterative onboarding for large historical datasets

If Wellster wants to ingest 5+ years of historical data (millions of rows), the answer is **never bulk-ingest day 1**. The phased approach:

**Phase A — Recent slice (week 1-2)**:
- Ingest most recent 6 months of data
- Run discovery → produces the initial category and label set
- Clinician HITL on the full mapping output (workshop-time)
- Substrate is materialised only for that recent slice

**Phase B — Backfill (week 3-4)**:
- Ingest historical data in chronological chunks (oldest first or newest first, your call)
- Discovery is run **incrementally** — only NEW unknown patterns surface
- HITL on additions only — typically small (most variation is in the recent slice)
- Substrate grows backwards in time

**Phase C — Continuous (week 5+)**:
- Ingest active data stream
- Incremental mode handles ongoing additions
- Quality_report flags any anomalies as data grows

This phasing matches a clinician's daily attention budget. You never ask a clinician to review 1000 mappings in one sitting.

### 7.5 · Multi-tenant / Enterprise considerations (Roadmap)

For a future enterprise deployment beyond Wellster:
- Multi-tenant substrate (per-customer isolated) — **planned, not built**
- Customer-specific code-system overrides (e.g. a customer using their internal product taxonomy alongside RxNorm) — **planned**
- Cross-tenant analytics with privacy-preserving boundaries — **roadmap**
- SOC2 / HIPAA audit path — **roadmap**

---

## 8 · Where We Are Today (Honest Inventory)

### 8.1 · Live on `main`

| Capability                                      | State                                  |
| ----------------------------------------------- | -------------------------------------- |
| AI Discovery (questions → categories)           | live                                   |
| AI Semantic mapping (FHIR codes proposed)       | live                                   |
| AI Answer normalization (canonical labels)      | live                                   |
| HITL `/review` surface (per-category)           | live (records state, not enforced)     |
| Unification → 8 substrate tables                | live                                   |
| Quality monitoring (`quality_report`)           | live (5 hardcoded checks)              |
| FHIR R4 export per patient                      | live (uses hardcoded codes, not signed mapping) |
| Substrate manifest API                          | live                                   |
| Snapshot CSV exports (6-resource whitelist)     | live                                   |
| Clinical annotations (write-back)               | live (pre-seeded + POST endpoint)      |
| Analyst with 6 artifact families                | live (LLM at query time, guardrailed)  |
| Cross-brand cohort artifact (Spring → GoLighter)| live                                   |
| Backend test suite                              | 33 tests passing                       |
| Wellster dataset                                | 134k rows unified, queryable           |

### 8.2 · Architected, but not yet enforced or productized

- HITL as programmatic gate on `unify.py` output (today `mapping_table.csv` is read regardless)
- FHIR export reading from reviewed `semantic_mapping.json` (today uses hardcoded code tables)
- Per-label HITL surface for canonical answer labels
- Unknown-variant review queue (today nulls in `answer_canonical`)
- Confidence-gated auto-approve
- Targeted re-materialisation when a mapping is overridden (today requires full pipeline re-run)
- Configurable quality thresholds (today hardcoded)
- Pagination on review surfaces

### 8.3 · Roadmap (post-pilot)

- Multi-modal loaders (notes, images, PDFs, wearables, real-time feeds)
- Versioned snapshots of substrate over time + rollback semantics
- GDPR right-to-be-forgotten workflow
- Authenticated user identity for annotations + audit (today demo author hardcoded)
- Webhook subscription registry
- Multi-tenant deployment
- SOC2 / HIPAA compliance audit

### 8.4 · Explicitly out of current scope

- We do **not** replace your operational databases — they remain your system of record
- We do **not** issue clinical recommendations or diagnoses (no MDR medical-device claim)
- We do **not** automate outreach or marketing decisions — those stay with Wellster Operations
- We do **not** move PII outside the substrate boundary without a signed DPA
- We do **not** claim formal FHIR-export validation against the HL7 validator — we generate FHIR R4 resources structurally; formal certification is future work

---

## 9 · Open Questions for Your Team

> [!question] Things we'd like your engineering instinct on

1. **Data delivery**: lowest-friction way to get incremental data into UniQ — periodic CSV drop, REST pull, direct Postgres replica, change-data-capture stream?
2. **Existing mapping work**: you mentioned your data team is already trying to structure the data. What have you tried, what worked, what didn't? We'd rather build on your prior work than duplicate it
3. **Compliance gating**: who internally has to sign off on a substrate-style data sharing arrangement? Typical timeline?
4. **Clinical sign-off ownership**: realistically, who would own HITL reviews — Medical Director? External clinician? Rotating panel?
5. **Brand expansion**: GoLighter + Spring first, or onboard MySummer in parallel?
6. **Multi-modal urgency**: are clinical notes, PDFs, or wearables already on your data-strategy roadmap? That shapes our loader-priority order
7. **Confidence thresholds**: where on the HITL spectrum (§4) does Wellster's clinical risk appetite land?
8. **Historical depth**: do you want to backfill 5+ years of historical data, or is "live forward only" the realistic deployment shape?
9. **Quality-threshold tuning**: should `quality_report` thresholds be per-cohort (obesity vs sexual health), or global?

---

## 10 · Worked Example — PT-383871

For your data team to ground-truth against:

| Aspect                                 | Value                                                |
| -------------------------------------- | ---------------------------------------------------- |
| Patient                                | PT-383871, female, 44, GoLighter brand               |
| Tenure                                 | 423 days (Jan 2025 → Mar 2026)                       |
| Treatment                              | Mounjaro, escalated 2.5mg → 5mg                      |
| BMI trajectory                         | 30.35 → 26.47 (Δ -3.88 across 11 measurements)       |
| Medication segments                    | 11 dosage-bounded periods                            |
| Quality flags                          | 0 (clean record)                                     |
| Distinct source fields collapsed       | 169                                                  |
| **Actual FHIR R4 resources** (verified)| **23** (1 Patient + 11 Observations + 11 MedicationStatements) |
| Audit-traceable per data point         | yes — back to `surrogate_key` + reviewed mapping     |

**API endpoints to verify yourself**:
- `GET /patients/383871` — typed JSON record
- `GET /export/383871/fhir` — full FHIR R4 bundle (23 resources)
- `GET /v1/substrate/resources/patients/export.csv` — bulk CSV (PT-383871 is one row in it)
- `GET /v1/patients/383871/annotations` — clinician notes pinned to this patient
- Analyst surface: prompt `Open patient 383871` → multi-track timeline + audit trail per event

---

## 11 · Cuts from v1 of this document

For transparency, things we removed after internal review because they overstated the current state:

- "AI runs at query time" claim was wrong-sided — corrected in §3.3 to acknowledge Analyst uses LLM, with explicit guardrails
- "Drift can only manifest as new patterns needing review" — softened, drift surfaces named per stage
- "FHIR resource count: 135" — corrected to actual 23 (the prior count was an artifact-internal events count, not real FHIR resources)
- "rejected mappings excluded from downstream tables" — removed (not implemented)
- "BMI changes >7" — corrected to actual >5
- "Missing dosage" check — removed (not in `quality.py`)
- `python pipeline.py --rerun-category X` CLI — removed (CLI flag does not exist)
- Active learning loop, partner SDKs, marketplace, SOC2/HIPAA — moved from "live capabilities" to "roadmap" per accurate framing
- Multi-modal "same engine unchanged" framing — downgraded to "same governance pattern, new loader+entity-mapping work required per modality"

This honesty serves the doc's purpose: a technical team that fact-checks against the code will find these corrections themselves. We'd rather surface them upfront.

---

> [!note] Iteration model
> This document is a starting point, not a closed spec. The most useful next step would be a 60-90 min working session with your data team where we walk through this doc together and you mark up everything that's unclear, optimistic, missing, or contradicting your reality. We iterate from your markup, not from our defaults.
