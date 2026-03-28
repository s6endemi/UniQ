"""
Step 2 — Load & Inspect Raw Wellster Data

Clinical purpose: Establish a clean, validated dataframe from raw survey exports.
Before any analytics can happen, we need to understand the data shape, quality,
and edge cases — especially date ranges, null patterns, and format inconsistencies
that will affect downstream BMI tracking and treatment analysis.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


# Columns that should be parsed as datetime
DATETIME_COLS = ["created_at", "first_order_at", "updated_at"]

# Columns that should be numeric
NUMERIC_COLS = ["current_age", "n_orders", "product_qty", "answer_value_height", "answer_value_weight"]

# Categorical columns to summarize
CATEGORICAL_COLS = ["t_status", "product", "order_type", "brand", "response_type", "indication", "gender"]


def detect_separator(file_path: Path) -> str:
    """Auto-detect CSV vs TSV by reading the first line."""
    with open(file_path, "r", encoding="utf-8") as f:
        header = f.readline()
    if "\t" in header and header.count("\t") > header.count(","):
        return "\t"
    return ","


def load_raw_data(file_path: Path) -> pd.DataFrame | None:
    """Load raw data file with auto-detected separator, proper encoding, and type handling."""
    if not file_path.exists():
        print(f"[ERROR] Data file not found: {file_path}")
        print(f"        Place your data file at: {config.DATA_RAW_DIR}/")
        return None

    sep = detect_separator(file_path)
    fmt = "TSV" if sep == "\t" else "CSV"
    print(f"[Step 1] Loading data from {file_path.name} (detected {fmt})...")

    try:
        df = pd.read_csv(file_path, sep=sep, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        print("[WARN] UTF-8 failed, trying latin-1 encoding...")
        df = pd.read_csv(file_path, sep=sep, encoding="latin-1", low_memory=False)

    raw_count = len(df)
    print(f"[Step 1] Raw file: {raw_count:,} rows x {len(df.columns)} columns")

    # Drop orphan rows where user_id is null (artifact from spreadsheet export)
    orphan_count = df["user_id"].isna().sum()
    if orphan_count > 0:
        df = df.dropna(subset=["user_id"]).reset_index(drop=True)
        print(f"[Step 1] Removed {orphan_count} orphan rows (null user_id) -> {len(df):,} rows")

    # Parse datetime columns — handles mixed formats (with/without UTC, with/without microseconds)
    for col in DATETIME_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # Parse numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Cast question_id to int (loaded as float due to nulls in orphan rows)
    if "question_id" in df.columns:
        df["question_id"] = df["question_id"].astype(int)

    # Ensure answer_value_array exists (some exports omit it)
    if "answer_value_array" not in df.columns:
        df["answer_value_array"] = "[]"
        print("[Step 1] Added missing answer_value_array column")

    print(f"[Step 1] Loaded {len(df):,} clean rows x {len(df.columns)} columns")
    return df


def inspect_data(df: pd.DataFrame) -> str:
    """Generate a comprehensive inspection report of the loaded data."""
    lines: list[str] = []

    def section(title: str) -> None:
        lines.append(f"\n{'='*60}")
        lines.append(f"  {title}")
        lines.append(f"{'='*60}")

    # --- Shape ---
    section("DATA SHAPE")
    lines.append(f"Total rows:            {len(df):,}")
    lines.append(f"Total columns:         {len(df.columns)}")
    lines.append(f"Unique patients:       {df['user_id'].nunique():,}")
    lines.append(f"Unique treatments:     {df['treatment_id'].nunique():,}")
    lines.append(f"Unique surveys:        {df['survey_id'].nunique():,}")
    lines.append(f"Unique question IDs:   {df['question_id'].nunique():,}")
    lines.append(f"Rows per patient:      {len(df) / df['user_id'].nunique():.1f} avg")

    # --- Date Range ---
    section("DATE RANGE")
    for col in DATETIME_COLS:
        if col in df.columns and df[col].notna().any():
            lines.append(f"{col}:")
            lines.append(f"  Min: {df[col].min()}")
            lines.append(f"  Max: {df[col].max()}")
            lines.append(f"  Non-null: {df[col].notna().sum():,}")

    # --- Categorical Distributions ---
    section("CATEGORICAL DISTRIBUTIONS")
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            vc = df[col].value_counts(dropna=False)
            lines.append(f"\n{col} ({vc.shape[0]} unique):")
            for val, count in vc.items():
                pct = count / len(df) * 100
                lines.append(f"  {val!s:45s} {count:>7,}  ({pct:.1f}%)")

    # --- Null Counts ---
    section("NULL / MISSING VALUES")
    null_counts = df.isnull().sum()
    null_pct = (df.isnull().sum() / len(df) * 100).round(1)
    for col in df.columns:
        marker = " <<<" if null_pct[col] > 50 else ""
        lines.append(f"  {col:35s} {null_counts[col]:>7,} / {len(df):>7,}  ({null_pct[col]:5.1f}%){marker}")

    # --- Numeric Stats ---
    section("NUMERIC COLUMN STATS")
    for col in NUMERIC_COLS:
        if col in df.columns and df[col].notna().any():
            lines.append(f"\n{col}:")
            lines.append(f"  Count:  {df[col].notna().sum():,}")
            lines.append(f"  Mean:   {df[col].mean():.2f}")
            lines.append(f"  Median: {df[col].median():.2f}")
            lines.append(f"  Min:    {df[col].min():.2f}")
            lines.append(f"  Max:    {df[col].max():.2f}")
            lines.append(f"  Std:    {df[col].std():.2f}")

    # --- Semantic Duplicate Questions ---
    section("SEMANTIC DUPLICATE QUESTIONS (same text, different IDs)")
    qt = df.groupby("question_en")["question_id"].nunique().sort_values(ascending=False)
    dupes = qt[qt > 1]
    lines.append(f"Questions with multiple IDs: {len(dupes)} (out of {len(qt)} unique texts)")
    for text, n_ids in dupes.head(10).items():
        ids = sorted(df[df["question_en"] == text]["question_id"].unique())
        lines.append(f"\n  [{n_ids} IDs] {text[:90]}...")
        lines.append(f"    IDs: {ids[:8]}{'...' if len(ids) > 8 else ''}")

    # --- Answer Value Format Samples ---
    section("ANSWER VALUE FORMAT ANALYSIS")
    # BMI / JSON
    bmi_rows = df[df["answer_value_height"].notna()]
    lines.append(f"BMI rows (height+weight populated): {len(bmi_rows)}")
    # File uploads
    file_mask = df["answer_value"].astype(str).str.contains("AnswerFile|Später hochladen|Upload later", na=False)
    lines.append(f"File upload / deferred rows:        {file_mask.sum()}")
    # Non-empty answer_value_array
    arr_non_empty = df["answer_value_array"].astype(str).apply(lambda x: x not in ("[]", "", "nan"))
    lines.append(f"Non-empty answer_value_array:       {arr_non_empty.sum()}")

    # --- Patient Distribution ---
    section("PATIENT DISTRIBUTION")
    multi = df.groupby("user_id")["treatment_id"].nunique()
    lines.append(f"Patients with 1 treatment:   {(multi == 1).sum()}")
    lines.append(f"Patients with 2 treatments:  {(multi == 2).sum()}")
    lines.append(f"Patients with 3+ treatments: {(multi >= 3).sum()}")
    rpp = df.groupby("user_id").size()
    lines.append(f"\nRows per patient — mean: {rpp.mean():.1f}, median: {rpp.median():.0f}, min: {rpp.min()}, max: {rpp.max()}")

    # --- Sample Rows ---
    section("SAMPLE ROWS (first 5)")
    sample_cols = ["user_id", "treatment_id", "question_id", "question_en", "answer_value", "product", "created_at"]
    available = [c for c in sample_cols if c in df.columns]
    lines.append(df[available].head(5).to_string(index=False))

    # --- Column List ---
    section("ALL COLUMNS & DTYPES")
    for col in df.columns:
        lines.append(f"  {col:35s} {str(df[col].dtype)}")

    report = "\n".join(lines)
    return report


def run_load() -> pd.DataFrame | None:
    """Execute the full load & inspect step."""
    df = load_raw_data(config.RAW_DATA_FILE)
    if df is None:
        return None

    report = inspect_data(df)
    print(report)

    # Save inspection report
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.INSPECTION_REPORT.write_text(report, encoding="utf-8")
    print(f"\n[Step 1] Inspection report saved to {config.INSPECTION_REPORT}")

    return df


if __name__ == "__main__":
    run_load()
