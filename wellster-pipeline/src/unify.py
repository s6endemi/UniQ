"""
Step 6 — Build Unified Output Tables

Clinical purpose: Transform the normalized survey data into structured analytical tables
that enable patient-level longitudinal analysis. These tables answer questions like:
"How has this patient's BMI changed over time?" and "What medication journey did they take?"

Output tables:
  - patients.csv: One row per patient — demographics, tenure, current treatment, BMI change
  - treatment_episodes.csv: One row per treatment — lifecycle data
  - bmi_timeline.csv: Longitudinal BMI measurements per patient
  - medication_history.csv: Chronological medication journey
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def _extract_bmi(normalized_value: str) -> dict | None:
    """Extract BMI data from normalized_value JSON string."""
    try:
        parsed = json.loads(normalized_value)
        if "bmi" in parsed and parsed.get("parse_method") != "no_bmi_data":
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def build_bmi_timeline(survey: pd.DataFrame) -> pd.DataFrame:
    """Build longitudinal BMI measurements from unified survey data."""
    print("[Step 6] Building BMI timeline...")

    bmi_rows = survey[survey["clinical_category"] == "BMI_MEASUREMENT"].copy()
    bmi_data = []

    for _, row in bmi_rows.iterrows():
        parsed = _extract_bmi(row["normalized_value"])
        if parsed and "bmi" in parsed and parsed["bmi"] > 0:
            bmi_data.append({
                "user_id": int(row["user_id"]),
                "treatment_id": int(row["treatment_id"]),
                "date": row["created_at"],
                "height_cm": parsed.get("height_cm"),
                "weight_kg": parsed.get("weight_kg"),
                "bmi": parsed["bmi"],
                "product_at_time": row["product"],
                "data_quality_flag": _flag_bmi(parsed),
            })

    bmi_df = pd.DataFrame(bmi_data)
    if len(bmi_df) > 0:
        bmi_df["date"] = pd.to_datetime(bmi_df["date"], errors="coerce", utc=True)
        bmi_df = bmi_df.sort_values(["user_id", "date"]).reset_index(drop=True)

    bmi_df.to_csv(config.BMI_TIMELINE_TABLE, index=False, encoding="utf-8")
    print(f"[Step 6] BMI timeline: {len(bmi_df)} measurements for {bmi_df['user_id'].nunique()} patients")
    return bmi_df


def _flag_bmi(parsed: dict) -> str:
    """Flag suspicious BMI values."""
    bmi = parsed.get("bmi", 0)
    h = parsed.get("height_cm", 0)
    w = parsed.get("weight_kg", 0)

    if bmi < 15 or bmi > 80:
        return "bmi_out_of_range"
    if h and (h < 100 or h > 250):
        return "height_suspicious"
    if w and (w < 30 or w > 300):
        return "weight_suspicious"
    return "ok"


def build_treatment_episodes(survey: pd.DataFrame) -> pd.DataFrame:
    """Build one row per treatment episode with lifecycle data."""
    print("[Step 6] Building treatment episodes...")

    episodes = (
        survey.groupby("treatment_id")
        .agg(
            user_id=("user_id", "first"),
            product=("product", "first"),
            product_dosage=("product_dosage", "first"),
            indication=("indication", "first"),
            t_status=("t_status", "first"),
            order_type=("order_type", "first"),
            n_orders=("n_orders", "max"),
            brand=("brand", "first"),
            start_date=("created_at", "min"),
            latest_date=("updated_at", "max"),
            survey_count=("survey_id", "nunique"),
            question_count=("question_id", "nunique"),
        )
        .reset_index()
    )

    episodes["start_date"] = pd.to_datetime(episodes["start_date"], errors="coerce", utc=True)
    episodes["latest_date"] = pd.to_datetime(episodes["latest_date"], errors="coerce", utc=True)
    episodes["user_id"] = episodes["user_id"].astype(int)
    episodes["treatment_id"] = episodes["treatment_id"].astype(int)

    episodes.to_csv(config.TREATMENT_EPISODES_TABLE, index=False, encoding="utf-8")
    print(f"[Step 6] Treatment episodes: {len(episodes)} episodes for {episodes['user_id'].nunique()} patients")
    return episodes


def build_medication_history(episodes: pd.DataFrame) -> pd.DataFrame:
    """Build chronological medication journey per patient."""
    print("[Step 6] Building medication history...")

    episodes_sorted = episodes.sort_values(["user_id", "start_date"]).copy()
    rows = []

    for user_id, user_eps in episodes_sorted.groupby("user_id"):
        user_eps = user_eps.reset_index(drop=True)
        for i, ep in user_eps.iterrows():
            next_ep = user_eps.iloc[i + 1] if i + 1 < len(user_eps) else None
            ended = next_ep["start_date"] if next_ep is not None else pd.NaT
            duration = (ended - ep["start_date"]).days if pd.notna(ended) else None

            rows.append({
                "user_id": int(user_id),
                "product": ep["product"],
                "dosage": ep["product_dosage"],
                "started": ep["start_date"],
                "ended": ended,
                "duration_days": duration,
                "order_type": ep["order_type"],
                "n_orders": ep["n_orders"],
                "next_product": next_ep["product"] if next_ep is not None else None,
                "treatment_id": ep["treatment_id"],
            })

    med_hist = pd.DataFrame(rows)
    med_hist.to_csv(config.MEDICATION_HISTORY_TABLE, index=False, encoding="utf-8")
    print(f"[Step 6] Medication history: {len(med_hist)} entries for {med_hist['user_id'].nunique()} patients")
    return med_hist


def build_patients(survey: pd.DataFrame, bmi_df: pd.DataFrame, episodes: pd.DataFrame) -> pd.DataFrame:
    """Build one row per patient with demographics and derived metrics."""
    print("[Step 6] Building patient profiles...")

    # Use the latest of (created_at, updated_at, first_order_at) for activity range
    # first_order_at has timezone inconsistencies — use created_at as the reliable anchor
    patients = (
        survey.groupby("user_id")
        .agg(
            gender=("gender", "first"),
            current_age=("current_age", "first"),
            first_order_date=("created_at", "min"),
            latest_activity_date=("updated_at", "max"),
            total_orders=("n_orders", "max"),
        )
        .reset_index()
    )

    patients["first_order_date"] = pd.to_datetime(patients["first_order_date"], errors="coerce", utc=True)
    patients["latest_activity_date"] = pd.to_datetime(patients["latest_activity_date"], errors="coerce", utc=True)

    # Treatment counts
    treat_counts = episodes.groupby("user_id").agg(
        total_treatments=("treatment_id", "nunique"),
        active_treatments=("t_status", lambda x: (x == "in_progress").sum()),
    ).reset_index()
    patients = patients.merge(treat_counts, on="user_id", how="left")

    # Current medication (from most recent active treatment, or latest treatment)
    latest_active = (
        episodes.sort_values("latest_date", ascending=False)
        .groupby("user_id")
        .first()
        .reset_index()[["user_id", "product", "product_dosage"]]
    )
    latest_active.columns = ["user_id", "current_medication", "current_dosage"]
    patients = patients.merge(latest_active, on="user_id", how="left")

    # BMI metrics
    if len(bmi_df) > 0:
        bmi_sorted = bmi_df.sort_values(["user_id", "date"])
        latest_bmi = bmi_sorted.groupby("user_id").last()[["bmi"]].reset_index()
        latest_bmi.columns = ["user_id", "latest_bmi"]
        earliest_bmi = bmi_sorted.groupby("user_id").first()[["bmi"]].reset_index()
        earliest_bmi.columns = ["user_id", "earliest_bmi"]

        patients = patients.merge(latest_bmi, on="user_id", how="left")
        patients = patients.merge(earliest_bmi, on="user_id", how="left")
        patients["bmi_change"] = (patients["latest_bmi"] - patients["earliest_bmi"]).round(2)
    else:
        patients["latest_bmi"] = None
        patients["earliest_bmi"] = None
        patients["bmi_change"] = None

    # Patient tenure
    patients["tenure_days"] = (
        patients["latest_activity_date"] - patients["first_order_date"]
    ).dt.days

    patients["user_id"] = patients["user_id"].astype(int)
    patients["current_age"] = patients["current_age"].astype(int)

    patients.to_csv(config.PATIENTS_TABLE, index=False, encoding="utf-8")
    print(f"[Step 6] Patient profiles: {len(patients)} patients")
    return patients


def run_unify(survey: pd.DataFrame | None = None) -> tuple:
    """Execute the full unification step."""
    if survey is None:
        survey = pd.read_csv(config.SURVEY_UNIFIED_TABLE)

    bmi_df = build_bmi_timeline(survey)
    episodes = build_treatment_episodes(survey)
    med_hist = build_medication_history(episodes)
    patients = build_patients(survey, bmi_df, episodes)

    print(f"\n[Step 6] All unified tables saved to {config.OUTPUT_DIR}/")
    return patients, episodes, bmi_df, med_hist


if __name__ == "__main__":
    run_unify()
