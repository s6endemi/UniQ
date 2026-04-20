# UniQ — COMPLETE CONTEXT DOCUMENT
# For any AI to pick up and work strategically + technically from here

---

## WHO I AM

Eren Demir, 23, AI Engineer and founder/CEO of Previa Health (AI-powered MSK prevention startup, €300K pre-seed raised). UniQ is a separate project from a healthcare hackathon — Previa remains my primary venture. UniQ emerged from the Wellster x med-dev Digital Health Hackubator in Munich (March 2026) and is now in a 4-week Spira Labs incubation track leading to an investor pitch night in late April 2026.

## THE TEAM

- Eren Demir — AI Engineer, technical lead, product vision, built the entire pipeline
- Arturo Soria Garcia — Business Intelligence at Wellster (insider perspective, data access)
- Zahra Hadipour — MSc Global Public Health, Biomedical Engineering background

---

## THE PRODUCT: UniQ

### One sentence
An AI engine that takes fragmented healthcare data, automatically discovers its clinical meaning, unifies it into structured standards-compliant records, and provides an API/platform for anyone in the organization to build use cases on top.

### What it does (proven, built, working)
1. Takes raw healthcare data (currently questionnaires, expandable to any structured data type)
2. Extracts unique data patterns (e.g., 134K rows → 238 unique questions)
3. AI classifies them into clinical categories (1 API call, no hardcoded rules)
4. Human-in-the-loop validates the proposed taxonomy
5. AI normalizes answer variants across languages (416 variants → 164 canonical labels)
6. Outputs unified analytical tables (patients, treatments, bmi_timeline, medications, quality_report)
7. Exports as CSV, JSON, or FHIR R4 with ICD-10, SNOMED CT, RxNorm, LOINC codes
8. Runs incrementally — validated taxonomy persists, only NEW data gets classified

### Key metrics (proven)
- 3 datasets tested: 12K → 23K → 134K rows, zero code changes
- 2 brands (GoLighter obesity + Spring sexual health), 5,374 patients, 19 medications
- 4,553 question IDs → 26 clinical categories
- 2 API calls total, ~$0.10 cost
- 1,010 quality alerts found (819 undocumented med switches, 147 BMI gaps, 34 BMI spikes)
- 3,731 FHIR R4 resources generated

### What we're building now (for pitch night)
Three-layer product:

**Layer 1: UniQ Engine (built)**
Continuous data unification. Not a one-time cleanup — runs permanently as new data flows in. When surveys change, new products launch, or new markets open, UniQ automatically adapts.

**Layer 2: Medical AI Analyst / Chatbot (building)**
Standard feature on top of unified data. Anyone types a clinical question, gets an evidence-based answer WITH dynamic visualizations (charts, graphs). LLM translates natural language → SQL on unified tables → returns data → generates text answer + chart. Example: "How does BMI change over time for Mounjaro vs Wegovy?" → line chart + clinical interpretation.

**Layer 3: API + Sandbox (building)**
FastAPI endpoints on unified data. Customers build their own use cases:
- GET /patients/{id} → unified patient record
- GET /patients/search?medication=X&age=Y → filtered cohort
- POST /query → natural language → answer
- GET /export/{id}/fhir → FHIR Bundle on demand

Example agent: a script that calls /patients/search?bmi_gap=true weekly and sends email summaries. We show this as proof that any use case can be built on top.

### The strategic insight (from Spira Labs coach Martin)
Don't try to guess the customer's use case. Build the platform and let THEM build what they need. Like Stripe for payments or Twilio for communications — we provide the data infrastructure, customers create their own solutions. The chatbot is ONE showcase use case, not the whole product.

---

## THE CUSTOMER: WELLSTER HEALTHTECH GROUP

- Germany's #1 digital patient company
- €30M revenue, 2M+ patients, 7 years since launch, NPS 75
- 3 brands: GoLighter (obesity — Wegovy, Mounjaro, Saxenda), Spring (sexual health — Sildenafil, Tadalafil), MySummer (contraception)
- Fully integrated ecosystem: own telemedicine entity, own online pharmacy + compounding lab
- 12 indications, 60 SKUs, 750K+ direct-to-patient treatments
- Almost entirely self-pay (patients pay out of pocket)
- Patient journey: Access platform → Expert education → Doctor consultation → Treatment fulfillment → Follow-up

