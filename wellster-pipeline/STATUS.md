# UniQ — Unified Questionnaire Intelligence

## STATUS QUO — What We Built, What It Does, Why It Wins

---

## THE PRODUCT IN ONE SENTENCE

An AI engine that takes fragmented questionnaire data from any healthcare platform, automatically discovers clinical categories, normalizes answers across languages and survey versions, and exports unified, medically coded data in FHIR R4 format — ready for EHR integration, analytics, and regulatory reporting.

---

## THE PROBLEM (McKinsey framing)

### Situation
Wellster Healthtech operates 3 telehealth brands (GoLighter/obesity, Spring/sexual health, MySummer/contraception) serving 750K+ treatments across 12 indications. Every brand collects patient data through medical questionnaires at every touchpoint — initial consultation, follow-ups, re-orders.

### Complication
Survey questions change constantly — new IDs, reworded text, different answer formats, language variants. The same clinical question "Do you suffer from pre-existing conditions?" exists under **67 different question IDs**. "Normal blood pressure" is expressed in **9 different text variants** across German, English, and survey versions.

Result: longitudinal patient analysis is impossible. Wellster cannot answer basic clinical questions:
- "Is Mounjaro more effective than Wegovy for patients aged 40-50?"
- "What's our side effect profile across medications?"
- "Which patients are dropping off treatment?"

### Current workaround
Medical coders manually map questions in spreadsheets. Takes weeks. Always behind. Breaks every time surveys update.

### Resolution
UniQ automates the entire process. AI discovers the clinical structure, humans validate, the system normalizes everything into queryable, medically coded data.

---

## THE SOLUTION (YC framing)

### What it does
1. **Upload** any questionnaire CSV/TSV — auto-detects format, columns, structure
2. **AI classifies** all questions in a single API call — discovers clinical categories from scratch, no hardcoded rules, no predefined schema
3. **Human reviews** the proposed taxonomy — critical for medical data compliance
4. **AI normalizes** all answer values — 416 variants become 164 canonical labels (HYPERTENSION, NORMAL, CONTINUOUS, OCCASIONAL_NAUSEA...)
5. **System exports** unified data as CSV, JSON, or **FHIR R4** with proper medical codes (ICD-10, SNOMED CT, RxNorm, LOINC, ATC)

### What makes it different
- **Zero hardcoded rules** — the AI discovers categories from the data itself
- **Human-in-the-loop** — AI proposes, human validates. Non-negotiable for health data.
- **Incremental** — validated taxonomy persists. Next upload only classifies NEW questions. Cost: ~$0.05 per run.
- **Multi-domain** — same engine handles obesity AND erectile dysfunction data without any code changes
- **Medically coded** — output uses real ICD-10, SNOMED CT, RxNorm, LOINC codes. Not custom labels.

### Who pays
Any organization where questionnaires evolve and historical comparability breaks:

| Customer | Pain | Willingness to pay |
|---|---|---|
| **Telehealth platforms** (Wellster, Ro, Hims) | Can't track patient outcomes over time | High — directly impacts clinical quality metrics |
| **Clinical trial CROs** (IQVIA, Parexel) | Protocol amendments break eCRF data continuity, delays FDA submission | Very high — weeks of delay = millions lost |
| **Insurance / Krankenkassen** | Can't aggregate patient-reported outcomes across providers | High — bad reimbursement decisions cost millions |
| **Hospital groups post-merger** | Different intake forms for years, no unified patient records | Medium-high — compliance + clinical risk |

### Business model
SaaS per data volume. Entry: self-serve upload + export. Upsell: managed taxonomy validation, custom analytics, FHIR integration consulting.

---

## WHAT WE PROVED — THE NUMBERS

### Dataset 1: GoLighter 3-month (initial build)
- 12,400 rows → 677 question IDs → 84 unique texts → **15 categories**
- Validated pipeline design, answer parsing, quality checks

