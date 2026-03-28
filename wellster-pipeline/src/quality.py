"""
Step 7 — Data Quality Checks

Clinical purpose: Identify cross-temporal data quality issues that individual survey
responses can't catch. These are clinically meaningful signals — a BMI spike could
indicate a data entry error or a genuine concern; a subscription lapse could mean
a patient dropped off treatment without medical supervision.

These checks demonstrate that our unified dataset enables a level of patient safety
monitoring that fragmented data never could.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def check_bmi_spikes(bmi_df: pd.DataFrame) -> list[dict]:
    """Flag BMI changes > 5 points between consecutive measurements.

    Could be data entry error or genuine rapid weight change — either way
    worth clinical review.
    """
    issues = []
    if len(bmi_df) == 0:
        return issues

    bmi_sorted = bmi_df.sort_values(["user_id", "date"])

    for user_id, group in bmi_sorted.groupby("user_id"):
        if len(group) < 2:
            continue
        vals = group.reset_index(drop=True)
        for i in range(1, len(vals)):
            delta = abs(vals.loc[i, "bmi"] - vals.loc[i - 1, "bmi"])
            if delta > 5:
                issues.append({
                    "check_type": "bmi_spike",
                    "severity": "warning",
                    "user_id": int(user_id),
                    "treatment_id": int(vals.loc[i, "treatment_id"]),
                    "description": f"BMI changed by {delta:.1f} points between measurements",
                    "details": f"From {vals.loc[i-1, 'bmi']:.1f} to {vals.loc[i, 'bmi']:.1f}",
                })
    return issues


def check_bmi_gaps(patients: pd.DataFrame, bmi_df: pd.DataFrame) -> list[dict]:
    """Flag patients with 90+ day tenure but no recent BMI measurement.

    Regular BMI monitoring is essential for GLP-1 treatment effectiveness tracking.
    """
    issues = []
    if len(bmi_df) == 0:
        return issues

    long_tenure = patients[patients["tenure_days"] > 90]
    latest_bmi_dates = bmi_df.groupby("user_id")["date"].max().reset_index()
    latest_bmi_dates.columns = ["user_id", "last_bmi_date"]

    for _, patient in long_tenure.iterrows():
        uid = patient["user_id"]
        bmi_match = latest_bmi_dates[latest_bmi_dates["user_id"] == uid]
        if len(bmi_match) == 0:
            issues.append({
                "check_type": "bmi_gap",
                "severity": "warning",
                "user_id": int(uid),
                "treatment_id": None,
                "description": f"Patient has {patient['tenure_days']} day tenure but no BMI recorded",
                "details": "No BMI measurement found in data",
            })
    return issues


def check_medication_switches(med_hist: pd.DataFrame) -> list[dict]:
    """Flag undocumented medication switches.

    If a patient changes from Wegovy to Mounjaro without a survey capturing
    the reason, this is a clinical blind spot.
    """
    issues = []
    switches = med_hist[med_hist["next_product"].notna()].copy()

    for _, row in switches.iterrows():
        if row["product"] != row["next_product"]:
            issues.append({
                "check_type": "undocumented_switch",
                "severity": "info",
                "user_id": int(row["user_id"]),
                "treatment_id": int(row["treatment_id"]),
                "description": f"Medication switch: {row['product']} → {row['next_product']}",
                "details": f"Switch after {row['duration_days']} days" if row["duration_days"] else "Duration unknown",
            })
    return issues


def check_subscription_lapse(episodes: pd.DataFrame) -> list[dict]:
    """Flag active subscription treatments with no recent activity.

    Patients with order_type = 'Sub Re-Order' who haven't reordered in 60+ days
    despite t_status = 'in_progress'. Potential churn or compliance issue.
    """
    issues = []
    active_subs = episodes[
        (episodes["t_status"] == "in_progress") &
        (episodes["order_type"].isin(["Sub Re-Order", "Sub Start"]))
    ]

    for _, ep in active_subs.iterrows():
        if pd.notna(ep["latest_date"]) and pd.notna(ep["start_date"]):
            days_since = (pd.Timestamp.now(tz="UTC") - ep["latest_date"]).days
            if days_since > 60:
                issues.append({
                    "check_type": "subscription_lapse",
                    "severity": "warning",
                    "user_id": int(ep["user_id"]),
                    "treatment_id": int(ep["treatment_id"]),
                    "description": f"Active subscription with no activity for {days_since} days",
                    "details": f"Product: {ep['product']}, Last activity: {ep['latest_date']}",
                })
    return issues


def check_suspicious_bmi_values(bmi_df: pd.DataFrame) -> list[dict]:
    """Flag BMI values that are physiologically unlikely."""
    issues = []
    if len(bmi_df) == 0:
        return issues

    flagged = bmi_df[bmi_df["data_quality_flag"] != "ok"]
    for _, row in flagged.iterrows():
        issues.append({
            "check_type": "suspicious_bmi",
            "severity": "warning",
            "user_id": int(row["user_id"]),
            "treatment_id": int(row["treatment_id"]),
            "description": f"Suspicious BMI data: {row['data_quality_flag']}",
            "details": f"Height: {row['height_cm']}, Weight: {row['weight_kg']}, BMI: {row['bmi']}",
        })
    return issues


def run_quality(
    patients: pd.DataFrame | None = None,
    bmi_df: pd.DataFrame | None = None,
    episodes: pd.DataFrame | None = None,
    med_hist: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Run all quality checks and produce the quality report."""
    print("\n[Step 7] Running data quality checks...")

    # Load from files if not provided
    if patients is None:
        patients = pd.read_csv(config.PATIENTS_TABLE)
    if bmi_df is None:
        bmi_df = pd.read_csv(config.BMI_TIMELINE_TABLE)
        if "date" in bmi_df.columns:
            bmi_df["date"] = pd.to_datetime(bmi_df["date"], errors="coerce", utc=True)
    if episodes is None:
        episodes = pd.read_csv(config.TREATMENT_EPISODES_TABLE)
        for col in ["start_date", "latest_date"]:
            if col in episodes.columns:
                episodes[col] = pd.to_datetime(episodes[col], errors="coerce", utc=True)
    if med_hist is None:
        med_hist = pd.read_csv(config.MEDICATION_HISTORY_TABLE)

    all_issues = []
    all_issues.extend(check_bmi_spikes(bmi_df))
    all_issues.extend(check_bmi_gaps(patients, bmi_df))
    all_issues.extend(check_medication_switches(med_hist))
    all_issues.extend(check_subscription_lapse(episodes))
    all_issues.extend(check_suspicious_bmi_values(bmi_df))

    report = pd.DataFrame(all_issues)
    if len(report) == 0:
        report = pd.DataFrame(columns=["check_type", "severity", "user_id", "treatment_id", "description", "details"])

    report.to_csv(config.QUALITY_REPORT_TABLE, index=False, encoding="utf-8")

    # Summary
    print(f"[Step 7] Quality report: {len(report)} issues found")
    if len(report) > 0:
        severity_counts = report["severity"].value_counts()
        for sev, count in severity_counts.items():
            print(f"  {sev:15s} {count:>4}")
        check_counts = report["check_type"].value_counts()
        print(f"\n[Step 7] Issues by type:")
        for check, count in check_counts.items():
            print(f"  {check:30s} {count:>4}")

    print(f"[Step 7] Saved to {config.QUALITY_REPORT_TABLE}")
    return report


if __name__ == "__main__":
    run_quality()