### Wellster's data problem (validated)
- Surveys evolve constantly — same clinical question exists under 67+ different IDs
- Same answer ("normal blood pressure") stored in 9+ text variants across German/English
- Data fragmented across brands (GoLighter, Spring, MySummer use different systems)
- Historical analysis impossible — can't track treatment effectiveness over time
- Current workaround: manual spreadsheet mapping by medical coders, takes weeks, breaks on every update
- Wellster described this as "nice to have, never essential" — important context for business case validation

### Wellster team involved
- Supporters: Irena (Product Owner), Maria (Product Owner), Alex (Head of Engineering), Claudio (Product Lead), Jan (Medical Director)
- Participants: Arturo (Data Scientist — our teammate), Nauman (Senior Full Stack Developer)

---

## COMPETITIVE LANDSCAPE (19 companies analyzed)

### The structural gap
The entire healthcare data ecosystem assumes data arrives in recognized formats. Nobody automates the transformation of raw, evolving, multilingual questionnaire/survey data into those formats. UniQ is the missing upstream layer.

### Data integration platforms
- Arcadia — $198M raised, Nordic Capital acquired. EHR/claims aggregation. No survey data, no AI discovery.
- Redox — $95M raised. API middleware. Pure plumbing, doesn't interpret content.
- Health Gorilla — $80M raised. Clinical data network. Structured records only.
- Datavant — $7B valuation. Privacy-preserving data linkage. Links, doesn't structure.
- 1upHealth — $80M raised. FHIR-first for payer CMS compliance. Converts structured formats only.
- Particle Health — $49M raised. Patient record API. Aggregates existing, doesn't transform raw.

### Clinical trial platforms
- Medidata — acquired for $5.8B. eCRF/EDC. Predefined schemas, no AI discovery.
- Veeva — $28.9B market cap. Clinical data mgmt. Schema-bound.
- IQVIA — $16.3B revenue. Services-heavy, no self-service questionnaire standardization.

### Healthcare NLP
- Amazon Comprehend Medical — ~$0.85/chart. English-only, known entities, no category discovery.
- Google Healthcare NLP — Clinical documents only, no survey versioning.
- John Snow Labs — Pre-trained models, no category discovery from scratch.

### Survey tools
- REDCap — 5,900+ institutions. Captures data, zero standardization across versions. Prime INPUT for UniQ.
- Qualtrics — Acquired Press Ganey for $6.75B. No medical coding, no FHIR.

### Key reference companies (for pitch — prove the model works)
- **Flatiron Health** — unified fragmented oncology data from 200+ clinics into one platform. Acquired by Roche for **$1.9B**. Same pattern: fragment → unify → intelligence.
- **Dandelion Health** — unifies multimodal RWD (clinical notes, images, waveforms) for research. Funded, GLP-1 data library, AHA partnership. Same market (GLP-1/obesity) as Wellster.
- **Aily Labs** — $80M raised, Munich. Enterprise Decision Intelligence. 15,000 Sanofi employees use it daily. Saved Sanofi $300M. Key insight: Aily assumes data is clean. In healthcare it's not. UniQ is the layer UNDERNEATH Aily.

### UniQ's position
Upstream infrastructure. Complementary to the entire ecosystem. Our output feeds into every platform above. We don't compete — we enable.

---

## MARKET SIZING

| Level | 2025 | 2030 |
|-------|------|------|
| TAM | ~$7.5B | ~$15B |
| SAM | ~$900M | ~$1.8B |
| SOM (addressable) | $23-70M | — |
| Year 1 realistic | €250K-750K ARR | — |

