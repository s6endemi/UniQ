# WELLSTER UNIFIED DATA PIPELINE — CLAUDE CODE BUILD PLAN
# Agent-optimized: execute each step sequentially. Wait for confirmation before proceeding.

## CONTEXT

You are building a data pipeline for a healthcare hackathon. The client is Wellster Healthtech Group,
a digital telehealth company in Germany operating three brands:
- GoLighter (obesity/weight management) ← PRIMARY FOCUS
- Spring (sexual health)
- MySummer (contraception)

The raw data is a flat CSV/TSV where each row = one patient answering one question in one survey
for one treatment. A single patient with 13 orders might have hundreds of rows.

The core problem: survey questions change over time (new IDs, reworded text, different answer formats).
This makes longitudinal patient analysis impossible without first unifying the data.

We are building: a scalable pipeline that transforms this raw data into clean, analytics-ready
structured tables — with automatic semantic question mapping, answer normalization,
and cross-temporal data quality checks.

Tech stack: Python, Pandas, Claude/Gemini API for semantic mapping, Streamlit for demo frontend.

---

## STEP 1: PROJECT SETUP

Create a Python project with this structure:

```
wellster-pipeline/
├── data/
│   └── raw/                    # raw Wellster TSV/CSV files go here
├── output/
│   ├── mapping_table.csv       # question_id → clinical_category
│   ├── patients.csv            # unified patient profiles
│   ├── treatment_episodes.csv  # one row per treatment
│   ├── bmi_timeline.csv        # longitudinal BMI measurements
│   ├── survey_unified.csv      # all survey responses mapped + normalized
│   ├── medication_history.csv  # chronological medication changes
│   └── quality_report.csv      # data quality flags
├── src/
│   ├── load.py                 # Step 2: load and inspect raw data
│   ├── discover.py             # Step 3: extract unique questions, LLM discovery
│   ├── classify.py             # Step 4: LLM classification with fixed taxonomy
│   ├── normalize.py            # Step 5: answer normalization per category
│   ├── unify.py                # Step 6: build unified output tables
│   ├── quality.py              # Step 7: data quality checks
│   └── demo.py                 # Step 8: Streamlit demo app
├── config.py                   # API keys, file paths, settings
├── pipeline.py                 # runs full pipeline end-to-end
└── requirements.txt
```

requirements.txt:
```
pandas
anthropic          # or google-generativeai for Gemini
streamlit
plotly
openpyxl
```

---

## STEP 2: LOAD AND INSPECT (src/load.py)

Load the raw data file. The file is TSV (tab-separated).

```python
# Key tasks:
# 1. Load file with proper encoding (utf-8), separator (\t)
# 2. Print: total rows, unique user_ids, unique treatment_ids, unique question_ids
# 3. Print: columns and their dtypes
# 4. Print: sample of 5 rows
# 5. Print: date range (min/max of created_at)
# 6. Print: unique values for: t_status, product, order_type, brand, response_type, indication
# 7. Print: null counts per column
# 8. Save summary to output/data_inspection.txt
```

Important column types to parse:
- `created_at`, `first_order_at`, `updated_at` → datetime
- `current_age`, `n_orders`, `product_qty` → numeric
- `answer_value_height`, `answer_value_weight` → numeric (can be null)
- Everything else → string

---

## STEP 3: DISCOVERY — EXTRACT UNIQUE QUESTIONS + LLM CLUSTERING (src/discover.py)

### 3a. Extract unique questions

```python
# Extract all unique question_id + question_en combinations
# Drop duplicates
# Sort by question_id
# Print: "Found X unique questions from Y total rows"
# Save to output/unique_questions.csv
```

### 3b. Send to LLM for discovery clustering

Send the unique questions to Claude API in batches of 30.

