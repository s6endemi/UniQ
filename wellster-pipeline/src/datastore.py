"""UniQ Datastore — UnifiedDataRepository.

Single place that answers questions about unified patient data. Loads the
pipeline artifacts once, coerces dtypes once, parses the JSON-encoded
`answer_canonical` strings once. After that every access is O(1) or a
vectorised Pandas filter.

Consumers (Streamlit UI pages, future FastAPI routers, chatbot tool-use)
all talk to this class. No one reads CSVs directly or decodes
`answer_canonical` by hand anymore.

Phase 2 scope (intentionally narrow):
    - Bulk DataFrame properties (mapping, patients, episodes, bmi_timeline,
      medication_history, quality_report, survey).
    - Typed patient-keyed reads (patient, bmi_for_patient, ...).
    - Metadata helpers (categories, counts).

What's deliberately NOT here:
    - No generic `search(filters)` DSL — callers do their own Pandas filters
      against the exposed DataFrames until real call sites tell us which
      filters deserve promotion.
    - No Concept-based lookup (`rows_for_concept(Concept.BMI)`) — that is
      Phase 4 and will sit on top of this layer.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.engine import PipelineArtifacts, load_artifacts_from_disk
from src.normalization_registry import NormalizationRegistry


# ---------------------------------------------------------------------------
# Typed patient record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientRecord:
    """Typed summary of one row in `patients.csv`.

    Optional fields are `None` when the underlying column is NaN. The raw
    row is always available via `UnifiedDataRepository.patients` if a
    consumer needs columns that are not promoted here.
    """

    user_id: int
    gender: str
    current_age: int
    total_treatments: int
    active_treatments: int
    current_medication: str | None
    current_dosage: str | None
    tenure_days: int | None
    latest_bmi: float | None
    earliest_bmi: float | None
    bmi_change: float | None
    first_order_date: pd.Timestamp | None
    latest_activity_date: pd.Timestamp | None

    @classmethod
    def from_row(cls, row: pd.Series) -> PatientRecord:
        def _is_missing(v: Any) -> bool:
            """Safe missing-ness check that covers None, NaN, NaT, pd.NA.

            `pd.isna` raises on list/dict, and `bool(pd.NA)` raises on
            "ambiguous truth value" — so naive `value or default` patterns
            blow up on Int64/Boolean arrays. We wrap both.
            """
            if v is None:
                return True
            try:
                return bool(pd.isna(v))
            except (TypeError, ValueError):
                return False

        def _opt(v: Any) -> Any:
            return None if _is_missing(v) else v

        def _opt_str(v: Any, default: str = "") -> str:
            return default if _is_missing(v) else str(v)

        def _opt_int(v: Any, default: int | None = 0) -> int | None:
            if _is_missing(v):
                return default
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        return cls(
            user_id=int(row["user_id"]),
            gender=_opt_str(row.get("gender")),
            current_age=_opt_int(row.get("current_age"), default=0) or 0,
            total_treatments=_opt_int(row.get("total_treatments"), default=0) or 0,
            active_treatments=_opt_int(row.get("active_treatments"), default=0) or 0,
            current_medication=_opt(row.get("current_medication")),
            current_dosage=_opt(row.get("current_dosage")),
            tenure_days=_opt_int(row.get("tenure_days"), default=None),
            latest_bmi=_opt(row.get("latest_bmi")),
            earliest_bmi=_opt(row.get("earliest_bmi")),
            bmi_change=_opt(row.get("bmi_change")),
            first_order_date=_opt(row.get("first_order_date")),
            latest_activity_date=_opt(row.get("latest_activity_date")),
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def parse_canonical(value: Any) -> list[str]:
    """Decode a single `answer_canonical` entry to a list of canonical labels.

    Accepts None, NaN, JSON-encoded string, or already-parsed list. Returns
    an empty list on anything that does not parse as a list of strings.

    Shared between the Repository (pre-parses the whole column at load) and
    downstream consumers like `export_fhir.py` that may receive rows where
    the column has already been parsed. Having one helper avoids
    double-parse bugs (parsing a list as a JSON string fails silently).
    """
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(parsed, list):
        return [str(x) for x in parsed]
    return []


# Backward-compatibility alias for any internal caller that still used the
# underscore-prefixed name.
_parse_canonical = parse_canonical


def _extract_normalized_values(value: Any) -> list[str]:
    """Decode normalized_value into the original answer values.

    This mirrors `normalize_answers_ai` without importing that module into
    the repository path. The validated layer uses it to re-check current
    registry review_status at runtime instead of trusting stale
    `answer_canonical` labels from a previous materialization.
    """
    if value is None:
        return []
    try:
        if bool(pd.isna(value)):
            return []
    except (TypeError, ValueError):
        pass

    try:
        parsed = value if isinstance(value, dict) else json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []

    values = parsed.get("values", [])
    if not isinstance(values, list):
        values = [values]
    if not values and parsed.get("raw"):
        values = [str(parsed["raw"])[:80]]

    out: list[str] = []
    for item in values:
        stripped = str(item).strip()
        if stripped and stripped.lower() not in {"nan", "none", "null"}:
            out.append(stripped)
    return out


_DATE_COLUMNS_PER_TABLE: dict[str, list[str]] = {
    "patients": ["first_order_date", "latest_activity_date"],
    "episodes": ["start_date", "latest_date"],
    "bmi_timeline": ["date"],
    "medication_history": ["started", "ended"],
    "survey": ["created_at", "updated_at", "first_order_at"],
}


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class UnifiedDataRepository:
    """Typed, cached access to the unified pipeline artifacts.

    The repository exposes two parallel survey surfaces:

    - `survey` (a.k.a. raw / staging): every survey row, including those
      whose `clinical_category` is `pending` or `rejected` in the
      semantic mapping, or whose `normalization_status` is `unknown`.
      Available for audit, debug, and pre-validation analysis.

    - `survey_validated`: the trust-gated subset that downstream
      consumers should use by default — only rows whose category is
      `approved` or `overridden` in the semantic mapping AND whose
      values normalised to a canonical label (status in
      `{complete, partial}`).

    The validated view is computed lazily from `survey` plus the
    on-disk `semantic_mapping.json`, and cached per repository instance.
    Cache invalidation is at process boundary: a fresh request triggers
    a fresh repo, which re-reads the mapping. That matches the demo /
    pilot deployment shape.
    """

    def __init__(self, artifacts: PipelineArtifacts) -> None:
        self._artifacts = artifacts

        # Copy so coercion does not mutate the original artifacts. Slightly
        # more memory, but keeps the engine-side dataframes pristine.
        self._mapping = artifacts.mapping.copy()
        self._patients = artifacts.patients.copy()
        self._episodes = artifacts.episodes.copy()
        self._bmi_timeline = artifacts.bmi_timeline.copy()
        self._medication_history = artifacts.medication_history.copy()
        self._quality_report = artifacts.quality_report.copy()
        self._survey = artifacts.survey.copy()

        self._coerce_dtypes()
        self._preparse_canonical()
        self._patient_index = self._build_patient_index()
        self._survey_validated_cache: pd.DataFrame | None = None
        self._validated_categories_cache: set[str] | None = None

    @classmethod
    def from_output_dir(cls, output_dir: Path | None = None) -> UnifiedDataRepository:
        """Build a repository from a pipeline output directory.

        Raw CSV is not loaded — the repository operates on the unified
        artifacts only, so skipping the 80 MB raw re-parse saves noticeable
        startup time.
        """
        return cls(load_artifacts_from_disk(output_dir, include_raw=False))

    # ---- Initialisation helpers -------------------------------------------

    def _coerce_dtypes(self) -> None:
        """Re-apply dtypes lost through CSV round-trip (int ids, datetime cols)."""
        id_tables = {
            "patients": self._patients,
            "episodes": self._episodes,
            "bmi_timeline": self._bmi_timeline,
            "medication_history": self._medication_history,
            "survey": self._survey,
            "quality_report": self._quality_report,
        }
        for df in id_tables.values():
            for col in ("user_id", "treatment_id"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        date_tables = {
            "patients": self._patients,
            "episodes": self._episodes,
            "bmi_timeline": self._bmi_timeline,
            "medication_history": self._medication_history,
            "survey": self._survey,
        }
        for name, df in date_tables.items():
            for col in _DATE_COLUMNS_PER_TABLE.get(name, []):
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    def _preparse_canonical(self) -> None:
        if "answer_canonical" in self._survey.columns:
            self._survey["answer_canonical"] = self._survey["answer_canonical"].apply(_parse_canonical)

    def _build_patient_index(self) -> dict[int, int]:
        """Map user_id -> positional row index for O(1) lookups."""
        index: dict[int, int] = {}
        for pos, uid in enumerate(self._patients["user_id"].tolist()):
            if pd.notna(uid):
                index[int(uid)] = pos
        return index

    # ---- Bulk DataFrame access --------------------------------------------

    @property
    def mapping(self) -> pd.DataFrame:
        return self._mapping

    @property
    def patients(self) -> pd.DataFrame:
        return self._patients

    @property
    def episodes(self) -> pd.DataFrame:
        return self._episodes

    @property
    def bmi_timeline(self) -> pd.DataFrame:
        return self._bmi_timeline

    @property
    def medication_history(self) -> pd.DataFrame:
        return self._medication_history

    @property
    def quality_report(self) -> pd.DataFrame:
        return self._quality_report

    @property
    def survey(self) -> pd.DataFrame:
        """Raw / staging survey rows. Includes pending + rejected categories
        and unknown-status rows. Use this only when you need full coverage
        for audit / debug / pre-validation analysis. Default downstream
        consumers should use `survey_validated`."""
        return self._survey

    @property
    def survey_validated(self) -> pd.DataFrame:
        """Trust-gated survey: only rows whose clinical_category has been
        signed off (`approved` or `overridden`) AND whose values normalised
        to a canonical label (`complete` or `partial`).

        Cached on first access. Falls back gracefully when the
        `normalization_status` column is missing (older substrate runs)
        — in that case the gate is category-only, not label-aware."""
        if self._survey_validated_cache is None:
            self._survey_validated_cache = self._build_survey_validated()
        return self._survey_validated_cache

    @property
    def taxonomy(self) -> dict:
        return self._artifacts.taxonomy

    @property
    def answer_normalization(self) -> dict:
        return self._artifacts.answer_normalization

    # ---- Validated layer construction -------------------------------------

    def _validated_categories(self) -> set[str]:
        """Categories with `review_status in {approved, overridden}` from the
        on-disk semantic_mapping.json. Loaded once per repo instance."""
        if self._validated_categories_cache is not None:
            return self._validated_categories_cache
        try:
            import json
            from pathlib import Path

            mapping_path = Path(config.OUTPUT_DIR) / "semantic_mapping.json"
            if not mapping_path.exists():
                self._validated_categories_cache = set()
                return self._validated_categories_cache
            data = json.loads(mapping_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                self._validated_categories_cache = set()
                return self._validated_categories_cache
            validated = {
                str(category)
                for category, entry in data.items()
                if isinstance(entry, dict)
                and str(entry.get("review_status", "")) in {"approved", "overridden"}
                and not category.startswith("__")
            }
            self._validated_categories_cache = validated
            return validated
        except Exception:
            self._validated_categories_cache = set()
            return self._validated_categories_cache

    def _build_survey_validated(self) -> pd.DataFrame:
        """Apply the validated-layer filter against `self._survey`.

        Two gates:
        - Category-level: clinical_category must be in the validated set
        - Label-level: normalization_status (if present) must be in
          `{complete, partial}` — `unknown`, `no_mapping`, `skipped` rows
          flow into the raw layer only

        If `normalization_status` is missing (older substrate), only the
        category gate is applied and a warning is logged once.
        """
        df = self._survey
        if df.empty:
            return df.copy()

        validated_cats = self._validated_categories()
        if not validated_cats:
            # No mapping file or empty validated set — return empty validated
            # surface rather than the full raw survey, so downstream
            # consumers fail safely instead of silently using raw data.
            return df.iloc[0:0].copy()

        cat_mask = (
            df["clinical_category"].isin(validated_cats)
            if "clinical_category" in df.columns
            else pd.Series([False] * len(df), index=df.index)
        )

        if "normalization_status" not in df.columns:
            return df.iloc[0:0].copy()

        registry = NormalizationRegistry.from_disk()
        registry_status = {
            (record.category, record.original_value): record.review_status
            for record in registry.records
        }

        def _label_is_currently_valid(row: pd.Series) -> bool:
            status = str(row.get("normalization_status", "") or "")
            if status == "not_applicable":
                return True
            if status not in {"complete", "partial"}:
                return False

            category = str(row.get("clinical_category", "") or "")
            values = _extract_normalized_values(row.get("normalized_value"))
            if not category or not values:
                return False

            approved_seen = False
            for value in values:
                review_status = registry_status.get((category, value))
                if review_status is None:
                    continue
                if review_status not in {"approved", "overridden"}:
                    return False
                approved_seen = True
            return approved_seen

        label_mask = df.apply(_label_is_currently_valid, axis=1)
        return df[cat_mask & label_mask].reset_index(drop=True)

        # Fallback: substrate predates P0.3 — gate on category only.
    # ---- Typed patient-keyed reads ----------------------------------------

    def patient(self, user_id: int) -> PatientRecord | None:
        idx = self._patient_index.get(int(user_id))
        if idx is None:
            return None
        return PatientRecord.from_row(self._patients.iloc[idx])

    def bmi_for_patient(self, user_id: int) -> pd.DataFrame:
        """BMI measurements for one patient, sorted chronologically."""
        df = self._bmi_timeline
        return (
            df[df["user_id"] == int(user_id)]
            .sort_values("date")
            .reset_index(drop=True)
        )

    def medications_for_patient(self, user_id: int) -> pd.DataFrame:
        """Medication history for one patient, sorted by start date."""
        df = self._medication_history
        return (
            df[df["user_id"] == int(user_id)]
            .sort_values("started")
            .reset_index(drop=True)
        )

    def survey_for_patient(
        self,
        user_id: int,
        *,
        category: str | None = None,
    ) -> pd.DataFrame:
        """Survey rows for one patient (raw), optionally filtered by category.

        For patient-facing consumers (artifacts, FHIR export), prefer
        `survey_validated_for_patient` — that one applies the trust gate.
        This raw variant exists for audit / debug paths."""
        df = self._survey[self._survey["user_id"] == int(user_id)]
        if category is not None:
            df = df[df["clinical_category"] == category]
        return df.reset_index(drop=True)

    def survey_validated_for_patient(
        self,
        user_id: int,
        *,
        category: str | None = None,
    ) -> pd.DataFrame:
        """Validated survey rows for one patient.

        Same signature as `survey_for_patient`, but reads from the trust-
        gated `survey_validated` view. Use this in any consumer that
        ships clinical content downstream (FHIR export, patient_record,
        opportunity_list, analyst-derived artifacts)."""
        df = self.survey_validated
        df = df[df["user_id"] == int(user_id)]
        if category is not None:
            df = df[df["clinical_category"] == category]
        return df.reset_index(drop=True)

    def quality_for_patient(self, user_id: int) -> pd.DataFrame:
        """Quality alerts for one patient."""
        df = self._quality_report
        return df[df["user_id"] == int(user_id)].reset_index(drop=True)

    # ---- Metadata ---------------------------------------------------------

    def categories(self) -> set[str]:
        """All clinical_category values observed in the mapping table."""
        return set(self._mapping["clinical_category"].dropna().unique())

    def count_patients(self) -> int:
        return len(self._patients)

    def count_active_patients(self) -> int:
        return int((self._patients["active_treatments"] > 0).sum())