### Key tailwinds
- GLP-1 market: $53.5B (2024) → $156.7B (2030). Prescriptions: 680K→4.7M/month
- ePA Germany: FHIR mandatory, sanctions active since Jan 2026 (up to 2% billing deduction)
- EHDS: FHIR-based exchange mandated across 27 EU states by 2029
- US: $1M/violation for information blocking (21st Century Cures Act)
- 80% of medical data remains unstructured
- Data quality is #1 barrier for healthcare AI adoption (57% of organizations)

---

## BUSINESS MODEL

### Pricing (corrected from hackathon)
Hackathon: $0.10 per 134K rows = unsustainable. Corrected to value-based:

| Tier | Monthly | Annual | Target |
|------|---------|--------|--------|
| Startup | €1,500-3,000 flat | €18-36K | Small telehealth, DiGA |
| Growth | €3,000-10,000 + overage | €36-120K | Mid-size telehealth, CROs |
| Enterprise | Custom | €50-200K + volume | Hospital groups, large CROs |

Plus per-record fee: €0.10-0.50 per coded patient record.

### ROI argument
Manual coding: €1-3/chart. Amazon Comprehend: ~€0.85 (NER only). UniQ: €0.10-0.50 (full pipeline + FHIR). = 75-95% cost savings. Wellster at 2M patients = €200K+ contract.

### GTM
Telehealth first (30-90 day sales cycle) → CROs (2-4 months) → DiGA companies → Hospital groups (6-18 months).

---

## EXPANSION PATH

| Priority | Use case | Market | Why UniQ fits |
|----------|----------|--------|---------------|
| Now | Telehealth data unification | $200-500M | Proven with Wellster |
| 6mo | Clinical trial eCRF reconciliation | $300M-1B | Schema evolution = core capability. $20B/yr amendment costs |
| 9mo | PRO harmonization | $150-500M | Cross-language normalization. PHQ-9 in 100+ languages |
| 12mo | Insurance form standardization | $200-800M | 9B+ US claims/yr, 42% rejection from data errors |

---

## REGULATORY POSITION

- **GDPR:** Applies. We're data processor (Art 28). Manageable with DPAs. Taxonomy (structural intelligence) is separable from personal data.
- **EU AI Act:** Strong case for non-high-risk. Narrow procedural task + human-in-the-loop. Documentation needed before Aug 2026.
- **MDR:** Almost certainly not a medical device. We structure data, don't diagnose. Formal opinion recommended (€5-15K).
- **FHIR R4:** Not a feature — legally mandated in DE (ePA), EU (EHDS by 2029), US (Cures Act).

---

## TECHNICAL ARCHITECTURE

### Data flow
Raw data → Auto-Discovery (LLM identifies what each column/field means clinically) → Human validates → Continuous Unification (deterministic code applies mappings to all data) → Unified Analytical Tables → Export Layer (CSV, JSON, FHIR on demand) → API Layer → Customer use cases

### Key principle: AI on structure, code on volume
LLM only processes unique patterns (~238 from 134K rows). Deterministic code applies mappings to full dataset. That's why it costs $0.10 and takes minutes.

### Unified format vs FHIR
Internal format = flat analytical tables optimized for queries and intelligence. FHIR = export format generated on demand when data needs to leave the system. Like database vs PDF — you store in the database, export as PDF when needed.

### Tech stack
- Python 3.10+, Pandas for data processing
- Claude/Opus API for classification and reasoning (MedGemma as on-premise option for GDPR)
- FastAPI for API endpoints
- Streamlit + Plotly for demo frontend with dynamic charts
- FHIR R4 builder for standards-compliant export

### MedGemma context
Google's open-source medical AI model (4B/27B). Trained on EHR, clinical text, medical images. Runs locally = GDPR advantage. Not our core differentiator but a technology option. In pitch: mention capability ("runs on-premise, no patient data leaves infrastructure"), don't lead with model name.

---

## PITCH NIGHT STRATEGY

### Judging criteria (optimize for these)
1. Solution Clarity & Feasibility — **12 POINTS** (highest)
2. Problem/Need Identification — 9 points
3. Research & Understanding — 9 points
4. Originality & Innovation — 6 points
5. Usage of Wellster Data — 6 points
6. Presentation & Communication — 6 points
7. Bonus (working demo) — 5 points

