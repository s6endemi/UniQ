# Golden Master — Pipeline Baseline (2026-04-20)

Frozen reference output of `python pipeline.py` on `treatment_answer.csv`.
Used as regression baseline while refactoring (Engine-API → Repository → Concept-Schicht → UI split).

If a refactor breaks structure, the pipeline should still produce numerically identical
tables (modulo AI-taxonomy drift, which is what the Concept-Schicht handles).

## Input
- `data/raw/treatment_answer.csv` — 134,039 rows, 32 columns
- Orphan cleanup: 42 null-user_id rows dropped → 133,996 clean rows
- Pipeline model: `claude-sonnet-4-6`
- Mode: discovery (no pre-existing `taxonomy.json`)

## Artifact manifest

| File | SHA-256 (first 16) | Size | Rows |
|---|---|---:|---:|
| mapping_table.csv        | 541c260dcdb06fe6 |   1.9 MB |  4,553 |
| survey_unified.csv       | 3b31d6d9ecb2cc7d | 101.7 MB | 133,996* |
| patients.csv             | 717022da4a28c424 | 571 KB |  5,374 |
| treatment_episodes.csv   | 96de230e55b4b5a8 |   1.1 MB |  8,835 |
| medication_history.csv   | 8e6c17b5ceb1f897 | 716 KB |  8,835 |
| bmi_timeline.csv         | 7fc83740efaab173 | 406 KB |  5,705 |
| quality_report.csv       | 6cecbb1c42b2850d | 114 KB |  1,028 |
| taxonomy.json            | 4bf1d99b6044a4a5 |   4 KB | 20 categories |
| answer_normalization.json| 9b4ebc9b29c44f04 |  24 KB | 406→235 canonical |
| data_inspection.txt      | 332e3cce88e6ac6e |  14 KB | - |

\* `wc -l` over-counts due to embedded newlines in JSON-encoded `normalized_value` column; actual data rows = 133,996.

## Run metrics (from `pipeline_run.log`)

### AI classification (discovery mode)
- 238 unique question texts → 20 categories in 1 API call
- 1 question missed → recovered via follow-up call
- API cost: 28,620 in / 7,964 out tokens (first call), 956 / 58 (recovery)

### AI answer normalization
- 16 categories with >1 answer variant, 406 unique values total
- Single API call: 6,046 in / 10,064 out tokens
- Output: 406 variants → 235 canonical labels
- Applied to 116,087 / 133,996 rows (86.6%)

### Unification
- 5,374 patients, 8,835 treatment episodes
- 5,705 BMI measurements (4,901 patients with ≥1 BMI)

### Quality checks (1,028 alerts total)
| Check | Count | Severity |
|---|---:|---|
| undocumented_switch | 819 | info |
| bmi_gap             | 147 | warning |
| bmi_spike           |  34 | warning |
| subscription_lapse  |  25 | warning |
| suspicious_bmi      |   3 | warning |

## Discovered taxonomy (20 categories, from `taxonomy.json`)

```
BLOOD_PRESSURE_ASSESSMENT
BMI_MEASUREMENT
BODY_PHOTO_UPLOAD
CURRENT_MEDICATIONS
DEMOGRAPHIC_AND_IDENTITY
ED_TREATMENT_HISTORY
ED_TREATMENT_OUTCOMES
ERECTILE_DYSFUNCTION_ASSESSMENT
GASTROINTESTINAL_SYMPTOMS
ID_DOCUMENT_UPLOAD
LIFESTYLE_RISK_FACTORS
MEDICAL_HISTORY
OBESITY_COMORBIDITIES
PATIENT_CONSENT_CONFIRMATION
PHOTO_UPLOAD_DECISION
SIDE_EFFECT_REPORT
TREATMENT_PREFERENCE_AND_ELIGIBILITY
WEIGHT_LOSS_LIFESTYLE
WEIGHT_LOSS_TREATMENT_HISTORY
WEIGHT_LOSS_TREATMENT_MONITORING
```

## Full drift map — why the Concept-Schicht is load-bearing

