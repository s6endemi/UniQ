---
tags: [uniq, wellster, call-prep]
type: handout
date: 2026-04-28
person: Irena Medlin
status: pre-call
---

# Irena · Call Handout

> [!info] Purpose
> Reference material for the intro conversation. Bullet-organised, not a script. The flow follows a natural builder's story — start with the problem, walk through the engine, end with open questions.

---

## 1 · Problem Statement

> [!quote] What we observed in your treatment-answer dataset (~134k rows)
> The same clinical question *"Do you have diabetes?"* exists under **67 different question IDs**.
> *"Normal blood pressure"* is stored in **9 different text variants** across DE / EN / survey versions.

**Scale of the fragmentation**

- **4,553** unique question IDs total → collapse into **20** clinical categories
- **416** answer variants → collapse into **164** canonical labels
- Survey schemas evolve constantly — every new version creates a new ID layer

**Operational consequences**

- Longitudinal patient analysis is effectively impossible without manual re-coding
- Questions like *"Is Mounjaro more effective than Wegovy in patients aged 40–50?"* can't be answered directly from the raw set
- Manual mappings break every time surveys change
- Cross-brand insights (Spring → GoLighter) get lost because there's no shared semantic layer

> [!warning] The structural point
> This isn't a "data quality" problem we can solve with a one-time cleanup script. The missing thing is a **continuous, clinician-validated layer** that turns raw input into standards-compliant output — automatically, every time new data arrives.

---

## 2 · The Data We Actually Have

**Source data** (from the hackathon handover):

- 1 CSV: `treatment_answer.csv` (~106 MB, 134,000 rows)
- Columns: `user_id`, `question_id`, `question_de`, `question_en`, `answer_value`, `answer_de`, `answer_en`, `product`, `brand`, `created_at`, `treatment_id`, `surrogate_key`, ~20 more

**What we materialised from it**

| Resource             |    Rows | What it holds                                                              |
| -------------------- | ------: | -------------------------------------------------------------------------- |
| `patients`           |   5,374 | Demographic identity · current_age · current_medication · tenure           |
| `bmi_timeline`       |   5,705 | BMI measurements over time, deduplicated                                   |
| `medication_history` |   8,835 | Rx segments with start / end / dosage                                      |
| `treatment_episodes` |   8,835 | Therapy episodes per patient                                               |
| `quality_report`     |   1,031 | Detected data-quality issues (BMI spikes, undocumented med switches, gaps) |
| `survey_unified`     | 133,996 | Every survey event with canonical answer + clinical category               |
| `semantic_mapping`   |      20 | Clinician-signed category mappings (FHIR types + medical codes)            |
| `fhir_bundle`        |   5,374 | Per-patient FHIR R4 bundle, exportable on demand                           |

**Brand and cohort distribution**

- 2 brands currently represented: **GoLighter** (obesity) and **Spring** (sexual health)
- Mounjaro · Wegovy · Saxenda patients in GoLighter
- Sildenafil · Tadalafil patients in Spring
- Cross-brand overlap: only **18 patients** appear in both → relevant cross-sell asymmetry

---

## 3 · How the Engine Works

> [!abstract] In one sentence
> AI does the **category discovery**, a clinician validates the **mapping**, deterministic code applies that mapping to **all data** continuously. The structured substrate is the output.

**Three concrete steps**

### Step 1 · Discovery (one LLM call)

- The ~4,500 question IDs are not classified one-by-one
- All unique patterns go to Claude in a single call: *"What clinical categories do you see in these questions?"*
- Output: 20 proposed categories with definitions (`BMI_MEASUREMENT`, `MEDICATION_HISTORY`, `SIDE_EFFECT_REPORT`, …)
- Each question ID is then assigned to a category
- **No hardcoded schema** — when a new question appears tomorrow, the system places it automatically

### Step 2 · HITL · Clinician sign-off

- Clinician sees a review surface: 20 mappings, each with the AI's proposal (FHIR Resource Type, LOINC / SNOMED / RxNorm code, display label)
- Three actions per mapping: **Approve · Override · Reject**
- No data leaves the substrate without this sign-off
- One-time effort per category — not per data point
- **Compliance-relevant**: every downstream data point is traceable back to a clinician-signed mapping decision

### Step 3 · Continuous unification

- Deterministic Pandas code applies the validated mapping across all 134k rows
- Output: the 8 structured tables (see §2)
- **Incremental**: when 10k new rows arrive tomorrow, only that delta is processed
- If a new unknown question ID appears, only that one round-trips through Step 1

> [!tip] Key principle
> AI on **structure** (discovery), code on **volume** (application). That's why a full run costs ~$0.10 in LLM calls and finishes in minutes — not why the substrate is cheap to operate, but why the architecture scales without re-prompting on every row.

---

## 4 · What We Built — As a Layer, Not an App

> [!important] Identity question
> UniQ is not "a tool" — it's a **layer between Wellster's raw data and everything that consumes it**.

**Concretely that means**

- Wellster's operational databases stay where they are
- UniQ continuously **materialises** a clinician-signed repository beside them
- That repository becomes the source of truth for **every downstream consumer**
- What sits on top:
    - **Analyst** (natural-language querying with validated artifact templates)
    - **FHIR export** (per-patient, ePA / EHDS compliant)
    - **Cross-cohort insights** (e.g. screening candidates between brands)
    - **Quality reporting** (operational data hygiene)
    - **AI-agent consumption** (yours or third-party)