### Pitch structure (the "STOP" framework from Martin)
1. Open with Arturo's use case list — all the different problems various Wellster departments have
2. "STOP — before any of this is possible, step 1: the data needs to be unified"
3. Show UniQ unification: Chaos → Order (before/after on real Wellster data)
4. Live demo: Chatbot query with dynamic visualization on real Wellster data
5. Show API + example agent: "This is one use case. Here's the platform to build any use case"
6. Competitive validation: "Flatiron proved this for oncology ($1.9B). Dandelion for cardiology. We're applying the same model to telehealth — the fastest growing, most underserved segment"
7. Close: "We don't sell you a solution to a problem we don't fully know. We give you the platform and tools to solve it yourself."

### Key pitch lines
- "We don't just clean data. We turn it into the smartest person in the room."
- "Flatiron was acquired for $1.9B doing this for oncology. Dandelion is doing it for cardiology. The telehealth segment — the fastest growing in healthcare — has no one doing this. Until now."
- "Not a dashboard. A clinical brain for your organization."
- "Our pipeline doesn't break when your surveys change next month. It adapts automatically."

### What went well at hackathon (keep)
- Data structuring + FHIR: "super clear," "foundation to other layers"
- Originality: novel AI-driven approach recognized
- Usage of Wellster data: "super adapted to the Wellster case"
- Scalability: proven across 3 datasets

### What to fix from hackathon (critical)
- Presentation: "very difficult to follow," "3 min in problem space too long," "weak presentation"
- Business model: "who pays and how much" — now restructured to value-based
- GDPR: compliance gap addressed
- Data scope: "what about images?" — addressed with data-type-agnostic framing

---

## COMPETING TEAM: IMPACTINFO

Dr. Janet Brinz, Lars Lowinski, Damià Vicens Ramis, David Vogenauer. Built a dashboard that consolidates fragmented patient data into a unified view with a timeline interface for doctors. Interdisciplinary team (dentistry, medical engineering, quantum computing, data engineering).

### Our assessment
- Easier to understand and demo (visual dashboard)
- But: doesn't solve the fragmentation problem, just displays it prettier
- No AI-driven category discovery, no schema evolution handling
- "What happens when surveys change?" — no answer
- Our tech moat is deeper but harder to show in 5 minutes
- Counter-strategy: build the chatbot with live visualizations = same visual wow + deeper technology

---

## OPEN QUESTIONS STILL BEING VALIDATED

1. Is the unified data alone worth recurring payment, or does it need the intelligence layer?
2. Is Wellster pursuing Krankenkassen reimbursement? (Biggest potential business case)
3. What does Wellster's tech team actually need day-to-day? (Arturo validating)
4. Beyond questionnaires — what other Wellster data sources can we access?
5. Is the platform/API model (let customers build their own use cases) more compelling than a specific pre-built solution?

---

## KEY CONTACTS

- Martin (Spira Labs coach) — weekly calls, strategic guidance
- Arturo Soria Garcia — Wellster insider, data access, tech team relationships
- Wellster tech contacts: Irena (Product Owner), Alex (Head of Engineering), Claudio (Product Lead)
- Hackathon organizers: Youye Song MBA, Leonard Rinser, Claudio Kusnitzoff Diaz

---

## IMPORTANT FRAMING NOTES

- Previa Health is Eren's primary venture. UniQ should not look like a pivot.
- UniQ is not "just questionnaires" — the method is data-type agnostic, questionnaires were the proof of concept.
- Don't oversell what doesn't exist yet. The pipeline is proven. The chatbot and API are being built.
- When discussing MedGemma: lead with capability (on-premise, GDPR-friendly medical AI), not model name.
- The platform/API framing (from Martin) resolves the "which use case?" question — we don't need to choose one.
- Show successful companies (Flatiron $1.9B, Dandelion, Aily $80M) to prove the model works, not to compare scale.

Codex will review your output once you are done.