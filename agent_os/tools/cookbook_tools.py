"""Cookbook composition tools for AgentOS agents."""

from __future__ import annotations

from typing import Any

from agent_os.common.feasibility_engine import (
    _deep_find_keys,
    _first_non_empty,
    evaluate_feasibility,
    extract_lot_area_sf,
    extract_use_permission,
    extract_zoning_summary,
)
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


def run_instant_feasibility(
    address: str,
    use: str,
    units: float | None = None,
    height_ft: float | None = None,
    stories: float | None = None,
    gross_sqft: float | None = None,
    state_env: str | None = None,
    zip_code: str | None = None,
    enable_search_alternatives: bool = False,
    search_polygon: str | None = None,
) -> dict:
    """Compose market, zoning, and optional search into instant feasibility output."""
    payload = {
        "address": address,
        "project": {
            "use": use,
            "units": units,
            "height_ft": height_ft,
            "stories": stories,
            "gross_sqft": gross_sqft,
        },
        "state_env": state_env,
        "zip_code": zip_code,
        "enable_search_alternatives": enable_search_alternatives,
        "search_polygon": search_polygon,
    }
    payload["project"] = {k: v for k, v in payload["project"].items() if v is not None}
    payload = {k: v for k, v in payload.items() if v is not None}

    client = _client()
    status, response = evaluate_feasibility(payload, client)
    trace = client.call_log
    if status >= 400:
        if AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS:
            return {
                "error": response,
                "gridics_api_trace": trace,
            }
        return {"error": response}
    if isinstance(response, dict):
        response = dict(response)
        if AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS:
            response["gridics_api_trace"] = trace
    return response


def run_instant_availability(
    address: str,
    use: str,
    units: float | None = None,
    height_ft: float | None = None,
    stories: float | None = None,
    gross_sqft: float | None = None,
    state_env: str | None = None,
    zip_code: str | None = None,
    enable_search_alternatives: bool = False,
    search_polygon: str | None = None,
) -> dict:
    """Alias tool focused on instant availability checks."""
    return run_instant_feasibility(
        address=address,
        use=use,
        units=units,
        height_ft=height_ft,
        stories=stories,
        gross_sqft=gross_sqft,
        state_env=state_env,
        zip_code=zip_code,
        enable_search_alternatives=enable_search_alternatives,
        search_polygon=search_polygon,
    )


def screen_parcels_by_polygon(
    state_env: str,
    search_polygon: str,
    use: str,
    min_lot_size_sf: float | None = None,
    page_start: int = 1,
    pages_to_scan: int = 1,
    max_parcels_to_evaluate: int = 25,
) -> dict:
    """Search polygon GroupIDs, then screen parcels by use permission and minimum lot size."""
    try:
        page_start = int(page_start)
    except (TypeError, ValueError) as e:
        raise ValueError("page_start must be an integer >= 1") from e
    if page_start < 1:
        raise ValueError("page_start must be >= 1")

    try:
        pages_to_scan = int(pages_to_scan)
    except (TypeError, ValueError) as e:
        raise ValueError("pages_to_scan must be an integer >= 1") from e
    if pages_to_scan < 1:
        raise ValueError("pages_to_scan must be >= 1")

    try:
        max_parcels_to_evaluate = int(max_parcels_to_evaluate)
    except (TypeError, ValueError) as e:
        raise ValueError("max_parcels_to_evaluate must be an integer >= 1") from e
    if max_parcels_to_evaluate < 1:
        raise ValueError("max_parcels_to_evaluate must be >= 1")
    if min_lot_size_sf is not None and min_lot_size_sf < 0:
        raise ValueError("min_lot_size_sf must be >= 0")

    client = _client()
    state = state_env.strip().lower()
    polygon = search_polygon.strip()

    all_group_ids: list[str] = []
    total_pages: int | None = None
    total_rows: int | None = None
    pages_scanned = 0

    for page in range(page_start, page_start + pages_to_scan):
        search_result = client.search(search_polygon=polygon, page=page)
        pages_scanned += 1

        if total_pages is None:
            value = _first_non_empty(_deep_find_keys(search_result, {"pages"}))
            if isinstance(value, (int, float)):
                total_pages = int(value)
        if total_rows is None:
            value = _first_non_empty(_deep_find_keys(search_result, {"rows"}))
            if isinstance(value, (int, float)):
                total_rows = int(value)

        data = search_result.get("data") if isinstance(search_result, dict) else None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, (str, int)):
                    all_group_ids.append(str(item))

    unique_group_ids = list(dict.fromkeys(all_group_ids))
    to_evaluate = unique_group_ids[:max_parcels_to_evaluate]

    matches: list[dict[str, Any]] = []
    evaluated = 0
    errors: list[dict[str, str]] = []

    for group_id in to_evaluate:
        evaluated += 1
        try:
            payload = client.get_property_record_by_group_id(state_env=state, group_id=group_id)
        except Exception as e:  # pragma: no cover
            errors.append({"group_id": group_id, "error": str(e)})
            continue

        use_permitted = extract_use_permission(payload, use)
        lot_size_sf = extract_lot_area_sf(payload)
        zone = extract_zoning_summary(payload).get("zone_combination_name")

        lot_ok = (
            True
            if min_lot_size_sf is None
            else lot_size_sf is not None and lot_size_sf >= min_lot_size_sf
        )
        if use_permitted is True and lot_ok:
            matches.append(
                {
                    "group_id": group_id,
                    "state_env": state,
                    "zone": zone,
                    "use_permitted": True,
                    "lot_size_sf": lot_size_sf,
                }
            )

    response: dict[str, Any] = {
        "query": {
            "state_env": state,
            "use": use,
            "min_lot_size_sf": min_lot_size_sf,
            "page_start": page_start,
            "pages_to_scan": pages_to_scan,
            "max_parcels_to_evaluate": max_parcels_to_evaluate,
        },
        "search": {
            "pages_scanned": pages_scanned,
            "total_pages": total_pages,
            "total_rows": total_rows,
            "group_ids_collected": len(unique_group_ids),
        },
        "screening": {
            "evaluated": evaluated,
            "matches": len(matches),
            "errors": len(errors),
            "is_sample_only": True,
            "limitations": [
                "This is a sampled screen, not an exhaustive statewide evaluation.",
                "Increase pages_to_scan and max_parcels_to_evaluate for broader coverage.",
            ],
        },
        "matches": matches,
    }
    if errors:
        response["sample_errors"] = errors[:5]
    if AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS:
        response["gridics_api_trace"] = client.call_log
    return response
