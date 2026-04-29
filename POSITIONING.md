# UniQ — Strategic Positioning

_Last updated: 2026-04-25_
_Audience: Eren, Arturo, Zahra · for pitch night Spira Labs (late April 2026) and follow-on conversations_

---

## TL;DR — One paragraph

**UniQ is the Clinical Truth Layer.** We turn fragmented, schema-chaotic
healthcare data into one continuously updated, clinician-signed, FHIR-native
record that any consumer — analytics tools, FHIR partners, AI agents,
regulators — can act on without re-engineering. We are not a dashboard, not a
data warehouse, not an AI agent platform. We are the **clinical ground truth
layer** those things sit on. Architecturally we're **hybrid adaptive**:
pluggable loaders, a FHIR-grounded entity model, AI-driven semantic mapping
within it, HITL governance, and a service-led onboarding model that matches
how successful B2B software actually sells. The AI wave is our timing,
GDNG / ePA / EHDS are our regulatory tailwind, clinical truth
infrastructure is our identity.

**One-line for the pitch:**

> *"Every healthcare company has AI ambitions. None can deliver, because
> their data doesn't mean what its schema says it means. UniQ is the
> Clinical Truth Layer — discovered by AI, signed by clinicians, served in
> FHIR. Healthcare data, finally computable."*

---

## 1 · Why this positioning, why now

After the strategic deep-dive (Dandelion / Flatiron / Aily research + Eren's
intuition pull), three framing options remained on the table:

| Frame | Identity | Risk |
|---|---|---|
| A · RWD Asset Enabler | Wellster data → sellable asset to pharma (Dandelion model) | Conservative · needs consortium · methodologically narrow |
| B · Agent Trust Layer | Clinician-validated infra for healthcare AI agents | Novel but ties identity to current AI wave |
| **C · Clinical Truth Layer** | **The clinical ground-truth layer for any computational consumer** | **Broader TAM · timing-resilient · matches what is built** |

**We commit to Frame C.** Reasons:

1. **It is what we objectively built.** HITL, template-bound artifacts, FHIR
   export, handle-based agent loop — every architectural decision serves a
   ground-truth layer, not a single consumer. Calling ourselves "AI Agent
   Infrastructure" is *narrower* than reality.
2. **AI is the wave; clinical truth is the layer.** Every previous wave (BI,
   mobile, cloud) needed clean data. The next wave (AI agents) needs it
   harder, with stronger provenance. Whichever wave hits next still needs a
   trusted clinical truth layer. Identity should outlast wave timing.
3. **Larger TAM.** Frame B serves "AI agent buyers" (a segment).
   Frame C serves "anyone who needs to act on healthcare data" (the market).
4. **Defensible moat.** Schema-evolution + AI-discovery + HITL governance
   produces clinical ground truth. AI-agent-friendliness emerges from it as a
   side effect.

### Why "Clinical Truth Layer" specifically

- **"Truth" is not marketing — it's the literal output of HITL.** Every
  semantic decision passes through clinician sign-off. We produce *clinical
  ground truth*, not just structured data. "Ground truth" is also an
  established ML term, so the language inherits technical credibility, not
  hype.
- **"Layer" is universally understood.** Unlike "substrate" (correct but
  academic), every developer, investor, and operator knows what a layer is.
  No stumbling at the first sentence of the pitch.
- **No major company owns the term.** Salesforce launched "Einstein Trust
  Layer" for AI safety; that primes the audience to expect a *trust /
  truth layer* concept and recognise its weight, while leaving us
  distinctive (we are clinical, they are enterprise; we are truth, they
  are trust).

---

## 2 · The category we create

