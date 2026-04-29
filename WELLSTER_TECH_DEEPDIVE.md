---
tags: [uniq, wellster, technical-deepdive, follow-up]
type: technical-doc
date: 2026-04-29
audience: Wellster Data Team + Product Owners
authored-by: Eren Demir (UniQ)
status: draft-v3
---

# UniQ - Technical Deep-Dive for Wellster

> Technical follow-up to the Wellster intro call on 2026-04-28.
> This document answers the concrete data-team concerns: answer normalization
> trust, AI drift, manual effort vs automation, HITL configurability, FHIR
> export, reproducibility, and GDPR-relevant patient retraction.

## Honesty Convention

Every capability below uses one of these states:

- **Live + verified**: implemented in the current codebase and exercised by tests, API checks, or the materialization manifest.
- **Live, pilot-operated**: implemented, but still operated through API/JSON/runbook rather than polished product UI.
- **Pilot setup**: expected configuration work during Wellster onboarding.
- **Roadmap**: not needed for the first pilot; included so the boundary is explicit.

The current external support docs are:

- `wellster-pipeline/ARCHITECTURE.md` - module map, data flow, trust boundaries.
- `wellster-pipeline/OPERATIONS.md` - materialization, tests, eval, retraction, manifest runbook.

---

## TL;DR

UniQ is a Clinical Truth Layer: it turns fragmented Wellster survey data into a typed, queryable, audited substrate beside your existing systems.

The critical trust gaps from the earlier draft now have live pilot mechanisms: answer normalization is registry-backed and reviewable, unknown variants go into a queue, reviewed categories and labels gate a `survey_validated` runtime layer, materialization is hash-verifiable, analyst LLM behavior has guardrail tests, and patient retraction is live with HMAC tombstones.

The system is pilot-ready, not enterprise-production-complete. Postgres governance storage, SSO/RBAC, multi-tenant isolation, full observability, and generic multimodal loaders remain explicit roadmap items.

---

## 1. Current Verified State

The current materialized run is verifiable through:

```text
GET /v1/substrate/manifest
output/materialization_manifest.json
```

Headline numbers from the current manifest:

| Surface | Current value |
| --- | ---: |
| Raw input rows | 133,996 |
| Raw question IDs | 4,553 |
| Unique English question texts in mapping table | 234 |
| Discovered clinical categories | 20 |
| Category review state | 17 approved, 3 rejected |
| Raw/staging survey events (`survey_unified.csv`) | 133,996 |
| Validated survey events (`survey_validated`) | 116,207 |
| Validated completeness | 116,207 full, 0 partial |
| Normalization registry records | 527 |
| Normalization review state | 527 approved, 0 pending, 0 rejected |
| Unknown normalization queue | 338 total, 217 open, 121 promoted |
| Quality findings | 1,041 |
| Patient records | 5,374 |
| Chat eval | 19/19 passed, stale=false |
| Active patient retractions | 0 |

Current substrate resources exposed in the manifest:

| Resource | Rows | Role |
| --- | ---: | --- |
| `patients` | 5,374 | typed patient index |
| `bmi_timeline` | 5,705 | longitudinal BMI events |
| `medication_history` | 8,835 | medication/dosage events |
| `treatment_episodes` | 8,835 | treatment periods |
| `quality_report` | 1,041 | data-quality findings |
| `survey_unified` | 133,996 | raw/staging survey layer |
| `survey_validated` | 116,207 | reviewed runtime survey layer |
| `semantic_mapping` | 20 | category governance |
| `fhir_bundle` | 5,374 | per-patient FHIR export surface |
| `clinical_annotations` | 2 | clinician write-back notes |

The manifest also exposes per-table SHA-256 hashes, the input hash, mapping hash,
normalization hash, git commit, retraction stats, and chat-eval status.

---

## 2. Architecture in One Page

