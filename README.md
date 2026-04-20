# UniQ — Unified Questionnaire Intelligence

An AI-powered engine that unifies fragmented healthcare questionnaire data into clean,
standardized, FHIR-compliant clinical datasets.

**The problem:** Every telehealth platform, clinical trial, and insurance company collects
questionnaire data where the same question exists under dozens of different IDs across
survey versions. Longitudinal analysis becomes impossible.

**The solution:** UniQ automatically classifies questions into clinical categories,
normalizes answer variants across languages, and exports unified data as CSV, JSON, or
FHIR R4 with ICD-10, SNOMED CT, RxNorm, and LOINC codes.

Built for the Wellster Healthtech Hackathon 2025.

## Repository Structure

```
UniQ/
├── wellster-pipeline/       # The core product — AI engine + Streamlit app
│   ├── src/                 # Pipeline source code
│   ├── pipeline.py          # Orchestrator
│   ├── config.py            # Configuration
│   └── STATUS.md            # Strategic project documentation
│
├── uniq-video/              # Remotion pitch video
│   ├── src/                 # Video source (React/Remotion)
│   └── VIDEO_BRIEF.md       # Video creative brief
│
└── agent.md / hackathon.md  # Original hackathon context
```

## Quick Start — Pipeline

```bash
cd wellster-pipeline

# 1. Create virtual environment + install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Add your questionnaire data
# Place a CSV/TSV in `data/raw/` and point RAW_DATA_FILE in config.py to it.
# Expected columns: user_id, question_id, question_en, answer_value, product, etc.
# See STATUS.md for the full schema.

# 4. Run the pipeline
python pipeline.py

# 5. Launch the Streamlit demo
streamlit run src/demo.py
```

**Note on data:** Raw patient data is excluded from this repo for privacy reasons.
Output files (`wellster-pipeline/output/`) regenerate automatically when you run the pipeline.

## Quick Start — Video

```bash
cd uniq-video
npm install
npm run dev    # Open http://localhost:3000
```

## Key Numbers

- **134,000** patient survey rows processed
- **4,553** fragmented question IDs → **26** clinical categories
- **416** answer variants → **164** canonical labels
- **99.9%** deterministic parsing · **2** AI calls total · **$0.10** processing cost
- **3,731** FHIR R4 resources generated with real medical codes

## License

MIT