| Adjacent category | Examples | What they assume |
|---|---|---|
| Data integration | Mulesoft, Boomi | Schemas already known |
| ETL / ELT | Fivetran, dbt | Source data has clean structure |
| Data warehouses | Snowflake, BigQuery | Pre-modelled schemas |
| BI / semantic layers | Looker, Cube | Dimensional model exists |
| Healthcare data networks | Datavant, Health Gorilla | Records already structured |
| Clinical data aggregators | Flatiron, Dandelion | Aggregate, then someone abstracts |
| FHIR middleware | Redox, 1upHealth | Source is already FHIR-shaped |
| AI safety / trust layers | Salesforce Einstein Trust Layer | Enterprise data, not clinical |

**No category in this list automates the transformation of raw, evolving,
multilingual clinical data into clinician-signed, FHIR-native records.** That
is the gap we own.

The category we name and create:

> **The Clinical Truth Layer** — the layer that sits between chaotic
> healthcare source data and any downstream consumer (humans, APIs, AI
> agents, regulators), turning raw input into clinician-signed,
> FHIR-native ground truth that can finally be computed on.

We are upstream of every adjacent category. They consume our output.

---

## 3 · Why now — four forces converging

### A · The AI wave needs ground truth, not just structured data
Every healthcare org wants AI agents (triage, intake, follow-up, decision
support). The model is not the bottleneck. The data is. **No clinical AI
goes to production on raw EHR/survey data — the liability is too high.**
UniQ provides the truth mechanism (HITL + provenance + standards) that
makes deployment possible.

### B · Regulation turned FHIR into a compliance floor
- **Germany ePA**: mandatory since Jan 2026, sanctions live (up to 2 % billing
  deduction).
- **EU EHDS**: FHIR-based exchange across 27 member states by 2029.
- **US 21st Century Cures Act**: $1M/violation for information blocking.

Most telehealth platforms are 12–18 months from compliance. UniQ
shortens that to weeks. **FHIR is no longer a feature; it is a regulatory
floor we deliver as a default output.**

### C · GDNG turned data USE into a regulatory enabler
The German Health Data Use Act (Gesundheitsdatennutzungsgesetz, in force
since 2024) explicitly **enables** secondary use of anonymised health
data for research, precision medicine, and AI training — provided the
data is structured, clinician-validated, and audit-trail-backed.

Most telehealth platforms can't activate GDNG today because their data
fails the structural prerequisites. **UniQ's HITL workflow + FHIR-native
output + standards-coding is exactly the operational answer to GDNG.**
We don't just deliver compliance — we unlock a new revenue lane
(precision-medicine partnerships, RWD licensing) that GDNG opened but
no one has the data infrastructure to access.

This force is **positive** (enables monetisation), unlike A/B which are
negative (avoid penalty). Combined, they create a complete carrot-stick
regulatory environment.

### D · Telehealth growth makes manual coding unscalable
GLP-1 alone goes from $53.5B (2024) → $156.7B (2030); prescriptions from 680K
to 4.7M/month. Each prescription generates fragmented patient-reported data.
Manual coding, the current workaround, breaks at this scale.

For context: Wellster (our proof customer) operates at **2M+ patients ·
60M+ data points** across three brands. Their hackathon-shared sample we
worked with was ~0.27% of that. **The architectural challenge of working
at production scale is solved; the only remaining question is contract
scope.**

---

**Four forces hit in the same window. A trusted clinical truth layer is
required infrastructure for the next 5 years of healthcare data work,
regardless of which downstream wave dominates.**

---

## 4 · What we actually do — concrete, demoable, today

The truth layer has four sequential capabilities. They are not aspirations —
they are live on `main` and demoable in 3.5 minutes.

| # | Capability | Today's evidence |
|---|---|---|
| 1 | **Discover** the clinical structure from raw, schema-chaotic data | 134K rows → 238 unique questions → 26 categories, 2 API calls, ~$0.10 |
| 2 | **Govern** every semantic decision through clinician sign-off | `/review` HITL workflow · 20/20 mappings reviewed · audit trail per category |
| 3 | **Standardise** to FHIR R4 with ICD-10 / LOINC / RxNorm / SNOMED | 3,731+ FHIR resources exportable today |
| 4 | **Serve** any consumer — humans, APIs, AI agents, regulators | `/analyst` v2 (14/16 eval) · `/platform` API + Agents preview · per-patient FHIR export |

