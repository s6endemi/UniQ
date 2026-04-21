"""
Configuration for the Wellster Unified Data Pipeline.

Centralizes file paths, API settings, and clinical taxonomy.
All paths are relative to the project root (wellster-pipeline/).
"""

import os
from pathlib import Path

# --- Load .env if present ---
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Raw data file — the Wellster CSV export (set to latest dataset)
RAW_DATA_FILE = DATA_RAW_DIR / "treatment_answer.csv"

# Output files
MAPPING_TABLE = OUTPUT_DIR / "mapping_table.csv"
PATIENTS_TABLE = OUTPUT_DIR / "patients.csv"
TREATMENT_EPISODES_TABLE = OUTPUT_DIR / "treatment_episodes.csv"
BMI_TIMELINE_TABLE = OUTPUT_DIR / "bmi_timeline.csv"
SURVEY_UNIFIED_TABLE = OUTPUT_DIR / "survey_unified.csv"
MEDICATION_HISTORY_TABLE = OUTPUT_DIR / "medication_history.csv"
QUALITY_REPORT_TABLE = OUTPUT_DIR / "quality_report.csv"
UNIQUE_QUESTIONS_FILE = OUTPUT_DIR / "unique_questions.csv"
DISCOVERY_RESULTS_FILE = OUTPUT_DIR / "discovery_results.json"
INSPECTION_REPORT = OUTPUT_DIR / "data_inspection.txt"

# --- API Settings ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-sonnet-4-6"
LLM_BATCH_SIZE = 30
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 2  # seconds, exponential backoff


def get_agent_mode() -> str:
    """Runtime agent selector for `/chat`.

    Read from the live environment rather than freezing a module-level
    constant so local eval harnesses can flip between v1 and v2 inside the
    same Python process.
    """
    return os.environ.get("UNIQ_AGENT_MODE", "v1").strip().lower() or "v1"

# --- Clinical Taxonomy ---
# Populated after Step 3 discovery + team review.
# Each key = category name, value = definition for the LLM classifier.
CLINICAL_TAXONOMY: dict[str, str] = {}