PROMPT (use this exactly):
```
You are a medical data engineer analyzing questionnaire data from a digital obesity 
telehealth platform (GoLighter by Wellster).

Below are unique medical questionnaire questions. Each has a question_id and the English text.

YOUR TASKS:
1. Identify natural clinical groupings — questions that ask about the same clinical concept 
   even if worded differently or having different IDs
2. Propose a taxonomy of clinical categories with short definitions
3. Flag questions that are duplicates (same intent, different wording/ID)
4. Note questions that cover multiple concepts

Return JSON:
{
  "proposed_categories": [
    {"name": "BMI_MEASUREMENT", "definition": "Questions collecting height, weight, or BMI data"},
    ...
  ],
  "question_assignments": [
    {"question_id": 37213, "proposed_category": "PHOTO_UPLOAD_ID", "reasoning": "Asks for ID document photo", "duplicate_of": null},
    {"question_id": 108865, "proposed_category": "PHOTO_UPLOAD_BODY", "reasoning": "Asks for full body photo", "duplicate_of": 37213},
    ...
  ],
  "notes": "any observations about the data structure"
}

QUESTIONS:
[insert batch here]
```

### 3c. Aggregate results

- Collect all batch results
- Merge proposed categories across batches (deduplicate)
- Save to output/discovery_results.json
- Print summary: "Proposed X categories, found Y duplicate pairs"

AT THIS POINT: Stop and show the proposed taxonomy to the team for review.
The team (especially the medical member) validates and adjusts categories.
Save the final validated taxonomy to config.py as CLINICAL_TAXONOMY dict.

---

## STEP 4: CLASSIFICATION — MAP ALL QUESTIONS TO FINAL TAXONOMY (src/classify.py)

After the team validates the taxonomy, classify all questions with the fixed categories.

PROMPT:
```
You are a medical data classifier. Classify each question into EXACTLY ONE of these 
clinical categories. If none fits, use "OTHER".

CATEGORIES:
{insert validated taxonomy from config.py}

For each question return:
{"question_id": ..., "category": "...", "confidence": "high|medium|low"}

Respond ONLY with a JSON array, no other text.

QUESTIONS:
[batch of 30]
```

### Post-processing:
```python
# 1. Collect all classifications
# 2. Flag low-confidence items (print them for manual review)
# 3. Create mapping table: question_id | question_text | clinical_category | confidence
# 4. Save to output/mapping_table.csv
# 5. Print: "Mapped X questions. High: Y, Medium: Z, Low: W"
# 6. Print: distribution of categories (how many questions per category)
```

---

## STEP 5: ANSWER NORMALIZATION (src/normalize.py)

For each clinical category, build a parser that extracts structured values from the raw answer fields.

### Strategy: category-specific parsers

```python
# The main function takes a row + its category and returns a normalized dict.
#
# IMPORTANT: Look at the actual answer formats per category first.
# For each category, run:
#   df[df['clinical_category'] == cat]['answer_value'].unique()
# to understand what formats exist.
#
# Common patterns observed in the data:
#
# BMI_MEASUREMENT:
#   - answer_value contains JSON: {"bmi": 42.15, "height": 163, "weight": 112}
#   - OR answer_value_height and answer_value_weight are populated separately
#   - Parser: try json.loads(answer_value), extract bmi/height/weight
#     Fallback: use answer_value_height + answer_value_weight columns, calculate BMI
#     Output: {"height_cm": float, "weight_kg": float, "bmi": float}
#
# PHOTO_UPLOAD_BODY / PHOTO_UPLOAD_ID:
#   - answer_value = "Später hochladen" / file reference string / "AnswerFile#..."
#   - Parser: classify as "uploaded" / "deferred" / "missing"
#     Output: {"status": str}
#
# TREATMENT_CONSENT / MEDICATION_CONFIRMATION:
#   - answer_value = predefined confirmation text
#   - Parser: if non-empty → confirmed = true
#     Output: {"confirmed": bool}
#
# SIDE_EFFECT_REPORT:
#   - answer_value = predefined option OR free text
#   - Parser: if predefined → map directly. If free text → use LLM to extract symptoms
#     Output: {"reported_effects": list[str], "severity": str|null}
#
# MEDICAL_HISTORY / CONTRAINDICATION_CHECK / ALLERGY_CHECK:
#   - Usually predefined answers (yes/no/list)
#   - answer_value_array may contain JSON array
#   - Parser: try json.loads(answer_value_array), fallback to answer_value text
#     Output: {"conditions": list[str]} or {"has_contraindication": bool}
#
# OTHER / UNKNOWN:
#   - Keep raw answer_value, don't attempt to normalize
#   - Output: {"raw": str}
#
# ONLY use LLM for free-text fields that cannot be parsed deterministically.
# Count how many rows need LLM vs deterministic parsing — should be <5% LLM.
```

