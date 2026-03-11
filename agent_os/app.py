"""AgentOS app entrypoint."""

from __future__ import annotations

from agno.os import AgentOS
from fastapi.middleware.cors import CORSMiddleware

from agent_os.agents.registry import ALL_AGENTS
from agent_os.config import AGENT_OS_HOST, AGENT_OS_PORT
from agent_os.routes import feasibility_router, gridics_router

agent_os = AgentOS(
    id="gridics-cookbook-os",
    description="AgentOS runtime for Gridics zoning cookbook",
    agents=ALL_AGENTS,
)

app = agent_os.get_app()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(gridics_router)
app.include_router(feasibility_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/routes")
def routes() -> dict:
    return {
        "gridics": [
            "GET /api/gridics/markets",
            "GET /api/gridics/property-record",
            "GET /api/gridics/search",
        ],
        "feasibility": ["POST /api/instant-feasibility"],
        "agentos": ["GET /config", "agent run/session endpoints"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_os.app:app", host=AGENT_OS_HOST, port=AGENT_OS_PORT, reload=True)