**Difference vs. a normal data pipeline**

- A pipeline produces a one-time output
- A **layer is persistent + queryable + extensible + signed**
- Clinicians can also write back into it (annotations) — that's what turns the substrate into operational memory rather than a snapshot

---

## 5 · What Concretely Exists in the Repository

**8 resources, all joining through `user_id`:**

```
patients (5,374)
  ↓ user_id
  ├ bmi_timeline (5,705)
  ├ medication_history (8,835)
  ├ treatment_episodes (8,835)
  ├ quality_report (1,031)
  ├ survey_unified (133,996)
  └ fhir_bundle (5,374, exportable)

governance
  ├ semantic_mapping (20, signed)
  └ clinical_annotations (growing, write-back)
```

**Available per resource**

- API endpoint for read access (`GET /v1/...`)
- Snapshot CSV export (for BI / compliance / audit handoff)
- Structured relationship to other resources via foreign keys
- Status: `signed` / `queryable` / `exportable` / `monitored`

**Audit trail**

- Every data point in the substrate is traceable to (a) the source question ID and (b) the clinician who approved the mapping
- Visible per patient, per event, per mapping

---

## 6 · What to Show Live

**Order on the page**

|   # | Surface                                                            | Why this one                                                                                                            |
| ---:| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
|   1 | `/substrate-ready` — Repository Map                                | Proves "this is a layer, not a one-time export". Highlights: 8 resources, FK topology, API hooks, audit strip           |
|   2 | `/analyst` → `Open patient 383871`                                 | Shows what a consumer can do with the substrate. Highlights: multi-track timeline, click-to-audit-trail, add-note write |
|   3 | `/analyst` → `Find GoLighter screening candidates from Spring`     | Cross-brand insight emerging from the unified substrate. Highlights: 462 active candidates, ranked by clinical priority |
|   4 | `/review` *(optional)*                                             | The HITL sign-off surface. Highlights: 20 mappings, three actions per row                                               |

---

## 7 · Demo Patient as Anchor

> [!example] PT-383871 — representative Mounjaro case
> 44 years, female, GoLighter brand · 423 days tenure (Jan 2025 → Mar 2026) · Mounjaro escalation 2.5 mg → 5 mg · BMI 30.35 → 26.47 (−3.88) · 11 BMI measurements · 11 medication segments · **169 unique source fields collapsed into 1 structured record**

**Cross-brand cohort numbers (Spring → GoLighter screening)**

| Filter step                                       | Count |
| ------------------------------------------------- | ----: |
| Spring patients (any time)                        | 4,557 |
| With BMI ≥ 27 on file                             | 2,029 |
| With no GoLighter history                         | 2,014 |
| Active in last 180 days                           |   462 |
| High priority (BMI ≥ 30 + active in last 60 d)    |    60 |

---

## 8 · Open Questions — Where We Need Her Input

> [!question] Things we can't answer from outside Wellster

1. **Engineering reality** · what would be the simplest way to get at the live data — CSV drop, API pull, database connector?
2. **Compliance setup** · who inside Wellster needs to sign off on a data-sharing arrangement for a substrate like this? What DPA / AVV templates do you already have?
3. **Consumer priority** · would Wellster look first at the Analyst, at FHIR export, or at cross-cohort insights?
4. **GDNG activity** · is Wellster currently positioning to file data-use applications under the new Gesundheitsdatennutzungsgesetz, or is that still out of scope?
5. **Multi-modal data** · beyond survey data, do you also work with images, clinical notes, PDFs, wearables? (relevant for our roadmap)
6. **Clinician in the loop** · realistically, who would own the mapping sign-off — Medical Director (Jan?), an external clinician, both?
7. **Scaling** · beyond GoLighter + Spring, are there plans to bring MySummer or future brands into the substrate?

**What we're still validating internally**

- Whether the layer-identity (vs. use-case-identity) lands in a Wellster sales conversation
- Which of the four use cases (Cross-Sell · ePA Compliance · GDNG Activation · Quality Signal) is operationally most painful for Wellster
- Whether our "5-day onboarding without engineering" assumption is realistic in your environment

---

## 9 · What We Explicitly Don't Want

> [!danger] Boundaries
> Naming these proactively to remove them as concerns before they become questions.

- We **do not** replace Wellster's operational databases
- We **do not** build a black box that clinicians can't inspect
- We **do not** issue clinical recommendations or diagnoses (no MDR medical-device claim)
- We **do not** automate outreach or marketing decisions — those stay with Wellster Operations
- We **do not** move patient PII outside the substrate boundary without an explicit DPA

---

## 10 · Build Status (for context, not for showing)

> [!success] Live on `main` today
> Engine + HITL + substrate + Analyst + cross-brand artifact + FHIR export + clinician annotations
> 33 backend tests green · frontend type-check + lint clean · 134k Wellster rows productively unified

> [!todo] Not live, on the roadmap
> - Multi-modal loaders (notes · PDFs · images · wearables) — same engine, additional adapters
> - Substrate versioning (snapshot diff over time)
> - Real-time webhooks (`mapping.approved`, `quality.flagged`, …)
> - Partner marketplace for custom adapters

---

> [!note] After the call
> Drop notes back into this file under a new `## Post-call notes` section. Concrete pain points she named, words she used, follow-up commitments. Future prep iterations live from those notes, not from re-doing the strategic memory.