The narrative for the demo is precisely this 1→2→3→4 sequence. The new
**patient_record artifact** with the **truth-layer lineage ribbon** ("169 raw
fields → 1 unified record → 123/123 clinician-signed → 135 FHIR resources")
is the visual proof of all four capabilities collapsed into one screen.

---

## 4.5 · Architecture — Hybrid Adaptive (AI within FHIR-grounded templates)

A common question: *"Could the entity model itself be AI-discovered? Why
not generate the schema dynamically?"* Honest answer: **AI does
instance-level classification reliably; AI does NOT do schema-level
architecture reliably in regulated domains.** We commit to the
production-proven pattern.

### Three-layer architecture

```
Loaders (per data type, pluggable)        Core Engine (universal)            Artifact Templates (per output)
──────────────────────────────             ──────────────────────              ────────────────────────────
CSV Survey Loader      ┐                                                     ┌  cohort_trend
JSON FHIR Loader       │                                                     │  alerts_table
PDF Note Loader (NLP)  ├──→  raw rows → AI mapping → HITL → entity model →   │  table
DICOM Loader           │                                                     │  fhir_bundle
HL7 Stream Loader      │                                                     │  patient_record
Annotation API         ┘                                                     └  opportunity_list
```

### What the AI does (instance-level)
- Classify which raw `question_id` belongs to which clinical category
- Suggest FHIR resource type per discovered category
- Suggest medical codes (LOINC, ICD-10, RxNorm, SNOMED)
- Detect new patterns incrementally as schemas evolve

### What humans do (schema-level + governance)
- Confirm entity templates (FHIR R4 resources are the standard library)
- Approve / override / reject AI's semantic mappings via HITL workflow
- Define new entity templates only when genuinely needed (rare,
  clinician + engineer review)

### Why this beats "fully AI-driven" schema discovery
| Risk of fully-AI schema | Why it's a deal-killer |
|---|---|
| Inconsistent schemas across customers | Cross-customer learning advantage breaks |
| Schema hallucination in clinical context | Patient-harm liability |
| Non-FHIR output | Falls out of regulatory ecosystem |
| Non-reproducible runs | Unusable in production |
| HITL impossible at architecture level | Clinicians can't audit DB design |

### Why this beats "rigid hardcoded" platform
| Risk of pure hardcoding | Mitigation in our architecture |
|---|---|
| New data types = engineering project | Pluggable loader pattern (hours, not weeks) |
| Customer-specific schemas | YAML config drives column-mapping per customer |
| Schema drift breaks pipeline | Incremental classification handles new patterns |
| Locked taxonomy | AI extends the taxonomy, HITL approves additions |

### What this means for the customer onboarding model
This architecture matches how successful B2B software actually works:
**human-led setup, AI-augmented operation**. Snowflake, Databricks,
Salesforce, Glean, Harvey — all use the same pattern. We do too.

(See § 6.5 for the explicit Onboarding-Operation model.)

### What's hardcoded today vs. extension roadmap

| Component | Today | Phase 2 (3–6 mo) | Phase 3 (6–12 mo) |
|---|---|---|---|
| Loaders | 1 (Wellster CSV) | YAML-config + 3+ loaders (lab, notes, FHIR) | Stream + multi-modal |
| Entity model | 7 hardcoded tables | Pluggable FHIR R4 templates | AI-suggested template extensions, HITL-reviewed |
| AI mapping | Live, ~95% accuracy | Same | Same |
| HITL governance | Live, clinician-only | + engineer review for new templates | + automated regression checks |

---

## 5 · Reference companies — for trust, not for cloning

We name three. Each anchors a different part of the story.

### Flatiron Health — proves the pattern at scale
Acquired by Roche for **$1.9B (2018)**. Their core insight: **collapse
fragmented oncology data into clinician-validated records** for FDA-grade
real-world evidence. The key asset Roche bought was not the EHR software but
the curation operation — the same hybrid AI + clinician sign-off model we run.
Flatiron proved the pattern is worth nine zeros. _We apply the same pattern,
but to telehealth and AI-era consumers._

### Dandelion Health — proves the modern segment
**$15.9M Seed (2024+)**, Series-Seed operator with outsized presence: AHA AI
Lab partnership (Oct 2025), GLP-1 Data Library covering ~200K patients.
Demonstrates that structured clinical data is monetisable in the current
market climate. _We solve a problem they don't (truth layer for one
company's operational data, not aggregation across health systems for
research)._

