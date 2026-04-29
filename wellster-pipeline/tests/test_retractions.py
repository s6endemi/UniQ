"""Retraction / right-to-erasure smoke tests."""

from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from fastapi.testclient import TestClient

import config
import src.retractions as retractions
from src.api.main import app
from src.retractions import (
    append_tombstone,
    filter_retracted_dataframe,
    is_patient_retracted,
    purge_patient_from_outputs,
)


_results: list[tuple[str, str, str]] = []


def _ok(name: str, detail: str = "") -> None:
    _results.append(("OK", name, detail))


def _fail(name: str, detail: str) -> None:
    _results.append(("FAIL", name, detail))


def _report_and_exit() -> int:
    icons = {"OK": "[OK]", "FAIL": "[X]"}
    for status, name, detail in _results:
        print(f"  {icons[status]} {name}" + (f" -- {detail}" if detail else ""))
    passes = sum(1 for s, *_ in _results if s == "OK")
    fails = sum(1 for s, *_ in _results if s == "FAIL")
    print(f"\n{passes} pass, {fails} fail")
    return 1 if fails else 0


def _write_minimal_outputs(tmp: Path, user_id: int) -> None:
    other = user_id + 1
    for filename in (
        "patients.csv",
        "treatment_episodes.csv",
        "bmi_timeline.csv",
        "medication_history.csv",
        "quality_report.csv",
        "survey_unified.csv",
    ):
        pd.DataFrame(
            [
                {"user_id": user_id, "value": "delete"},
                {"user_id": other, "value": "keep"},
            ]
        ).to_csv(tmp / filename, index=False)
    (tmp / "clinical_annotations.json").write_text(
        (
            '{"version":1,"annotations":['
            f'{{"id":"a1","patient_id":{user_id}}},'
            f'{{"id":"a2","patient_id":{other}}}'
            "]}"
        ),
        encoding="utf-8",
    )


def main() -> int:
    if not config.PATIENTS_TABLE.exists():
        print("SKIP: output artifacts missing — run pipeline.py first")
        return 0

    user_id = int(pd.read_csv(config.PATIENTS_TABLE, usecols=["user_id"]).iloc[0]["user_id"])

    previous_secret = os.environ.get("UNIQ_RETRACTION_HASH_SECRET")
    os.environ["UNIQ_RETRACTION_HASH_SECRET"] = "test-retraction-secret-32-bytes-minimum"
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write_minimal_outputs(tmp, user_id)
            result = purge_patient_from_outputs(
                user_id,
                output_dir=tmp,
                deleted_by="test",
                reason="unit test",
            )
            if result["total_rows_removed"] == 7:
                _ok("purge removes patient rows from CSVs + annotations", "7 rows")
            else:
                _fail("purge removes patient rows from CSVs + annotations", str(result))

            tombstone = result.get("tombstone") or {}
            if tombstone.get("hash_scheme") == "hmac-sha256-v2":
                _ok("tombstone uses HMAC hash scheme")
            else:
                _fail("tombstone uses HMAC hash scheme", str(tombstone))

            remaining = pd.read_csv(tmp / "patients.csv")
            if int(user_id) not in set(remaining["user_id"].astype(int)):
                _ok("purged patient absent from patients.csv")
            else:
                _fail("purged patient absent from patients.csv", remaining.to_string())

            tombstone_path = tmp / "retraction_tombstones.json"
            if is_patient_retracted(user_id, tombstone_path):
                _ok("tombstone marks patient as retracted")
            else:
                _fail("tombstone marks patient as retracted", "not detected")

            df = pd.DataFrame({"user_id": [user_id, user_id + 1]})
            filtered = filter_retracted_dataframe(df, tombstone_path=tombstone_path)
            if filtered["user_id"].tolist() == [user_id + 1]:
                _ok("runtime dataframe filter suppresses retracted patient")
            else:
                _fail("runtime dataframe filter suppresses retracted patient", filtered.to_string())

        with tempfile.TemporaryDirectory() as td:
            legacy_path = Path(td) / "retraction_tombstones.json"
            legacy_path.write_text(
                '{"version":1,"tombstones":[{'
                '"patient_hash":"legacy-plain-sha",'
                '"status":"active"'
                '}]}',
                encoding="utf-8",
            )
            try:
                is_patient_retracted(user_id, legacy_path)
            except RuntimeError:
                _ok("active legacy SHA tombstones fail closed")
            else:
                _fail(
                    "active legacy SHA tombstones fail closed",
                    "legacy tombstone was silently ignored",
                )

        old_tombstone_file = retractions.TOMBSTONE_FILE
        with tempfile.TemporaryDirectory() as td:
            retractions.TOMBSTONE_FILE = Path(td) / "retraction_tombstones.json"
            try:
                append_tombstone(
                    user_id=user_id,
                    deleted_by="test",
                    reason="api gate test",
                    table_counts={},
                )
                with TestClient(app) as client:
                    patient_response = client.get(f"/patients/{user_id}")
                    fhir_response = client.get(f"/v1/export/{user_id}/fhir")
                if patient_response.status_code == 404 and fhir_response.status_code == 404:
                    _ok("API and FHIR refuse retracted patient", "404/404")
                else:
                    _fail(
                        "API and FHIR refuse retracted patient",
                        f"patient={patient_response.status_code}, fhir={fhir_response.status_code}",
                    )
            finally:
                retractions.TOMBSTONE_FILE = old_tombstone_file
    finally:
        if previous_secret is None:
            os.environ.pop("UNIQ_RETRACTION_HASH_SECRET", None)
        else:
            os.environ["UNIQ_RETRACTION_HASH_SECRET"] = previous_secret

    return _report_and_exit()


if __name__ == "__main__":
    raise SystemExit(main())
