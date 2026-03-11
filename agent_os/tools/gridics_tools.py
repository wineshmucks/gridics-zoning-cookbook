"""Gridics tool functions for AgentOS agents."""

from __future__ import annotations

import json
from pathlib import Path

from agent_os.common.gridics_client import GridicsClient

from agent_os.config import (
    AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS,
    GRIDICS_BASE_URL,
    GRIDICS_TIMEOUT_SECONDS,
    get_gridics_api_key,
)


def _client() -> GridicsClient:
    return GridicsClient(
        api_key=get_gridics_api_key(),
        base_url=GRIDICS_BASE_URL,
        timeout_seconds=GRIDICS_TIMEOUT_SECONDS,
    )


_MARKETS_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "markets.json"


def _load_markets_data() -> dict:
    if not _MARKETS_DATA_PATH.exists():
        raise RuntimeError(
            f"Missing markets data file at {_MARKETS_DATA_PATH}. "
            "Refresh it with: python agent_os/scripts/refresh_markets_data.py"
        )
    try:
        return json.loads(_MARKETS_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Invalid JSON in markets data file {_MARKETS_DATA_PATH}: {e}"
        ) from e


def get_markets() -> dict:
    """Fetch supported Gridics markets."""
    result = _load_markets_data()
    if AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS and isinstance(result, dict):
        result = dict(result)
        trace = [
            {
                "request": {
                    "method": "GET",
                    "path": "/markets",
                    "url": str(_MARKETS_DATA_PATH),
                    "params": {},
                    "headers": {},
                },
                "response": {
                    "status_code": 200,
                    "body": "Loaded from local static markets file.",
                },
            }
        ]
        result["gridics_api_trace"] = trace
    return result


def get_property_record(state_env: str, address: str, zip_code: str) -> dict:
    """Fetch zoning record by state_env/address/zip_code."""
    client = _client()
    result = client.get_property_record(state_env=state_env, address=address, zip_code=zip_code)
    if AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS and isinstance(result, dict):
        result = dict(result)
        result["gridics_api_trace"] = client.call_log
    return result


def search_parcels(search_polygon: str, page: int = 1) -> dict:
    """Search parcels by GeoJSON polygon and page."""
    client = _client()
    result = client.search(search_polygon=search_polygon, page=page)
    if AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS and isinstance(result, dict):
        result = dict(result)
        result["gridics_api_trace"] = client.call_log
    return result