```text
Wellster survey CSV/TSV
        |
        v
Load + discovery
        |
        v
taxonomy.json + mapping_table.csv + semantic_mapping.json
        |
        v
answer_normalization.json + normalization_queue.json
        |
        v
survey_unified.csv
  raw/staging layer: audit, debugging, unknowns, rejected/nonclinical categories
        |
        v
survey_validated
  runtime layer: approved/overridden categories + approved/overridden labels
        |
        +--> Patient API
        +--> FHIR export
        +--> Analyst chat via DuckDB
        +--> Cohort and opportunity artifacts
        +--> CSV snapshot exports
```

The core design is intentionally hybrid:

- AI proposes structure from unique patterns, not from every row.
- Clinician/data-team review signs the governance state.
- Deterministic code applies that state to the full dataset.
- Clinical downstream consumers read from the validated layer by default.
- The manifest proves exactly which input, mappings, normalization registry, and output hashes produced a run.

Key implementation files:

| Area | Files |
| --- | --- |
| Pipeline | `pipeline.py`, `src/engine.py` |
| Discovery/mapping | `src/classify_ai.py`, `src/semantic_mapping_ai.py`, `src/unify.py` |
| Answer normalization | `src/normalization_registry.py`, `src/normalization_queue.py`, `src/normalize_answers_ai.py` |
| Validated runtime layer | `src/datastore.py`, `src/query_service.py` |
| API | `src/api/routers/*`, `src/api/models.py` |
| Analyst | `src/chat_agent_v2.py`, `src/chat_prompts_v2.py`, `src/chat_v2_models.py` |
| FHIR | `src/export_fhir.py`, `src/medical_codes.py` |
| Retraction | `src/retractions.py`, `scripts/purge_patient.py` |
| Manifest | `src/materialization_manifest.py` |

---

## 3. Answer Normalization: What Changed Since v2

This was the most important technical concern from your team: not just "did AI
classify the question correctly?", but "can we trust the normalized answer
value?"

### 3.1 What is live now

Answer normalization is no longer just a flat `original -> canonical` map.
It is a record-backed registry:

```json
{
  "id": "norm-...",
  "category": "CURRENT_MEDICATIONS",
  "original_value": "L-thyroxin",
  "canonical_label": "LEVOTHYROXINE",
  "review_status": "approved",
  "source_count": 12,
  "first_seen": "2026-...",
  "last_seen": "2026-..."
}
```

Live properties:

- Stable record IDs per `(category, original_value)`.
- Per-label `review_status`: `approved`, `overridden`, `pending`, `rejected`.
- Reviewer identity and role captured when labels are changed.
- `source_count`, `first_seen`, and `last_seen` captured per record.
- Case-collision handling: values that differ only by casing are surfaced, not overwritten by object-key collisions.
- API surface:
  - `GET /v1/normalization`
  - `GET /v1/normalization/unknown`
  - `PATCH /v1/normalization/{id}`
  - `POST /v1/normalization/unknown/{id}/resolve`

### 3.2 Unknown variants

New answer variants are not silently trusted. They are captured in
`normalization_queue.json` and surfaced via:

```text
GET /v1/normalization/unknown
```

Current queue state:

| Queue state | Count |
| --- | ---: |
| Total unknown entries seen | 338 |
| Open | 217 |
| Promoted | 121 |
| Dismissed | 0 |

Open entries remain visible for review. Promoted entries are inserted into the
normalization registry as approved records and picked up by the next pipeline
run. Dismissed entries remain in the queue for audit.

### 3.3 Runtime gating

`survey_validated` applies two gates:

1. Category-level gate: `clinical_category` must be approved or overridden in
   `semantic_mapping.json`.
2. Label-level gate: normalized values must be approved or overridden in the
   normalization registry. `unknown`, `no_mapping`, and `skipped` rows stay in
   `survey_unified` only.

Current result:

```text
survey_unified:   133,996 rows
survey_validated: 116,207 rows
excluded from validated survey layer: 17,789 rows
```

This is the key trust boundary: unknowns are retained for audit and review, but
not treated as signed clinical facts.

### 3.4 What is still not polished

The per-label governance model is live, but the product UI is not yet polished.
Today the review surfaces are API-backed and runbook-backed. A browser UI for
merge/split/rename workflows is pilot setup, not a blocker for the trust model.

---

## 4. HITL and Manual Effort

