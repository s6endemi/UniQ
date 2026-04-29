# UniQ Wellster Pipeline Operations

This runbook covers the pilot-grade operational paths: materialization,
verification, eval, retraction, and manifest checks.

## Environment

Create `wellster-pipeline/.env` from `.env.example`.

Required for AI-backed stages and the analyst runtime:

```powershell
ANTHROPIC_API_KEY=...
```

Required before any patient retraction is performed:

```powershell
UNIQ_RETRACTION_HASH_SECRET=...
```

Generate the retraction secret with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep this secret outside git. Tombstones use HMAC-SHA256 and need the same
secret to detect already retracted patients after future materialization runs.

## Materialize

From `wellster-pipeline/`:

```powershell
python pipeline.py
```

The pipeline writes materialized outputs under `output/` and then writes:

```text
output/materialization_manifest.json
```

The manifest should be treated as the run receipt: input hash, mapping hash,
normalization hash, output-table hashes, git commit, retraction stats, and chat
eval status.

## Verify Core Tests

Run the focused pilot suite:

```powershell
python tests/test_normalization_registry.py
python tests/test_retractions.py
python tests/test_query_guardrails.py
python tests/test_query_service.py
python tests/test_api.py
python tests/test_chat_agent_v2.py
python tests/test_semantic_mapping.py
```

These tests are not just placeholder checks. They exercise real temp CSV purge,
FastAPI 404 behavior after retraction, DuckDB guardrail enforcement, API model
serialization, and v2 agent degradation paths.

## Run Chat Eval

Run this after pipeline materialization and after code or prompt changes:

```powershell
python tests/run_chat_eval.py
```

The default output is:

```text
output/chat_eval_report.json
```

`src/materialization_manifest.py` reads that report and exposes the pass count
and stale flag in both the raw manifest and `/v1/substrate/manifest`.

Run chat eval last before sending technical documentation, otherwise the
manifest can correctly mark the eval as stale if output artifacts changed after
the eval report was generated.

## Check Manifest Through API

Start the API if needed, or use FastAPI TestClient in-process. The key endpoint
is:

```text
/v1/substrate/manifest
```

For the Wellster pilot, verify at minimum:

- `materialization.input_row_count` is present.
- `materialization.validation_completeness` is present.
- `materialization.retraction_active_tombstones` is present.
- `materialization.chat_eval_passed == materialization.chat_eval_total`.
- `materialization.chat_eval_stale == false`.
- `materialization.output_table_hashes` includes `survey_validated`.

## Patient Retraction

Use the script from `wellster-pipeline/`:

```powershell
python scripts/purge_patient.py --user-id 12345 --deleted-by "privacy@wellster" --reason "DSGVO erasure request"
```

This removes the patient from materialized CSV/JSON outputs and appends a
tombstone to:

```text
output/retraction_tombstones.json
```

The tombstone contains a server-secret HMAC of the patient ID, not the plain
ID. This is pseudonymized operational state and still needs normal access
control.

After retraction:

- `/patients/{id}` returns 404.
- `/v1/export/{id}/fhir` returns 404.
- future pipeline runs re-apply active tombstones before the manifest is
  written.

To restore a patient for an operational correction, mark the tombstone status
as `restored` with reviewer context, then re-run `python pipeline.py`. A formal
restore CLI is not implemented yet.

## Governance Writes

Send reviewer headers on governance-changing API calls:

```text
X-Uniq-Reviewer: reviewer@example.com
X-Uniq-Role: clinician
```

This applies to semantic mapping review, normalization review, and clinical
annotations. Local demos can omit the headers, but pilot operations should not.

## Current Roadmap Triggers

Move from JSON governance stores to Postgres when concurrent reviewer editing
or enterprise audit requirements appear.

Add SSO/RBAC when more than one Wellster reviewer group needs role separation.

Add observability when the API is operated as a persistent production service,
not just a controlled pilot environment.

Add partial re-materialization when full reruns become operationally expensive
on larger historical backfills.
