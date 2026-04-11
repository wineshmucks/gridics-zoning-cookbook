# AgentOS + Notebook Testing

## Architecture

- `agent-os` is the single runtime for tools and agents.
- AgentOS serves both agent runtime endpoints and direct API routes.
- Notebooks call AgentOS over HTTP for testing.

## AgentOS Files

- App entrypoint: `agent-os/agent_os/app.py`
- Agent registry: `agent-os/agent_os/agents/registry.py`
- Gridics tools: `agent-os/agent_os/tools/gridics_tools.py`
- Cookbook tools: `agent-os/agent_os/tools/cookbook_tools.py`

## Route Map

- `GET /health`
- `GET /routes`
- `GET /api/gridics/markets`
- `GET /api/gridics/property-record`
- `GET /api/gridics/search`
- `POST /api/instant-feasibility`
- AgentOS runtime endpoints from `AgentOS.get_app()`

## Agent IDs

- `market-agent`
- `zoning-agent`
- `search-agent`
- `instant-feasibility-agent`
- `instant-availability-agent`

## Notebook Tests

- `notebooks/00-health-check.ipynb`
- `notebooks/01-gridics-tools.ipynb`
- `notebooks/02-instant-feasibility-route.ipynb`
- `notebooks/03-agentos-config.ipynb`