The pitch shows the operational phase. The real deployment has two phases.

### 4.1 Onboarding phase

Human-led, expected:

1. Ingest a current Wellster snapshot.
2. Run AI discovery and initial normalization.
3. Wellster clinician/data team reviews:
   - category mappings in `semantic_mapping.json`
   - answer labels in the normalization registry
   - unknown variants in the queue
   - FHIR resource mapping expectations
   - quality-report thresholds
4. Re-run full materialization.
5. Verify manifest, tests, FHIR examples, and known-good patients.

The current default state is already signed for the demo dataset:

```text
semantic categories: 17 approved, 3 rejected
normalization labels: 527 approved
```

The three rejected categories are non-clinical upload workflow categories:
ID/document/photo upload surfaces, not clinical signal.

### 4.2 Operational phase

Mostly autonomous:

- New rows materialize deterministically from the signed mappings.
- New unknown answer variants enter the queue.
- Rejected categories stay out of the validated runtime layer.
- Quality flags accumulate in `quality_report`.
- The manifest records hashes and eval status on each run.

The operational default is not "AI decides everything." It is "AI proposes
structure; signed governance state decides what downstream systems can consume."

---

## 5. AI Drift and Hallucination Boundaries

There are three AI surfaces. They have different risk profiles.

### 5.1 Discovery-time AI

AI sees the unique pattern set, not the full row volume:

```text
4,553 raw question IDs
234 unique English question texts in mapping_table.csv
20 clinical categories
```

This bounds the discovery problem. It also makes review feasible: clinicians
review categories and labels, not 133,996 individual rows.

Once mappings and normalization registry records are written, full-row
materialization is deterministic Pandas code.

### 5.2 Answer-normalization AI

The initial canonical label suggestions are AI-generated. Trust comes from the
registry and queue after that:

- reviewed records are deterministic;
- unknown variants are queued;
- rejected or unknown values do not enter `survey_validated`;
- coverage stats are visible in the manifest.

This does not claim that AI never makes a bad suggestion. It means bad
suggestions have a review state, an audit trail, and a runtime gate.

### 5.3 Analyst runtime LLM

The analyst chat uses Sonnet at query time. It is not allowed to directly write
data or invent arbitrary UI payloads.

Guardrails:

- DuckDB read-only guardrails block DDL/DML, stacked statements, file table
  functions, `ATTACH`, `COPY`, and `PRAGMA`.
- Tool inputs are Pydantic-validated.
- The model can only present typed artifact families through terminal tools.
- SQL results are resolved by backend handles; the model does not manufacture
  the final artifact payload.
- Failing terminal-tool validation degrades to a generic table artifact.

Test backing:

```text
query guardrail tests: 7/7
chat agent v2 tests:   5/5
chat eval:             19/19, stale=false
```

---

## 6. Reproducibility and Auditability

Each materialization run writes:

```text
output/materialization_manifest.json
```

The API exposes the same verification summary at:

```text
GET /v1/substrate/manifest
```

Current manifest includes:

- run ID and generated timestamp;
- git commit;
- raw input hash and row count;
- taxonomy hash;
- semantic mapping hash and status counts;
- normalization registry hash and queue counts;
- output table hashes;
- `survey_validated.validation_completeness`;
- chat eval pass/total/stale;
- retraction tombstone stats.

This is the reproducibility contract: if a downstream consumer wants to know
which signed mappings and which input produced the substrate it is querying,
the manifest answers that directly.

Clinical review is not only read-state. The substrate also accepts clinician
write-back via `clinical_annotations`: notes can be pinned to patient-level or
event-level context, carry reviewer identity from `X-Uniq-Reviewer` /
`X-Uniq-Role`, and surface inside the patient-record artifact. This is the
first write-back primitive that turns the substrate from a one-shot export into
operational memory.

---

## 7. GDPR Retraction / Right to Erasure

Patient retraction is live.

Operational command:

```powershell
python scripts/purge_patient.py --user-id 12345 --deleted-by "privacy@wellster" --reason "DSGVO erasure request"
```

What happens:

- patient rows are removed from materialized CSV/JSON outputs;
- clinical annotations for the patient are removed;
- a tombstone is written so future pipeline runs do not re-expose the patient;
- `/patients/{id}` returns 404;
- `/export/{id}/fhir` and `/v1/export/{id}/fhir` return 404;
- active tombstones are re-applied during pipeline materialization before the
  manifest is written.

Privacy detail:

- tombstones store a server-secret HMAC-SHA256 of `user_id`, not the plain ID;
- this is pseudonymization, not anonymization;
- `UNIQ_RETRACTION_HASH_SECRET` must be kept outside git and preserved for the
  pilot environment;
- active legacy SHA tombstones fail closed instead of being silently ignored.

Test backing:

```text
retraction tests: 7/7
```

The current manifest shows:

```text
active_retractions: 0
total_tombstones: 1
```

The existing tombstone is restored test state, not an active patient deletion.

---

## 8. FHIR Export

FHIR export is live for per-patient bundles:

```text
GET /export/{id}/fhir
GET /v1/export/{id}/fhir
```

Current example:

```text
GET /v1/export/383871/fhir
```

returns:

```text
23 FHIR resources
1 Patient
11 Observations
11 MedicationStatements
```

The export path runs an internal smoke validator before returning a bundle. This
is not a claim of HL7 certification. It is a structural sanity check that the
bundle is internally valid enough for pilot review.

Current coding reality:

- FHIR resource construction uses typed tables plus the validated survey layer.
- Value coding still uses the existing obesity-domain `medical_codes.py` tables.
- `semantic_mapping.json` gates category trust; it is not yet a full terminology
  server or value-code registry.

That separation is deliberate. "Category maps to FHIR resource type" and
"Mounjaro maps to a specific medication code" are different problems. The
second becomes a terminology-management track during broader productionization.

---

## 9. Quality Monitoring

`quality_report.csv` is materialized on each run.

Current checks:

- BMI spike greater than 5 points between consecutive measurements.
- BMI measurement gap greater than 90 days.
- Undocumented medication switch.
- Subscription lapse.
- Suspicious BMI value.

Current finding count:

```text
quality_report rows: 1,041
```

Sample findings from the current output:

| severity | check_type | description |
| --- | --- | --- |
| warning | `bmi_spike` | BMI changed by 5.8 points between measurements |
| warning | `bmi_gap` | Patient has 370 day tenure but no BMI recorded |
| info | `undocumented_switch` | Medication switch: Mounjaro -> Wegovy |

These are data-quality findings, not automated clinical warnings. Thresholds are
currently hardcoded; making them cohort-specific is pilot setup if Wellster wants
different tolerances by brand or clinical domain.

---

## 10. Analyst Surface

The analyst interface is a controlled consumer of the substrate, not a second
source of clinical truth.

Live artifact families:

- cohort trend;
- alerts table;
- generic table;
- FHIR bundle;
- patient record;
- opportunity list.

The `opportunity_list` artifact is the cross-brand cohort surface. On the live
substrate, the Spring -> GoLighter screening path currently computes:

| Funnel step | Count |
| --- | ---: |
| Spring patients | 4,557 |
| BMI >= 27 | 2,029 |
| No GoLighter history | 2,014 |
| Active in last 180 days | 451 |
| High priority | 59 |

This is not a model-generated sales claim. It is a deterministic join across
validated brand history, current BMI state, target-brand history, and recent
activity. The value is that the substrate makes this type of cross-brand cohort
query operationally cheap and inspectable.

The default runtime is `chat_agent_v2.py`. The older v1 agent remains in the
repository only as an explicit fallback via `UNIQ_AGENT_MODE=v1`.

Current eval state:

```text
tests/run_chat_eval.py
19/19 passed
stale=false
```

This eval is externally observable: it checks HTTP status, artifact kind, SQL
count, reply terms, artifact terms, and latency. It does not inspect private
recipe names as a shortcut.

---

## 11. Extensibility: What Is Defensible vs Handwavy

The generic part of UniQ is the governance pattern:

```text
AI proposes structure -> human validates -> deterministic code applies -> manifest proves the run
```

The current loader is not generic. It is coupled to Wellster survey exports and
their column model.