### Dataset 2: GoLighter 15-month (scale test)
- 23,076 rows → 1,639 question IDs → 177 unique texts → **18 categories**
- Pipeline automatically discovered 2 new categories (blood pressure, exercise)
- **Zero code changes** from Dataset 1

### Dataset 3: GoLighter + Spring multi-brand (production test)
- **133,996 rows** → **4,553 question IDs** → 238 unique texts → **26 categories**
- **5,374 patients**, **8,835 treatments**, **19 medications** (Mounjaro, Wegovy, Sildenafil, Tadalafil, Viagra...)
- **2 brands** (GoLighter + Spring), **2 indications** (Obesity + ED)
- AI discovered **7 new categories** for ED domain (SYMPTOM_ASSESSMENT, SYMPTOM_DURATION, DIAGNOSTIC_HISTORY...)
- **2 API calls total** (1 for question classification, 1 for answer normalization)
- **99.9% deterministic parsing**
- **1,010 quality alerts** found (819 undocumented med switches, 147 BMI gaps, 34 BMI spikes, 7 subscription lapses)

### FHIR Export
- **3,731+ FHIR R4 resources** generated automatically
- Patient, Observation (BMI with LOINC), MedicationStatement (RxNorm + ATC), Condition (ICD-10 + SNOMED CT), AdverseEvent (SNOMED CT)
- Interoperable with any EHR system globally

---

## TECHNICAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│   CSV / TSV / Excel — any questionnaire export                  │
│   Auto-detected format, columns, structure                      │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     UniQ ENGINE                                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ LOAD — auto-detect CSV/TSV, parse dates, clean orphans   │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CLASSIFY — AI discovers categories (single API call)     │  │
│  │                                                          │  │
│  │  taxonomy.json exists?                                   │  │
│  │    YES → incremental: classify only NEW questions        │  │
│  │    NO  → discovery: AI proposes taxonomy from scratch    │  │
│  │                                                          │  │
│  │  Human-in-the-loop: review, merge, validate              │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ NORMALIZE ANSWERS — AI maps variants to canonical labels │  │
│  │                                                          │  │
│  │  "Normal - Between 90/60 - 140/90"  →  NORMAL            │  │
│  │  "Normal - Zwischen 90/60 - 140/90" →  NORMAL            │  │
│  │  "Bluthochdruck, Ramipril 5mg"      →  HYPERTENSION      │  │
│  │                                                          │  │
│  │  Single API call for all categories                      │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ UNIFY — build analytical tables                          │  │
│  │  patients.csv, bmi_timeline.csv, treatment_episodes.csv  │  │
│  │  medication_history.csv, survey_unified.csv              │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ QUALITY — cross-temporal clinical checks                 │  │
│  │  BMI gaps, BMI spikes, undocumented med switches,        │  │
│  │  subscription lapses, suspicious values                  │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ MEDICAL CODING — map to international standards          │  │
│  │  ICD-10, SNOMED CT, RxNorm, LOINC, ATC                  │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ EXPORT — CSV, JSON, FHIR R4 Bundle                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌────────────────┬──────────────────────┬──────────────────────────┐
│  Analytics     │  EHR Integration     │  Regulatory Reporting    │
│  (BI tools,    │  (FHIR R4 → any      │  (ICD-10 coded           │
│   dashboards)  │   hospital system)   │   outcomes data)         │
└────────────────┴──────────────────────┴──────────────────────────┘
```

---

## PROJECT STRUCTURE

```
wellster-pipeline/
├── data/raw/                          # Raw input files
│   ├── treatment_answer.csv           # 134K rows, GoLighter + Spring
│   └── ...
├── output/                            # All generated artifacts
│   ├── survey_unified.csv             # Unified survey with canonical labels
│   ├── patients.csv                   # Patient profiles
│   ├── bmi_timeline.csv               # Longitudinal BMI
│   ├── treatment_episodes.csv         # Treatment lifecycle
│   ├── medication_history.csv         # Medication journey
│   ├── mapping_table.csv              # Question ID → category
│   ├── quality_report.csv             # Data quality issues
│   ├── taxonomy.json                  # Validated category definitions
│   ├── answer_normalization.json      # Answer → canonical mapping
│   └── fhir_bundle.json              # FHIR R4 export
├── src/
│   ├── load.py                        # Data loading + inspection
│   ├── classify_ai.py                 # AI question classification engine
│   ├── normalize.py                   # Format-based answer parsing
│   ├── normalize_answers_ai.py        # AI answer normalization
│   ├── unify.py                       # Build analytical tables
│   ├── quality.py                     # Data quality checks
│   ├── medical_codes.py               # ICD-10, SNOMED, RxNorm, LOINC mappings
│   ├── export_fhir.py                 # FHIR R4 bundle export
│   └── demo.py                        # Streamlit product demo
├── config.py                          # Configuration + .env loader
├── pipeline.py                        # Orchestrator
├── requirements.txt                   # Dependencies
├── .env                               # API key (gitignored)
└── .gitignore
```

---

## JUDGING CRITERIA ALIGNMENT (53 points total)

### 1. Solution Clarity & Feasibility — 12 POINTS (HIGHEST)

**What we deliver:**
- Working end-to-end pipeline processing 134K rows across 2 brands
- Production-grade code: type hints, error handling, incremental processing, intermediate saves
- Real FHIR R4 export with medical codes — deployable into existing healthcare infrastructure
- Streamlit demo with 4 views: Dashboard, Category Explorer, Patient Record, Process & Export

**Deployment path:** Docker container, scheduled pipeline runs, Streamlit or Retool for the frontend, FHIR endpoint for EHR integration. Could be production-ready in 4-6 weeks.

### 2. Problem/Need Identification — 9 POINTS

**The problem is real and quantified:**
- Same question under 67 different IDs — we showed it live
- 9 different text variants for "normal blood pressure" — we normalized them
- Wellster told us this was "always nice-to-have, never prioritized" — we made it a product

**Target audience defined:** Telehealth platforms first (Wellster = proof), then CROs, insurers, hospital groups.

### 3. Research & Understanding — 9 POINTS

**We demonstrate awareness of:**
- GDPR: pseudonymized user_ids only, no PII in outputs, medical data handling
- Clinical workflows: human-in-the-loop for taxonomy validation, quality alerts for clinical review
- Medical standards: FHIR R4, ICD-10, SNOMED CT, RxNorm, LOINC, ATC — not custom labels
- Market: GLP-1 market explosion (Wegovy, Mounjaro), telehealth growth, data interoperability mandates

### 4. Originality & Innovation — 6 POINTS

**Our edge:**
- AI discovers categories from scratch — no hardcoded schema, no manual mapping
- Two-level normalization: questions AND answers
- Single API call architecture — globally consistent categories, no batch fragmentation
- Incremental mode: validated taxonomy persists, only new questions cost API calls
- Medical coding layer: canonical answers mapped to international clinical codes

**Competing solutions:** Manual spreadsheet mapping (weeks), custom ETL scripts (break on schema changes), generic data integration tools (don't understand clinical semantics).

### 5. Usage of Wellster Data — 6 POINTS

**We used ALL of it:**
- Started with 3-month GoLighter data (12K rows)
- Scaled to 15-month data (23K rows) — automatically
- Then processed the full multi-brand dataset (134K rows, GoLighter + Spring)
- Found real clinical signals: 1,010 quality alerts, medication switches, BMI trajectories, side effect profiles, compliance patterns
- Cross-brand analytics: Mounjaro vs Wegovy vs Sildenafil vs Tadalafil — all in one unified view

### 6. Presentation & Communication — 6 POINTS

**Demo tells a story:**
- Dashboard: population overview with canonical metrics
- Explorer: filter by any of 26 categories × medication × gender — instant aggregated view
- Patient: unified record showing what fragmented data couldn't — medication journey, BMI trajectory, quality alerts
- Process: upload → classify → export (CSV, JSON, FHIR)

### 7. Bonus Points — up to 5 POINTS

- Working Streamlit demo with real data
- FHIR R4 export with ICD-10 + SNOMED CT + RxNorm + LOINC codes
- Multi-brand scalability proven live
- AI-powered auto-classify: paste any new question → instant classification
- Answer normalization across languages (German ↔ English)

---

## PITCH SCRIPT (2 minutes)

**[0:00 — Problem]**
"Wellster has 750,000 treatments. Every time they update a survey, the same question gets a new ID. 'Do you have pre-existing conditions?' exists under 67 different IDs. They literally cannot compare patient data from January to March. Every telehealth company, every clinical trial CRO, every insurance company has this exact problem."

**[0:25 — Solution]**
"We built UniQ — an AI engine that takes any questionnaire dataset, discovers the clinical structure automatically, normalizes every answer across languages and survey versions, and exports unified, medically coded data. No hardcoded rules. No manual mapping. Human-in-the-loop for validation."

**[0:50 — Demo]**
"Here's what it does. We uploaded Wellster's data — 134,000 rows, two brands, obesity and sexual health, 19 different medications. The AI classified 4,553 fragmented question IDs into 26 clinical categories. One API call. Then it normalized 416 answer variants into 164 canonical values — 'Normal blood pressure' in 9 different phrasings becomes one label. The output is FHIR R4 with proper ICD-10, SNOMED, and RxNorm codes."

**[1:15 — Scalability]**
"We proved it scales. First dataset: 12,000 rows. Second: 23,000. Third: 134,000 across two brands. Each time, zero code changes. The AI discovered new categories automatically. The validated taxonomy persists — next upload costs $0.05."

**[1:35 — Business]**
"Every organization with evolving questionnaires needs this. Telehealth platforms can't track outcomes. CROs lose weeks on protocol amendments. Insurers can't aggregate across providers. We solve it with a SaaS engine that costs cents per run and exports data any system can consume."

**[1:55 — Close]**
"UniQ. Fragmented data in. Unified, coded, interoperable healthcare data out."

---

## TECH STACK

| Component | Technology | Why |
|---|---|---|
| Language | Python 3.10+ | Data processing standard |
| Data | Pandas | Efficient tabular processing |
| AI | Claude Sonnet (Anthropic API) | Best at structured JSON output, medical vocabulary |
| Frontend | Streamlit | Rapid prototyping, interactive |
| Charts | Plotly | Interactive, publication-quality |
| Export | Custom FHIR R4 builder | Healthcare interoperability |
| Medical codes | Static mapping layer | ICD-10, SNOMED CT, RxNorm, LOINC, ATC |

**AI usage is surgical:**
- 2 API calls total for the full 134K row dataset
- Classification: 1 call (~25K tokens in, ~5K out)
- Answer normalization: 1 call (~6K tokens in, ~9K out)
- Total cost: ~$0.10
- Everything else is deterministic

---

## NEXT STEPS (if we enter the coaching track)

### Week 1-2: Production hardening
- Docker containerization
- Scheduled pipeline runs (cron / Airflow)
- Proper database backend (PostgreSQL)
- Authentication + multi-tenant support

### Week 3: Integration
- FHIR endpoint (REST API) for EHR consumption
- Webhook for "new data available" notifications
- Taxonomy management UI (merge, rename, validate categories)

### Week 4: Go-to-market
- Pilot with Wellster (all 3 brands)
- Pricing model validation
- First external customer outreach (CROs, Krankenkassen)

---

## TEAM

[Add team member names, roles, backgrounds]

Built with Claude Code (Anthropic) as the AI development partner.