### Apply normalization to full dataset:
```python
# 1. Join raw data with mapping_table on question_id
# 2. For each row, apply the appropriate category parser
# 3. Add normalized columns: normalized_value (JSON string), parse_method ("deterministic"|"llm")
# 4. Save to output/survey_unified.csv
# 5. Print: "Normalized X rows. Deterministic: Y%, LLM: Z%"
```

---

## STEP 6: BUILD UNIFIED OUTPUT TABLES (src/unify.py)

Transform the normalized survey data into structured analytical tables.

### Table 1: patients
```python
# One row per unique user_id
# Columns:
#   user_id, gender, current_age, first_order_date, latest_activity_date,
#   total_treatments, total_orders, active_treatments_count,
#   current_medication, current_dosage, latest_bmi, bmi_change_total,
#   patient_tenure_days
#
# Derived fields:
#   - first_order_date = min(first_order_at) per user
#   - latest_activity_date = max(updated_at) per user
#   - patient_tenure_days = latest_activity_date - first_order_date
#   - current_medication = product from most recent treatment where t_status = 'in_progress'
#   - latest_bmi = most recent BMI_MEASUREMENT normalized value
#   - bmi_change_total = latest_bmi - earliest_bmi
```

### Table 2: treatment_episodes
```python
# One row per unique treatment_id
# Columns:
#   user_id, treatment_id, product, product_dosage, indication,
#   start_date, latest_date, status, order_type, n_orders,
#   brand, survey_count
#
# Derived:
#   - start_date = min(created_at) for this treatment_id
#   - latest_date = max(updated_at) for this treatment_id
#   - survey_count = count distinct survey_ids for this treatment
```

### Table 3: bmi_timeline
```python
# One row per BMI measurement event
# Filter: only rows with clinical_category = 'BMI_MEASUREMENT' and valid normalized values
# Columns:
#   user_id, treatment_id, date, height_cm, weight_kg, bmi,
#   product_at_time, data_quality_flag
#
# data_quality_flag: 'ok' unless values are suspicious (see Step 7)
```

### Table 4: medication_history
```python
# Chronological medication journey per patient
# Source: treatment_episodes table, sorted by start_date per user_id
# Columns:
#   user_id, product, dosage, started, ended, duration_days,
#   order_type, n_orders, next_product
#
# Derived:
#   - ended = start_date of next treatment for same user (null if current)
#   - duration_days = ended - started
#   - next_product = product of the subsequent treatment (null if current)
```

### Table 5: survey_unified (already built in Step 5)

### Table 6: question_mapping (already built in Step 4)

Save all tables to output/ as CSV.
Print row counts for each table.

---

## STEP 7: DATA QUALITY CHECKS (src/quality.py)

Focus on cross-temporal and cross-field issues that the original questionnaires cannot catch.