Adding a new modality is real engineering work:

1. loader for the source format;
2. entity mapping into the substrate shape;
3. modality-aware discovery prompt;
4. HITL surface appropriate to the modality;
5. deterministic unification logic;
6. tests and manifest coverage.

So the honest claim is:

- Wellster survey CSV/TSV ingestion is live.
- Generic tabular onboarding is close, but not packaged.
- Notes, PDFs, images, and wearables are roadmap loaders, not hidden live
  capabilities.

This does not weaken the Clinical Truth Layer claim. It avoids pretending that
"same governance pattern" means "plug in any data type with no work."

---

## 12. Pilot-Ready vs Enterprise-Production-Ready

### Live + verified for the pilot

- Wellster survey ingestion.
- AI discovery on unique question patterns.
- Category governance via `semantic_mapping.json`.
- Normalization registry with per-label review state.
- Unknown-variant queue.
- Validated runtime layer.
- Manifest with hashes, eval state, and retraction stats.
- Patient retraction with HMAC tombstones.
- FHIR per-patient bundle export.
- Analyst guardrail tests and chat eval.
- Architecture and operations runbooks.

### Still roadmap, intentionally not built before first pilot

| Item | Trigger |
| --- | --- |
| Postgres governance store | concurrent reviewers or formal enterprise audit |
| SSO/RBAC | multiple Wellster reviewer groups with role separation |
| Full observability stack | persistent production service, not controlled pilot |
| Multi-tenant isolation | second customer or shared infrastructure |
| Partial re-materialization | full reruns become operationally expensive |
| Generic multimodal loaders | Wellster explicitly prioritizes notes/PDFs/images/wearables |
| Formal terminology service | broader FHIR/code-system production integration |
| HL7 validator certification path | production interoperability requirement |

This is the intended cut: build the controls that make pilot data trustworthy,
not the infrastructure that only becomes necessary after enterprise scale.

---

## 13. Worked Example: Patient 383871

Use this patient to ground-truth the system.

| Aspect | Value |
| --- | --- |
| Patient | 383871 |
| FHIR endpoint | `GET /v1/export/383871/fhir` |
| FHIR resource count | 23 |
| Resource types | Patient, Observation, MedicationStatement |
| Bundle smoke validation | passes before response |
| Patient endpoint | `GET /patients/383871` |

Expected FHIR shape:

```text
1 Patient
11 Observations
11 MedicationStatements
```

If this patient were retracted, both `/patients/383871` and
`/v1/export/383871/fhir` would return 404.

---

## 14. What We Want to Validate With Your Data Team

The next working session should not be a slide review. It should be a joint
technical walkthrough:

1. Walk `/v1/substrate/manifest`.
2. Inspect `survey_unified` vs `survey_validated`.
3. Review the 17 approved and 3 rejected categories.
4. Review the 527 normalization records and 217 open unknowns.
5. Pick 5-10 known patients and compare UniQ output against Wellster source
   truth.
6. Test FHIR export on those patients.
7. Run one simulated retraction and verify 404 behavior.
8. Decide quality-threshold tolerances.
9. Decide whether a browser UI for normalization review is needed before or
   during the pilot.

That is the point where this becomes a Wellster-specific signed substrate, not
just a strong demo on a snapshot.

---

## Appendix: Verification Commands

From `wellster-pipeline/`:

```powershell
python pipeline.py
python tests/test_normalization_registry.py
python tests/test_retractions.py
python tests/test_query_guardrails.py
python tests/test_query_service.py
python tests/test_api.py
python tests/test_chat_agent_v2.py
python tests/test_semantic_mapping.py
python tests/run_chat_eval.py
```

API checks:

```text
GET /v1/substrate/manifest
GET /v1/normalization
GET /v1/normalization/unknown
GET /patients/383871
GET /v1/export/383871/fhir
```

Retraction check:

```powershell
python scripts/purge_patient.py --user-id 383871 --deleted-by "privacy-review" --reason "verification"
```

Only run the retraction check on a disposable copy of `output/`, or restore the
tombstone and re-run the pipeline afterwards.