### Aily Labs — proves the layer above
Munich-based, **$80M Series B (Nov 2025)** for AI Decision Intelligence on
enterprise data. Sanofi case study claims $300M in operational savings. _Aily
assumes structured data exists. We build the layer underneath that assumption
for healthcare. We are an Aily-class enabler, not a competitor._

**Pitch line that lands:**

> *"Flatiron proved this pattern is worth $1.9B in oncology. Dandelion proves
> structured RWD has new monetary upside in the GLP-1 era. Aily proves AI on
> structured enterprise data unlocks hundreds of millions in value. We are
> the Clinical Truth Layer that makes all three patterns possible — for
> telehealth, for the AI age."*

---

## 6 · Customer use cases — multi-consumer, single truth layer

The truth layer is reusable. Each customer segment activates a different consumer.

| Consumer type | Customer segment | Example use case enabled |
|---|---|---|
| **Internal analytics** | Telehealth (Wellster, Ro, Hims) | "BMI trajectory of Mounjaro cohort, weeks 0–24" |
| **Cross-brand cross-sell** | Multi-brand telehealth | "Spring patients with BMI > 27 not on GLP-1 — outreach list for GoLighter funnel" |
| **Operational quality** | Telehealth + CROs | "1,031 quality flags surfaced — undocumented med switches, BMI spikes" |
| **Patient deep-view** | Clinical operations + customer support | The new patient_record artifact (PT-383871's full timeline + audit trail) |
| **FHIR interop** | Any DiGA, ePA-bound platform | One-click FHIR Bundle export per patient |
| **GDNG-activated RWD** | Telehealth + pharma partnerships | Anonymised structured cohort data licensable for precision medicine, GDNG-compliant by default |
| **AI agents** | Internal teams + partners | Clinician-validated data layer for triage / cohort / decision-support agents |
| **Regulatory submission** | All regulated entities | Audit-trail-backed FHIR exports for ePA / EHDS / Cures Act |

This is what Martin's *"don't pick a use case, give them the platform"*
becomes when sharpened: **multiple consumers, one truth layer, immediate
value on day one for each of them.**

---

## 6.5 · Onboarding-Operation duality — how customers actually engage us

A critical positioning clarity that aligns with B2B reality (and matches
how Snowflake, Databricks, Glean, Harvey all sell):

```
ONBOARDING                    ┃          OPERATION
(one-time, days)              ┃          (continuous, automatic)
─────────────────             ┃          ────────────────────────
- Data team session           ┃          - Incremental AI classification
- Loader configuration        ┃          - HITL only for genuinely new patterns
- Entity-model mapping        ┃          - Substrate maintains itself
- Clinician sign-off (initial)┃          - Standards-coded outputs
- FHIR export validation      ┃          - APIs, exports, agents on demand
- First production substrate  ┃
                              ┃
"Set up the truth"            ┃          "The truth runs"
```

### Why this framing matters
- Honest about service component (no false "fully autonomous" promise)
- Matches B2B buying patterns (Salesforce / Snowflake / Databricks)
- Creates legitimate switching cost (deep onboarding = customer commitment)
- Justifies premium pricing (white-glove setup, not commodity SaaS)

### Concrete time investment (per customer)
- **Days 1–2**: data exploration session, loader config, initial pipeline run
- **Days 3–5**: clinician HITL review of discovered categories (≤2h total)
- **Days 5–7**: FHIR export validation, integration touchpoint definition
- **Day 7+**: substrate live; ongoing reviews ~30 min / month for new patterns

→ **Setup is ~5 days. Operation is autonomous.** That's the business model.

### Revenue implication
Two-component pricing emerges naturally:
- **Setup fee** (one-time, €15–50K depending on complexity)
- **Operation fee** (recurring, tier-based on patient volume / API usage / FHIR resources exported)

(Detailed pricing model is out of scope for this positioning doc; this
section just clarifies WHY a setup-and-operate model is correct, not arbitrary.)

---

## 7 · The moat — what makes us defensible

Four properties compound:

1. **Schema-evolution resilience.** Most platforms break on every survey
   update. UniQ's AI re-discovers structure incrementally; only NEW patterns
   need re-classification. Validated state persists across pipeline runs.

2. **Clinician governance embedded in the pipeline.** HITL is not a separate
   tool — it is the gate every semantic decision passes through, with full
   audit trail per data point. Regulators love this. AI consumers need it
   for liability protection.

3. **Standards-native output.** FHIR R4 + ICD-10 + LOINC + RxNorm + SNOMED out
   of the box. Compliance is a default, not a retrofit. Telehealth platforms
   facing ePA sanctions cannot achieve this in their own stack in time.

4. **Cross-customer learning.** Every customer added makes the AI classifier
   better at recognising new clinical patterns. Network effect — the truth
   layer gets sharper as more telehealth companies use it. **First-mover
   advantage is real.**

---

## 8 · The pitch narrative — 3.5 minutes, three jurors

### Audience model
- **Nico (Wellster CEO)** — already convinced the product works at hackathon,
  needs to be moved from "I want to use this" to "this is a category-creating
  company I want a stake in." Speaks his language: concrete, real, actionable.
- **Martin (Spira Labs)** — coach who told us "platform play, not specific use
  case". Wants to see we evolved his thinking into something sharper. The
  Clinical Truth Layer frame is his platform idea + one more level of
  clarity (platform was the *shape*, truth layer is the *identity*).
- **Third juror (Digital Health)** — likely investor / industry expert. Wants
  category creation, defensibility, market sizing, references.

### Structure (target: 3:30)

**Open · 30 s**
> *"Every healthcare company in 2026 has the same goal: deploy AI on patient
> data. None succeeds. Not because the AI is bad — the AI is great. Because
> their data does not mean what its schema says it means. At Wellster, the
> question 'do you have diabetes?' lives under 67 different IDs. That is the
> wall every healthcare AI runs into."*

**Problem deep-dive · 30 s**
- Visual: 134K rows → 238 unique questions → 26 categories
- *"Manual coding takes weeks. Costs millions. Breaks the moment a survey
  changes. This is not solvable with a data team — it is structurally
  impossible at scale."*

**Solution / what we are · 60 s**
- *"UniQ is the Clinical Truth Layer. Discovered by AI. Signed by clinicians.
  Served in FHIR."*
- Live demo:
  1. **Intake Console** (~15 s) — *"AI discovers the structure"*
  2. **Review pivot approval** (~15 s) — *"Clinician signs off on every semantic decision"*
  3. **Substrate-Ready** (~10 s) — materialising metrics
  4. **Patient Record artifact** (~20 s) — *"Open patient 383871"* → lineage ribbon,
     BMI trajectory, audit-trail panel, FHIR export

**Reference companies · 30 s**
- *"Flatiron proved the pattern is worth $1.9B for oncology. Dandelion does
  it for GLP-1 RWD. Aily proved AI on structured data is worth $80M Series
  B in six months. We are the truth layer underneath all three — the
  clinical ground truth for telehealth and the AI era."*

**Why now · 20 s**
- Four forces in the same window:
  - AI wave needs ground truth (negative pressure: liability)
  - ePA / EHDS / Cures Act mandate FHIR (negative: penalty)
  - **GDNG enables data USE for precision medicine (positive: revenue unlock)**
  - GLP-1 wave makes manual coding unscalable (negative: cost)
- *"This is the 18-month window. Whoever is the trusted truth layer at
  scale by 2027 defines the category."*

**The opportunity / close · 30 s**
- Wellster as proof point ongoing; Platform-tab as evidence the truth layer
  is multi-consumer
- *"We don't ask you to commit to a use case we don't understand. We make
  your data computable. Your team builds anything on top — analytics, FHIR
  exports, AI agents, partner APIs. One truth layer, infinite consumers."*
- One closing soundbite (see § 9)

### What we cut from the demo
- **Story page Lattice animation**: too slow, save 15 s
- **Platform Agents-tab interactive configurator**: mention in 5 s, do not
  click through. Save 25 s.
- This frees ~40 s for the patient_record artifact moment, which is the
  single most pitch-defining surface we have.

---

## 9 · Slogans, soundbites, hooks

### Primary positioning sentence (use everywhere)

> **UniQ is the Clinical Truth Layer.**

### Pitch tagline candidates — pick one for the deck

1. *"From schema chaos to clinical truth."*
2. *"Healthcare data, finally computable."*
3. *"The ground-truth layer for the healthcare AI era."*
4. *"Clinical truth — discovered by AI, signed by clinicians, served in FHIR."* **← LEAD**

Lead candidate: **#4** — names the moat (clinical truth), describes the
method (AI + clinicians + FHIR), reinforces the category name in three
beats. Hardest to dismiss as buzzwords because every clause maps to a
verifiable product capability.

### Pitch hooks — drop into Q&A or follow-up

- *"Healthcare AI fails on data, not models. We fix the data."*
- *"FHIR is now law in Germany. Most platforms are 12 months from ready. We
  make any data FHIR-ready in weeks."*
- *"Flatiron unified oncology. We unify telehealth. Dandelion unifies
  research data. We unify operational data. Different customers, same
  truth-layer logic."*
- *"Your team builds the use case — analytics, agents, exports. We build
  the data foundation that makes them all possible."*

### Memorable visual to anchor the pitch
The truth-layer diagram — three layers, top-down:
```
       AI agents · BI tools · FHIR APIs · regulators · partners
                            ▲
                            │
                ┌───────────┴───────────┐
                │  UniQ Truth Layer      │
                │  • Discovered (AI)     │
                │  • Signed (HITL)       │
                │  • FHIR-native         │
                └───────────▲───────────┘
                            │
              Raw, fragmented, schema-evolving data
```

If the jury remembers ONE thing, it is this picture.

---

## 10 · Open decisions before pitch night

| # | Decision | Owner | Status |
|---|---|---|---|
| 1 | ~~Final tagline~~ — locked: § 9 #4 *"Clinical truth — discovered by AI, signed by clinicians, served in FHIR"* | ✓ done | — |
| 2 | ~~Confirm Clinical Truth Layer frame with Martin~~ | ✓ done | Martin: "good, sharper than before" |
| 3 | ~~Build BMI-27 / cross-brand opportunity SQL~~ | ✓ done | Insight surfaced (Spring patients with BMI > 27) |
| 4 | ~~Build BMI-27 opportunity_list artifact (new family)~~ | ✓ done | 456 active Spring → GoLighter screening candidates; dedicated artifact |
| 5 | Build clinician-annotation overlay on patient_record | Eren | Next slice (Living Substrate write-back) |
| 6 | Wellster sync with Irena Medlin + Maria Chernevich (intro via Martin) | Eren | This week |
| 7 | Decide whether to demo Platform-tab at all (recommend cut for time) | Eren | Day before pitch |
| 8 | Practice run with repository map + patient_record + opportunity artifacts in flow | Team | This week |
| 9 | Optional: 30-min validation call with one other telehealth (Ro / Hims / Heliva / Kry) | Eren | This week |

---

## 11 · What this positioning rules OUT

To stay disciplined, the truth-layer frame **excludes**:

- Building customer-specific dashboards (Wellster's clinical UI = customer's
  job, not ours)
- Selling our own consumer-facing analytics product (Aily's territory)
- Becoming a data marketplace / RWD broker (Dandelion's territory — possible
  later, not phase 1)
- Vertical-specific AI agents (triage, intake, etc. = customer or partner
  builds these on top of the truth layer)

These are tempting because they are concrete and demoable, but each pulls us
out of the truth-layer identity into being one specific consumer of our own
truth layer. **The discipline is: stay upstream.**

---

## 12 · Why this is McKinsey-rigorous, not pitch theatre

Five falsifiability tests this positioning passes:

1. **TAM defensibility**: every category we list in §2 needs structured
   clinical data as input. None of them solve the discovery problem. Our TAM
   is the union of every adjacent category, not a slice.
2. **Customer evidence**: Wellster (proof point on 5,374 patients of
   their 2M+ population, with leadership publicly aligned on the problem
   space), competing hackathon teams (validated the data problem is real),
   GLP-1 wave (timing).
3. **Reference company logic**: not "we are the next Flatiron", but "we
   apply Flatiron's proven pattern to a different segment with a different
   buyer". Comp-anchored, not aspirationally compared.
4. **Architectural defensibility**: AI-augmented within standards-grounded
   templates (FHIR R4) — the production-proven enterprise pattern. Not the
   "fully AI-driven schema" hype that fails clinical liability tests.
5. **Regulatory triangulation**: ePA / EHDS / Cures Act create the
   compliance floor (negative pressure), GDNG creates the data-use enabler
   (positive pressure). We sit at the intersection — same product solves
   both.

If any of these five falls, the positioning falls. None has fallen yet.

---

## 13 · Recent strategic refinements (post-Martin call, 2026-04-25)

Conversations and observations that further sharpened the positioning since
the initial draft. Captured here so future readers can trace the evolution.

- **Martin call (2026-04-24)**: confirmed Clinical Truth Layer frame
  lands. Pushed for "living substrate" (clinician contributions, not just
  one-shot pipeline) — addressed by patient_record annotation overlay
  (in build) and the Onboarding-Operation framing in §6.5.
- **Wellster intro received**: Martin connected Eren with Irena Medlin
  and Maria Chernevich (Wellster Product Owners). See `WELLSTER_BRIEFING.md`
  for the operational follow-up.
- **Wellster co-founder DMEA post (2026-04-25)**: Wellster leadership is
  publicly framing exactly our problem space — "Datenschatz aus der Praxis",
  "GDNG mutig anwenden", "Datennutzung für Präzisionsmedizin",
  "bürokratische Überregulierung dürfen Startups nicht ausbremsen". Our
  positioning IS the solution they describe; vocabulary fully absorbed
  into the briefing.
- **Datost YC announcement (2026-04-16)**: "AI data analyst with semantic
  layer" thesis is now YC-funded for general business data. Confirms the
  semantic-layer-thinking is hot. We are healthcare-specific upstream of
  Datost-class tools.
- **Architecture clarity (this doc, §4.5)**: hybrid adaptive (AI within
  FHIR-grounded templates) committed as the right answer vs. fully-AI or
  hardcoded extremes.
- **Onboarding-Operation duality (§6.5)**: B2B-realistic, premium-
  positioned, switching-cost-friendly model committed.

---

_End of strategic positioning document. Living artifact — update as more
conversations land and the pitch evolves._
