# Agno Zoning Starter

Starter repo for a production-oriented Agno workflow that converts zoning ordinances into a Gridics-style canonical representation and then exports the result into a workbook with families like:

- Zones - General / Uses / Parking / Use Capacity / Bonus
- Overlays - General / Uses / Parking / Use Capacity / Bonus
- Typologies - General / Uses / Parking / Use Capacity / Bonus

This repo is intentionally a **starter**:
- the orchestration skeleton is in place
- agents are defined with focused roles
- Pydantic schemas are ready for typed handoffs
- workbook export is scaffolded
- source extraction / cross-reference / QA hooks are stubbed for your implementation

The pipeline now uses a two-stage source flow:
- first it scrapes the source to local cache files
- then it parses the cached artifacts and runs extraction against them

If you have a vendor export workbook, you can also use that directly as input:
- point `--source-url` at the `.xlsx` file
- set `--source-kind excel`
- the loader will parse the export rows instead of scraping HTML

The cache contains:
- raw HTML: `*.html`
- source discovery: `*.discovery.json`
- parsed source document: `*.source.json`
- source chunks: `*.chunks.json`
- scrape metadata: `*.meta.json`
- run manifest: `manifest.json`
- step artifacts: `workflow_steps/01-load-source/01-input.json`, `workflow_steps/01-load-source/01-output.json`, etc.

The cache is also a source investigation bundle:
- `*.discovery.json` records candidate URLs and whether the page looked like a real content page
- `*.source.json` records what was actually parsed
- `*.chunks.json` records the exact text packets sent downstream
- `manifest.json` records the run configuration, resume step, and artifact paths
- `workflow_steps/` stores numbered step input/output files in execution order

If you do not pass `--cache-dir`, the runner now writes to a persistent default path:
`cache/<jurisdiction-slug>/<source-stem>/`

The runner will automatically clear stale cache artifacts when the source signature changes
(source URL, source kind, or `nodeId`), but it will keep the cache intact when you are
rerunning the same source and only changing the resume step.

To resume from a later step, pass `--start-from-step` with one of:
- `load-source`
- `intake`
- `extract`
- `qa`
- `export`

To invalidate a step and everything after it, pass `--invalidate-from-step` with one of:
- `load-source`
- `intake`
- `extract`
- `qa`
- `export`

## Why this shape

Agno supports typed data flow between steps, agent teams with structured outputs, and deterministic workflows built from agents, teams, and custom functions. That makes it a good fit for zoning ETL, where predictable multi-step processing matters more than free-form chat. See Agno's structured I/O, teams, and workflow patterns docs for the concepts this starter follows.

## Repo layout

```text
agno-zoning-starter/
├─ pyproject.toml
├─ .env.example
├─ README.md
├─ data/
│  └─ templates/
│     └─ zoning_template.xlsx
├─ scripts/
│  └─ run_pipeline.py
├─ src/
│  └─ zoning_agno/
│     ├─ config.py
│     ├─ models/
│     │  ├─ __init__.py
│     │  └─ schemas.py
│     ├─ prompts/
│     │  └─ instructions.py
│     ├─ tools/
│     │  ├─ __init__.py
│     │  ├─ workbook_tools.py
│     │  ├─ source_tools.py
│     │  └─ legal_tools.py
│     ├─ services/
│     │  ├─ __init__.py
│     │  ├─ template_loader.py
│     │  └─ pipeline_service.py
│     ├─ exporters/
│     │  ├─ __init__.py
│     │  └─ workbook_exporter.py
│     ├─ agents/
│     │  ├─ __init__.py
│     │  ├─ common.py
│     │  ├─ intake.py
│     │  ├─ extraction.py
│     │  ├─ qa.py
│     │  └─ teams.py
│     └─ workflows/
│        ├─ __init__.py
│        └─ zoning_pipeline.py
└─ tests/
   └─ test_schemas.py
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python3 scripts/run_pipeline.py \
  --source-url "https://library.municode.com/tx/abilene/codes/code_of_ordinances" \
  --jurisdiction "Abilene, TX" \
  --out ./out/abilene_standardized.xlsx

If the vendor provides an export workbook, use it directly:

```bash
python3 scripts/run_pipeline.py \
  --source-url ./cache/abilene/AbileneTXCodeofOrdinancesEXPORT20260225.xlsx \
  --jurisdiction "Abilene, TX" \
  --source-kind excel \
  --out ./out/abilene_standardized.xlsx
```

## Docker Postgres

`gridics-forge` now includes its own lightweight Docker Compose stack for PostgreSQL + pgvector.
This is the recommended way to run ingestion, normalization, embeddings, and retrieval locally.

Start the database:

```bash
docker compose up -d postgres
```

The default host connection is:

```bash
postgresql+psycopg://postgres:postgres@localhost:5433/gridics_forge
```

That value is already set in `.env`, so the local scripts will use it automatically.

Example Phase 1-6 run:

```bash
python3 scripts/load_municode_export.py \
  "cache/abilene/AbileneTXCodeofOrdinancesEXPORT20260225.xlsx" \
  --jurisdiction "Abilene, TX"

python3 scripts/normalize_municode_rows.py 1

python3 scripts/embed_chunks.py --source-document-id 1 --limit 250
```

Stop the database:

```bash
docker compose down
```
```

To reuse a cache directory instead of a temporary one:

```bash
python3 scripts/run_pipeline.py \
  --source-url "https://library.municode.com/tx/abilene/codes/code_of_ordinances" \
  --jurisdiction "Abilene, TX" \
  --cache-dir ./cache/abilene \
  --out ./out/abilene_standardized.xlsx
```

## Recommended next steps

1. Implement source adapters in `tools/source_tools.py` for Municode, eCode360, PDF, and local HTML caches.
2. Expand the field dictionaries in `models/schemas.py` so every workbook field has a canonical key and unit.
3. Add a real legal cross-reference graph in `tools/legal_tools.py`.
4. Add a review queue UI or database sink for unresolved fields.
5. Add regression tests using 2-3 known jurisdictions.


## Model factory

This starter repo now includes a model factory at `src/zoning_agno/agents/model_factory.py`.
It routes tasks to Groq, Gemini, or OpenRouter models based on task size and task profile.

### Default routing

- small → `groq:llama-3.1-8b-instant`
- medium → `gemini:gemini-2.0-flash`
- large → `openrouter:google/gemini-2.5-pro`

### Environment variables

```bash
SMALL_MODEL_PROVIDER=groq
SMALL_MODEL_ID=llama-3.1-8b-instant
MEDIUM_MODEL_PROVIDER=gemini
MEDIUM_MODEL_ID=gemini-2.0-flash
LARGE_MODEL_PROVIDER=openrouter
LARGE_MODEL_ID=google/gemini-2.5-pro

# optional task-specific overrides
USE_EXTRACTION_PROVIDER=openrouter
USE_EXTRACTION_MODEL_ID=anthropic/claude-3.7-sonnet
QA_REVIEW_PROVIDER=gemini
QA_REVIEW_MODEL_ID=gemini-2.5-pro
```

### Provider credentials

```bash
export GROQ_API_KEY=...
export GOOGLE_API_KEY=...
export OPENROUTER_API_KEY=...
```