```python
# Run these checks on the unified tables. Each check produces rows in quality_report.
#
# CHECK 1: BMI TIMELINE GAPS
# For patients with 3+ months tenure, check if BMI was measured at least every 3 months.
# Flag: "bmi_gap" | severity: "warning" | description: "No BMI recorded for X days"
#
# CHECK 2: BMI TRAJECTORY ANOMALIES
# If BMI increases by >5 points between two consecutive measurements, flag it.
# Could be data entry error or genuine concern — either way, worth reviewing.
# Flag: "bmi_spike" | severity: "warning"
#
# CHECK 3: MEDICATION SWITCH WITHOUT DOCUMENTATION
# If a patient's product changes between treatments but no survey captures the reason,
# flag it. This is a real clinical blind spot.
# Flag: "undocumented_switch" | severity: "info"
#
# CHECK 4: SUBSCRIPTION DROPOUT
# Patients with order_type = 'Sub Re-Order' who haven't reordered in 60+ days
# despite t_status = 'in_progress'. Potential churn or compliance issue.
# Flag: "subscription_lapse" | severity: "warning"
#
# CHECK 5: MISSING FOLLOW-UP SURVEY
# treatment rows where follow_up_survey_id is null but treatment has been active 30+ days
# Flag: "no_followup" | severity: "info"
#
# CHECK 6: ORPHANED DATA
# Survey responses that reference a question_id not in the mapping table
# (shouldn't happen after Step 4 but catches edge cases)
# Flag: "unmapped_question" | severity: "low"
#
# OUTPUT: quality_report.csv with columns:
# check_type | severity | user_id | treatment_id | description | details
#
# Print summary: "Found X issues. Critical: A, Warning: B, Info: C"
```

---

## STEP 8: STREAMLIT DEMO (src/demo.py)

Build a simple Streamlit app with 3 views:

### View 1: Patient Lookup
```python
# Input: user_id (dropdown or text input)
# Output:
#   - Patient summary card (age, gender, tenure, current medication)
#   - BMI timeline chart (plotly line chart)
#   - Medication history (colored timeline)
#   - Data quality flags for this patient (if any)
```

### View 2: Pipeline Stats
```python
# Show:
#   - Total patients processed
#   - Total treatments unified
#   - Question mapping coverage (X of Y questions mapped, Z% high confidence)
#   - Answer normalization stats (X% deterministic, Y% LLM)
#   - Data quality summary (issues by severity)
```

### View 3: Scalability Demo
```python
# Show the mapping table
# Have a text input where user can paste a NEW question text (simulating future survey change)
# On submit: call Claude API to classify the new question against the existing taxonomy
# Display: "This question would be classified as [CATEGORY] with [CONFIDENCE] confidence"
# Message: "Zero code changes needed — new questions are automatically integrated"
```

### Streamlit layout:
```python
# Use st.sidebar for navigation between views
# Use st.metric for key numbers
# Use plotly for charts (interactive)
# Keep it clean — no decorative elements, just clear data presentation
# Color scheme: use Wellster's green (#00C9A7) as accent color
```

---

## STEP 9: FULL PIPELINE RUNNER (pipeline.py)

```python
# Orchestrates all steps in sequence:
# 1. Load raw data (src/load.py)
# 2. Extract unique questions (src/discover.py - 3a only)
# 3. IF mapping_table.csv doesn't exist:
#      Run discovery (3b) → requires human review → save taxonomy to config
#      Run classification (Step 4)
#    ELSE:
#      Load existing mapping table
#      Check for new unmapped question_ids → classify only the new ones → append
# 4. Normalize answers (Step 5)
# 5. Build unified tables (Step 6)
# 6. Run quality checks (Step 7)
# 7. Print final summary
#
# This incremental logic is the scalability proof:
# First run: full pipeline
# Subsequent runs: only new/changed data gets processed
```

---

## NOTES FOR THE AGENT

- Always use English for variable names, comments, and output column names
- Handle encoding carefully — raw data contains German text with umlauts (ü, ö, ä, ß)
- Use try/except around JSON parsing — answer_value is unreliable
- Never hardcode question_ids — always work through the mapping table
- For LLM calls: use batch size 30, include retry logic with exponential backoff
- Save intermediate results after each step so the pipeline can resume
- Print clear progress messages at each step ("Step 3: Extracting unique questions... found 247")
- If the API key is not set, skip LLM steps and print a clear message about what's missing