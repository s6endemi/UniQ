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

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Add your data to data/raw/ and point config.py to it
# Then run:
python pipeline.py

# Launch the demo
streamlit run src/demo.py
```

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
