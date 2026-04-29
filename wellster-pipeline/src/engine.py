"""UniQ Engine — single entry point for the pipeline.

One function, `run_pipeline()`, executes the full flow:
    load -> classify -> normalize -> answer_normalize -> unify -> quality

It returns a typed `PipelineArtifacts` bundle with every produced table and
metadata artifact. Both the CLI (`pipeline.py`) and the Streamlit demo
(`src/demo.py`) call this function — there is no second orchestrator.

Incremental-mode guarantee (preserved from the original pipeline):
    If `taxonomy.json` and `mapping_table.csv` already exist in
    `config.OUTPUT_DIR`, the validated taxonomy is NOT overwritten. Only
    previously-unseen question texts go to the classifier.

Path handling (Phase 1 scope):
    `raw_path` is pluggable (needed for the Streamlit upload flow).
    `output_dir` still honours `config.OUTPUT_DIR`; downstream modules
    reference derived path constants bound at import time. Making output_dir
    fully pluggable is part of Phase 3 (Repository).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.classify_ai import run_classification
from src.load import load_raw_data
from src.normalize import normalize_answers
from src.normalize_answers_ai import normalize_answers_ai
from src.quality import run_quality
from src.semantic_mapping_ai import generate_semantic_mapping
from src.unify import run_unify


ProgressCallback = Callable[[str], None]


@dataclass
class PipelineArtifacts:
    """Every dataframe and artifact produced by a single pipeline run."""

    raw: pd.DataFrame
    mapping: pd.DataFrame
    survey: pd.DataFrame
    patients: pd.DataFrame
    episodes: pd.DataFrame
    bmi_timeline: pd.DataFrame
    medication_history: pd.DataFrame
    quality_report: pd.DataFrame
    taxonomy: dict = field(default_factory=dict)
    answer_normalization: dict = field(default_factory=dict)
    semantic_mapping: dict = field(default_factory=dict)
    output_dir: Path = field(default_factory=lambda: config.OUTPUT_DIR)

    def category_names(self) -> set[str]:
        """Convenience: unique clinical_category values in the mapping."""
        return set(self.mapping["clinical_category"].dropna().unique())


def _noop(_: str) -> None:
    pass


def run_pipeline(
    raw_path: Path | None = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> PipelineArtifacts:
    """Run the full UniQ pipeline end-to-end.

    Args:
        raw_path: Path to raw CSV/TSV. Defaults to `config.RAW_DATA_FILE`.
        on_progress: Optional callback invoked with a short status string
            before each step. Used by the Streamlit demo for live progress.

    Returns:
        `PipelineArtifacts` bundling all produced tables plus `taxonomy.json`
        and `answer_normalization.json` as parsed dicts.
    """
    progress = on_progress or _noop
    raw_path = raw_path or config.RAW_DATA_FILE
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    progress("Loading data")
    raw = load_raw_data(raw_path)
    if raw is None:
        raise FileNotFoundError(f"Raw data file not found: {raw_path}")

    progress("Classifying questions (AI)")
    mapping = run_classification(raw)

    progress("Normalizing answer formats")
    survey = normalize_answers(raw, mapping)

    progress("Normalizing answer values (AI)")
    survey, answer_norm = normalize_answers_ai(survey)
    # The AI normalizer mutates `survey` in place but does not persist it;
    # we re-save so downstream file-based consumers see the canonical column.
    survey.to_csv(config.SURVEY_UNIFIED_TABLE, index=False, encoding="utf-8")

    progress("Generating semantic mapping (AI, advisory)")
    taxonomy_doc = _load_json_if_exists(config.OUTPUT_DIR / "taxonomy.json")
    taxonomy_categories = taxonomy_doc.get("categories", []) if taxonomy_doc else []
    semantic_mapping = generate_semantic_mapping(taxonomy_categories)

    progress("Building unified tables")
    patients, episodes, bmi_df, med_hist = run_unify(survey)

    progress("Running quality checks")
    quality = run_quality(patients, bmi_df, episodes, med_hist)

    progress("Applying active retractions")
    try:
        from src.retractions import apply_active_retractions_to_outputs

        retraction_result = apply_active_retractions_to_outputs()
        if retraction_result.get("total_rows_removed"):
            print(
                "[INFO] Applied active retractions "
                f"({retraction_result['total_rows_removed']} rows removed)"
            )
    except Exception as exc:
        print(
            "[WARN] active retractions could not be applied "
            f"({type(exc).__name__}: {exc})"
        )

    progress("Writing materialization manifest")
    try:
        from src.materialization_manifest import write_manifest

        write_manifest(save=True)
    except Exception as exc:
        print(
            "[WARN] materialization_manifest.json could not be written "
            f"({type(exc).__name__}: {exc})"
        )

    return PipelineArtifacts(
        raw=raw,
        mapping=mapping,
        survey=survey,
        patients=patients,
        episodes=episodes,
        bmi_timeline=bmi_df,
        medication_history=med_hist,
        quality_report=quality,
        taxonomy=taxonomy_doc,
        answer_normalization=answer_norm,
        semantic_mapping=semantic_mapping,
        output_dir=config.OUTPUT_DIR,
    )


def _load_json_if_exists(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


ARTIFACT_FILENAMES = {
    "mapping": "mapping_table.csv",
    "survey": "survey_unified.csv",
    "patients": "patients.csv",
    "episodes": "treatment_episodes.csv",
    "bmi_timeline": "bmi_timeline.csv",
    "medication_history": "medication_history.csv",
    "quality_report": "quality_report.csv",
    "taxonomy": "taxonomy.json",
    "answer_normalization": "answer_normalization.json",
    "semantic_mapping": "semantic_mapping.json",
}


def load_artifacts_from_disk(
    output_dir: Path | None = None,
    *,
    include_raw: bool = True,
) -> PipelineArtifacts:
    """Reconstruct a `PipelineArtifacts` bundle from a previous run.

    Used by the Streamlit demo's "View Existing Results" path and by tests
    that want to compare fresh runs against golden fixtures. When a caller
    passes a non-default `output_dir` (e.g., `tests/fixtures/golden/`), every
    artifact is read from that directory.

    `include_raw=False` skips re-parsing the raw CSV (~80 MB) and leaves
    `artifacts.raw` as an empty DataFrame. Callers that only need the
    unified tables (Repository, QueryService) should pass False to avoid the
    startup cost.
    """
    output_dir = output_dir or config.OUTPUT_DIR
    if include_raw and config.RAW_DATA_FILE.exists():
        raw = load_raw_data(config.RAW_DATA_FILE)
    else:
        raw = pd.DataFrame()
    return PipelineArtifacts(
        raw=raw,
        mapping=pd.read_csv(output_dir / ARTIFACT_FILENAMES["mapping"]),
        survey=pd.read_csv(output_dir / ARTIFACT_FILENAMES["survey"], low_memory=False),
        patients=pd.read_csv(output_dir / ARTIFACT_FILENAMES["patients"]),
        episodes=pd.read_csv(output_dir / ARTIFACT_FILENAMES["episodes"]),
        bmi_timeline=pd.read_csv(output_dir / ARTIFACT_FILENAMES["bmi_timeline"]),
        medication_history=pd.read_csv(output_dir / ARTIFACT_FILENAMES["medication_history"]),
        quality_report=pd.read_csv(output_dir / ARTIFACT_FILENAMES["quality_report"]),
        taxonomy=_load_json_if_exists(output_dir / ARTIFACT_FILENAMES["taxonomy"]),
        answer_normalization=_load_json_if_exists(output_dir / ARTIFACT_FILENAMES["answer_normalization"]),
        semantic_mapping=_load_json_if_exists(output_dir / ARTIFACT_FILENAMES["semantic_mapping"]),
        output_dir=output_dir,
    )
