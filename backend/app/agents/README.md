# Zoning Agent Architecture

`backend/app/agents` is centered around AgentOS now:

- `zoning_agent.py` builds the primary Agno team, assistant agent, and orchestrator.
- `agent_os.py` constructs the AgentOS app directly from the zoning builders.

The assistant flow is:

1. AgentOS exposes the registry and run targets.
2. The frontend uses the fixed assistant target ID configured in code.
3. The UI calls the matching `/api/agents/{agent_id}/runs` endpoint.

The actual zoning orchestration now lives in `zoning_agent.py`, and the package surface is intentionally smaller and more direct.
