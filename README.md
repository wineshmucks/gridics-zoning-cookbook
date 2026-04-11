# Gridics Zoning Cookbook

This repository is organized around a single `agent_os` runtime, a Next.js `agent_ui`, and notebooks that test the API.

## Getting Started

1. Create/sign in to Gridics developer portal: https://developer.gridics.com/get-started
2. Get your credentials from Gridics Apps.
3. Create `agent_os/.env` (recommended) from `agent_os/.env.example` and set credentials:

```bash
GRIDICS_CONSUMER_KEY=your_consumer_key
CEREBRAS_API_KEY=your_cerebras_api_key
AGENT_OS_MODEL_PROVIDER=cerebras
AGENT_OS_MODEL_ID=llama-4-scout-17b-16e-instruct
# Gemini option:
# GOOGLE_API_KEY=your_google_api_key
# AGENT_OS_MODEL_PROVIDER=gemini
# AGENT_OS_MODEL_ID=gemini-2.0-flash
# Groq option:
# GROQ_API_KEY=your_groq_api_key
# AGENT_OS_MODEL_PROVIDER=groq
# AGENT_OS_MODEL_ID=llama-3.3-70b-versatile
# Optional compact format:
# AGENT_OS_MODEL=cerebras:llama-4-scout-17b-16e-instruct
GRIDICS_BASE_URL=https://api.gridics.com/v1
GRIDICS_TIMEOUT_SECONDS=20
AGENT_OS_MODEL_TEMPERATURE=0
AGENT_OS_HOST=0.0.0.0
AGENT_OS_PORT=7777
```

4. Install backend dependencies:

```bash
pip install -r requirements.txt
```

5. Run AgentOS (from repo root):

```bash
python -m agent_os.app
```

Alternative command:

```bash
uvicorn agent_os.app:app --host 0.0.0.0 --port 7777 --reload
```

6. Verify backend:

```bash
curl -sS "http://localhost:7777/health"
curl -sS "http://localhost:7777/routes"
```

7. Run Agent UI (new terminal):

```bash
cd agent_ui
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

## AgentOS

- Runtime app: `agent_os/app.py`
- Tools: `agent_os/tools/`
- Agents: `agent_os/agents/registry.py`
- Direct routes (for smoke testing):
- `GET /api/gridics/markets`
- `GET /api/gridics/property-record`
- `GET /api/gridics/search`
- `POST /api/instant-feasibility`

### Markets Data Cache

Market availability data is now cached in `agent_os/data/markets.json` and served locally by `get_markets()`.

Refresh the cache when needed:

```bash
python agent_os/scripts/refresh_markets_data.py
```

## Notebooks

- `notebooks/00-health-check.ipynb`
- `notebooks/01-gridics-tools.ipynb`
- `notebooks/02-instant-feasibility-route.ipynb`
- `notebooks/03-agentos-config.ipynb`

## Repository Structure

- `agent_os/`: AgentOS runtime, tools, and agents
- `agent_ui/`: Next.js UI for interacting with AgentOS
- `notebooks/`: notebook-based tests against AgentOS
- `agent_os/common/`: shared Python logic
- `api/specs/`: source-of-truth OpenAPI YAML specs
- `cookbook/`: numbered use-case definitions (1 to 24)
- `docs/`: supporting docs
