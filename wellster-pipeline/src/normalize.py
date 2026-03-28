"""
Step 5 — Answer Normalization

Clinical purpose: Raw answer_value fields contain inconsistent formats — JSON objects,
German text, file hashes, confirmation strings, multi-select arrays. This step parses
each answer into a structured, queryable format based on its clinical category.
This enables downstream analytics: BMI trajectories, side effect tracking, compliance metrics.

Strategy: deterministic parsers per answer_type. No LLM needed (<5% would be free-text,
and we keep those raw).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.load import load_raw_data


def _parse_json_bmi(row: pd.Series) -> dict:
    """Parse BMI measurement from JSON answer_value or separate height/weight columns."""
    # Try JSON in answer_value first
    val = str(row.get("answer_value", ""))
    try:
        parsed = json.loads(val)
        if isinstance(parsed, dict) and "height" in parsed:
            return {
                "height_cm": float(parsed.get("height", 0)),
                "weight_kg": float(parsed.get("weight", 0)),
                "bmi": round(float(parsed.get("bmi", 0)), 2),
                "parse_method": "json",
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: use answer_value_height and answer_value_weight columns
    h = row.get("answer_value_height")
    w = row.get("answer_value_weight")
    if pd.notna(h) and pd.notna(w) and float(h) > 0:
        h, w = float(h), float(w)
        bmi = round(w / ((h / 100) ** 2), 2)
        return {"height_cm": h, "weight_kg": w, "bmi": bmi, "parse_method": "columns"}

    # This row is in BMI_MEASUREMENT category but has no BMI data (e.g. a consent text
    # that mentions BMI eligibility). Return what we have.
    return {"raw": val, "parse_method": "no_bmi_data"}


def _parse_file_upload(row: pd.Series) -> dict:
    """Classify file upload status."""
    val = str(row.get("answer_value", "")).strip()
    if val.lower() in ("später hochladen", "upload later", "upload photo later"):
        return {"status": "deferred"}
    if val.lower().startswith("answerfile#"):
        return {"status": "uploaded", "file_ref": val}
    if len(val) == 24 and val.isalnum():
        return {"status": "uploaded", "file_ref": val}
    if val.lower() in ("upload_later",):
        return {"status": "deferred"}
    if "upload photo immediately" in val.lower() or "sofort" in val.lower():
        return {"status": "uploaded_immediate"}
    return {"status": "unknown", "raw": val}


def _parse_confirmation(row: pd.Series) -> dict:
    """Parse consent/confirmation answers."""
    val = str(row.get("answer_value", "")).strip()
    if val:
        return {"confirmed": True}
    return {"confirmed": False}


def _parse_predefined(row: pd.Series) -> dict:
    """Parse predefined answer options. Handles single-select and multi-select."""
    answer_en = str(row.get("answer_en", "")).strip()
    answer_de = str(row.get("answer_de", "")).strip()
    arr_raw = str(row.get("answer_value_array", "")).strip()

    # Try to extract list from answer_value_array
    values = []
    if arr_raw and arr_raw not in ("[]", "", "nan"):
        # It's not valid JSON — it's like [item1,item2,item3]
        # But answer_value might be valid JSON array
        val = str(row.get("answer_value", "")).strip()
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                values = [str(v).strip() for v in parsed]
        except (json.JSONDecodeError, ValueError):
            pass

        if not values:
            # Parse the bracket-delimited format from answer_value_array
            inner = arr_raw.strip("[]")
            if inner:
                values = [v.strip() for v in inner.split(",")]

    if not values:
        # Single value — use answer_en or answer_de
        if answer_en and answer_en != "nan":
            values = [answer_en]
        elif answer_de and answer_de != "nan":
            values = [answer_de]

    return {
        "values": values,
        "values_de": [answer_de] if len(values) <= 1 else [],
        "is_multi": len(values) > 1,
    }


def _parse_free_text(row: pd.Series) -> dict:
    """Keep free-text answers raw — these would need LLM for structured extraction."""
    val = str(row.get("answer_value", "")).strip()
    answer_en = str(row.get("answer_en", "")).strip()
    return {"raw": val, "answer_en": answer_en if answer_en != "nan" else ""}


# Parser dispatch
PARSERS = {
    "json_structured": _parse_json_bmi,
    "file_upload": _parse_file_upload,
    "confirmation": _parse_confirmation,
    "predefined": _parse_predefined,
    "free_text": _parse_free_text,
}


def normalize_answers(df: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Apply category-specific parsers to all rows.

    Joins raw data with the mapping table, then normalizes each answer
    based on its answer_type.
    """
    print(f"\n[Step 5] Normalizing {len(df):,} answers...")

    # Merge with mapping
    merged = df.merge(
        mapping[["question_id", "clinical_category", "answer_type"]],
        on="question_id",
        how="left",
    )

    # Apply parsers
    normalized_values = []
    parse_methods = []

    for _, row in merged.iterrows():
        atype = row.get("answer_type", "free_text")
        parser = PARSERS.get(atype, _parse_free_text)
        try:
            result = parser(row)
        except Exception as e:
            result = {"error": str(e), "raw": str(row.get("answer_value", ""))}
        normalized_values.append(json.dumps(result, ensure_ascii=False))
        parse_methods.append(result.get("parse_method", atype))

    merged["normalized_value"] = normalized_values
    merged["parse_method"] = parse_methods

    # Stats
    method_counts = merged["parse_method"].value_counts()
    deterministic = len(merged) - method_counts.get("free_text", 0)
    pct = deterministic / len(merged) * 100
    print(f"[Step 5] Normalized {len(merged):,} rows. Deterministic: {pct:.1f}%")
    print(f"[Step 5] Parse methods:")
    for method, count in method_counts.items():
        print(f"  {method:25s} {count:>6,}  ({count / len(merged) * 100:.1f}%)")

    # Save
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(config.SURVEY_UNIFIED_TABLE, index=False, encoding="utf-8")
    print(f"[Step 5] Saved to {config.SURVEY_UNIFIED_TABLE}")

    return merged


def run_normalize(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Execute the normalization step."""
    if df is None:
        df = load_raw_data(config.RAW_DATA_FILE)
    mapping = pd.read_csv(config.MAPPING_TABLE)
    return normalize_answers(df, mapping)


if __name__ == "__main__":
    run_normalize()