Hardcoded category strings in the codebase, checked against the 20 categories above:

### `src/demo.py` (UI — 5 hits)
| Line | Hardcoded string | Status | Actual category (if drifted) |
|---:|---|---|---|
| 323 | `BLOOD_PRESSURE_CHECK` | **drift** | `BLOOD_PRESSURE_ASSESSMENT` |
| 332 | `MEDICAL_CONDITIONS` | **drift** | `MEDICAL_HISTORY` + `OBESITY_COMORBIDITIES` |
| 515 | `SIDE_EFFECT_REPORT` | ok | — |
| 534 | `TREATMENT_ADHERENCE` | **drift** | not in taxonomy (embedded in `WEIGHT_LOSS_TREATMENT_MONITORING`) |
| 558 | `MEDICAL_CONDITIONS` | **drift** | `MEDICAL_HISTORY` + `OBESITY_COMORBIDITIES` |

### `src/export_fhir.py` (FHIR export — 3 hits)
| Line | Hardcoded string | Status |
|---:|---|---|
| 207 | `MEDICAL_CONDITIONS` | **drift** |
| 207 | `COMORBIDITY_SCREENING` | **drift** (not in taxonomy) |
| 215 | `SIDE_EFFECT_REPORT` | ok |

### `src/unify.py` (**Engine-internal**, 1 hit)
| Line | Hardcoded string | Status |
|---:|---|---|
| 40 | `BMI_MEASUREMENT` | ok now — **but if drifts, entire `bmi_timeline.csv` silently empty** |

This is the most dangerous hit: it's not just UI cosmetics, it's the core engine step that feeds Patient page, Insights, FHIR Observations, and Quality checks.

### `src/medical_codes.py` (`CATEGORY_CODING` dict)
Defines mapping from 18 category names to FHIR types. Currently unused at runtime (`get_category_coding()` is defined but never called). Still represents the intended concept→FHIR-type contract that the Concept-Schicht should own.

### Implications for Concept-Schicht (Phase 4)

The Concept-Schicht is not a UI-only adapter. Its scope must include:
- `src/unify.py` (engine) — `Concept.BMI` → filter mask
- `src/export_fhir.py` (engine export) — `Concept.CONDITIONS`, `Concept.SIDE_EFFECTS`
- `src/demo.py` (UI) — all current hardcodes
- `src/medical_codes.py` (coding) — FHIR type per Concept

Minimum Concept set for current consumers:
`BMI`, `BLOOD_PRESSURE`, `SIDE_EFFECTS`, `CONDITIONS`, `ADHERENCE`, `MEDICATIONS`.

## Known quirks observed during baseline run

1. **Windows UTF-8 stdout bug**: `src/classify_ai.py:268` prints `→` which crashes under
   `cp1252`. Baseline required `PYTHONIOENCODING=utf-8` env var. Fix properly during
   Phase 5 (Packaging/Logging): replace `print()` with structured logging.

2. **Taxonomy non-determinism**: Two successive discovery runs produce different category
   names (`MEDICAL_HISTORY_AND_CONDITIONS` vs `MEDICAL_HISTORY`). Expected behavior of
   discovery mode. This is the primary reason for the Concept-Schicht.

3. **`quality_report.csv` row count is time-dependent**: `src/quality.py:116`
   (`check_subscription_lapse`) computes `days_since` using `pd.Timestamp.now(tz="UTC")`.
   The subscription-lapse rule (>60 days inactive) therefore produces a slightly different
   count on every calendar day. Baseline manifest shows 1,028 alerts; re-runs on later
   days may produce 1,029, 1,030, etc. Business logic, not a bug — but means the
   `quality_report.csv` hash is never stable across days. Use **row counts by check_type**
   (not total or file hash) as the stable comparison key.

## How to regenerate

```bash
cd wellster-pipeline
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe pipeline.py
```

Then compare `output/*.csv` row counts against this manifest. Taxonomy / canonical-label
differences are expected and acceptable — the *counts* and *structural shape* should match.

Drift-check automated via `tests/smoke_demo_load.py`.
