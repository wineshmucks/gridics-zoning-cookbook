"""Shared feasibility rules engine for cookbook examples."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from agent_os.common.gridics_client import GridicsClient


STATE_MAP = {
    "AL": "al",
    "AK": "ak",
    "AZ": "az",
    "AR": "ar",
    "CA": "ca",
    "CO": "co",
    "CT": "ct",
    "DE": "de",
    "FL": "fl",
    "GA": "ga",
    "HI": "hi",
    "ID": "id",
    "IL": "il",
    "IN": "in",
    "IA": "ia",
    "KS": "ks",
    "KY": "ky",
    "LA": "la",
    "ME": "me",
    "MD": "md",
    "MA": "ma",
    "MI": "mi",
    "MN": "mn",
    "MS": "ms",
    "MO": "mo",
    "MT": "mt",
    "NE": "ne",
    "NV": "nv",
    "NH": "nh",
    "NJ": "nj",
    "NM": "nm",
    "NY": "ny",
    "NC": "nc",
    "ND": "nd",
    "OH": "oh",
    "OK": "ok",
    "OR": "or",
    "PA": "pa",
    "RI": "ri",
    "SC": "sc",
    "SD": "sd",
    "TN": "tn",
    "TX": "tx",
    "UT": "ut",
    "VT": "vt",
    "VA": "va",
    "WA": "wa",
    "WV": "wv",
    "WI": "wi",
    "WY": "wy",
    "DC": "dc",
}


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _normalize_use(use: str) -> str:
    return re.sub(r"[^a-z0-9]", "", use.lower())


def _deep_find_keys(obj: Any, target_keys: set[str]) -> List[Any]:
    matches: List[Any] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _normalize_key(k) in target_keys:
                matches.append(v)
            matches.extend(_deep_find_keys(v, target_keys))
    elif isinstance(obj, list):
        for item in obj:
            matches.extend(_deep_find_keys(item, target_keys))
    return matches


def _first_non_empty(values: List[Any]) -> Optional[Any]:
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if match:
            return float(match.group(0))
    return None


def _flatten_messages(value: Any) -> List[str]:
    out: List[str] = []
    if isinstance(value, str):
        if value.strip():
            out.append(value.strip())
    elif isinstance(value, list):
        for v in value:
            out.extend(_flatten_messages(v))
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten_messages(v))
    return out


def clean_address(address: str) -> str:
    text = re.sub(
        r"\b(?:apt|apartment|unit|suite|ste|#)\s*[\w-]+\b",
        "",
        address,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def infer_state_env(address: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{2})\b(?:\s+\d{5}(?:-\d{4})?)?$", address.upper())
    if not m:
        return None
    return STATE_MAP.get(m.group(1))


def infer_zip(address: str) -> Optional[str]:
    m = re.search(r"\b(\d{5})(?:-\d{4})?\b", address)
    return m.group(1) if m else None


def market_supported(markets_payload: Dict[str, Any], state_env: str) -> Optional[bool]:
    target = state_env.lower()
    if not isinstance(markets_payload, dict):
        return None

    flat_strings: List[str] = []
    for value in _deep_find_keys(markets_payload, {"data", "markets", "stateenv", "state", "states"}):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    flat_strings.append(item.lower())
                elif isinstance(item, dict):
                    code = _first_non_empty(
                        _deep_find_keys(item, {"stateenv", "state", "abbr", "code", "market"})
                    )
                    if isinstance(code, str) and code.lower() == target:
                        active = _first_non_empty(
                            _deep_find_keys(item, {"active", "available", "isactive", "enabled"})
                        )
                        if isinstance(active, bool):
                            return active
                        return True

    if target in flat_strings:
        return True
    return None


def extract_zoning_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    zone = _first_non_empty(
        _deep_find_keys(payload, {"zonecombinationname", "zone", "zonename", "subzone"})
    )
    typology = _first_non_empty(_deep_find_keys(payload, {"typology", "buildingtypology", "type"}))
    calc_status = _first_non_empty(
        _deep_find_keys(payload, {"calculationstatus", "calculationstatusmessage", "status"})
    )

    notes_values = _deep_find_keys(payload, {"notifications", "messages", "warnings", "notes"})
    notes: List[str] = []
    for v in notes_values:
        notes.extend(_flatten_messages(v))

    max_far = _safe_float(
        _first_non_empty(_deep_find_keys(payload, {"maxfar", "farmax", "allowablefar", "far"}))
    )
    max_units = _safe_float(
        _first_non_empty(_deep_find_keys(payload, {"maxunits", "dwellingunitsmax", "maximumunits"}))
    )
    max_height = _safe_float(
        _first_non_empty(_deep_find_keys(payload, {"maxheight", "maximumheight", "maxheightft"}))
    )
    front_setback = _safe_float(
        _first_non_empty(_deep_find_keys(payload, {"frontsetback", "frontsetbackft", "setbackfront"}))
    )
    side_setback = _safe_float(
        _first_non_empty(_deep_find_keys(payload, {"sidesetback", "sidesetbackft", "setbackside"}))
    )
    rear_setback = _safe_float(
        _first_non_empty(_deep_find_keys(payload, {"rearsetback", "rearsetbackft", "setbackrear"}))
    )

    return {
        "zone_combination_name": zone,
        "typology": typology,
        "calculation_status": calc_status,
        "notes": notes,
        "constraints": {
            "max_far": max_far,
            "max_units": max_units,
            "max_height_ft": max_height,
            "front_setback_ft": front_setback,
            "side_setback_ft": side_setback,
            "rear_setback_ft": rear_setback,
        },
    }


def extract_use_permission(payload: Dict[str, Any], requested_use: Optional[str]) -> Optional[bool]:
    if not requested_use:
        return None
    desired = _normalize_use(requested_use)

    candidates: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            normalized_keys = {_normalize_key(k) for k in node.keys()}
            if normalized_keys & {
                "allowed",
                "ispermitted",
                "permitted",
                "byright",
                "isallowed",
                "usename",
                "use",
            }:
                candidates.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)

    for item in candidates:
        name = _first_non_empty(
            _deep_find_keys(item, {"usename", "use", "name", "category", "typology"})
        )
        if not isinstance(name, str):
            continue
        observed = _normalize_use(name)
        if desired not in observed and observed not in desired:
            continue

        raw_permission = _first_non_empty(
            _deep_find_keys(item, {"allowed", "ispermitted", "permitted", "byright", "isallowed"})
        )
        if isinstance(raw_permission, bool):
            return raw_permission
        if isinstance(raw_permission, str):
            text = raw_permission.strip().lower()
            if text in {"yes", "y", "true", "allowed", "permitted", "by-right", "byright"}:
                return True
            if text in {"no", "n", "false", "prohibited", "not allowed", "conditional"}:
                return False
    return None


def extract_lot_area_sf(payload: Dict[str, Any]) -> Optional[float]:
    lot_area = _first_non_empty(
        _deep_find_keys(
            payload,
            {
                "lotarea",
                "lotareasf",
                "lotsizesf",
                "lotsize",
                "lotsquarefeet",
                "lotsqft",
                "parcelarea",
                "parcelareasf",
            },
        )
    )
    return _safe_float(lot_area)


def evaluate_rules(
    project: Dict[str, Any], zoning_summary: Dict[str, Any], use_permission: Optional[bool]
) -> Tuple[str, float, List[str], List[str]]:
    reasons: List[str] = []
    next_steps: List[str] = []
    constraints = zoning_summary["constraints"]

    requested_units = _safe_float(project.get("units"))
    requested_height = _safe_float(project.get("height_ft"))

    hard_fail = False
    needs_review = False

    if use_permission is True:
        reasons.append("Requested use appears permitted in returned zoning use stats.")
    elif use_permission is False:
        reasons.append("Requested use appears disallowed or conditional in returned zoning use stats.")
        hard_fail = True
    else:
        reasons.append("Use permission could not be determined from returned use fields.")
        needs_review = True

    max_units = constraints.get("max_units")
    if requested_units is not None and max_units is not None:
        if requested_units > max_units:
            reasons.append(f"Requested units ({requested_units:g}) exceed observed max units ({max_units:g}).")
            hard_fail = True
        else:
            reasons.append(f"Requested units ({requested_units:g}) are within observed max units ({max_units:g}).")

    max_height = constraints.get("max_height_ft")
    if requested_height is not None and max_height is not None:
        if requested_height > max_height:
            reasons.append(
                f"Requested height ({requested_height:g} ft) exceeds observed max height ({max_height:g} ft)."
            )
            hard_fail = True
        else:
            reasons.append(
                f"Requested height ({requested_height:g} ft) is within observed max height ({max_height:g} ft)."
            )

    calc_status = str(zoning_summary.get("calculation_status") or "").lower()
    if any(flag in calc_status for flag in ["error", "fail", "invalid"]):
        needs_review = True
        reasons.append("Calculation status indicates errors or incomplete computation.")
    elif "ok" in calc_status:
        reasons.append("Calculation status indicates a successful zoning computation.")
    elif calc_status:
        needs_review = True
        reasons.append(f"Calculation status is '{zoning_summary.get('calculation_status')}', review recommended.")

    notes = zoning_summary.get("notes") or []
    if notes:
        needs_review = True
        reasons.append("API returned notifications/messages that should be reviewed.")

    if hard_fail:
        result = "likely_no"
        confidence = 0.3
        next_steps.append("Evaluate variance/conditional-use pathway with local jurisdiction.")
    elif needs_review:
        result = "needs_review"
        confidence = 0.58
        next_steps.append("Perform planner review of overlays, parking, and local amendments.")
    else:
        result = "likely_yes"
        confidence = 0.84

    if not notes:
        next_steps.append("Confirm parking and overlay-specific requirements before permit submission.")

    return result, confidence, reasons, next_steps


def evaluate_feasibility(payload: Dict[str, Any], client: GridicsClient) -> Tuple[int, Dict[str, Any]]:
    address = str(payload.get("address") or "").strip()
    if not address:
        return 400, {"error": "address is required"}

    state_env = str(payload.get("state_env") or "").strip().lower() or infer_state_env(address)
    zip_code = str(payload.get("zip_code") or "").strip() or infer_zip(address)

    if not state_env:
        return 400, {"error": "state_env is required (or inferable from address state abbreviation)"}
    if not zip_code:
        return 400, {"error": "zip_code is required (or inferable from address)"}

    project = payload.get("project") or {}
    cleaned_address = clean_address(address)

    market_status = "unknown"
    try:
        markets = client.get_markets()
        support = market_supported(markets, state_env)
        if support is False:
            return 200, {
                "result": "coverage_unavailable",
                "confidence": 0.99,
                "reasons": [f"Market '{state_env}' is not available per market availability response."],
                "key_constraints": {},
                "source": {"gridics": {"market_availability": markets}},
                "next_steps": ["Choose a supported market or retry when coverage expands."],
            }
        market_status = "supported" if support is True else "unknown"
    except Exception:
        market_status = "check_failed"

    try:
        zoning_payload = client.get_property_record(
            state_env=state_env,
            address=cleaned_address,
            zip_code=zip_code,
        )
    except Exception as e:
        return 502, {"error": f"property-record call failed: {e}"}

    zoning_summary = extract_zoning_summary(zoning_payload)
    use_permission = extract_use_permission(zoning_payload, project.get("use"))

    result, confidence, reasons, next_steps = evaluate_rules(project, zoning_summary, use_permission)

    alternatives: Optional[Dict[str, Any]] = None
    if result != "likely_yes" and payload.get("enable_search_alternatives"):
        polygon = payload.get("search_polygon")
        if isinstance(polygon, str) and polygon.strip():
            try:
                search_result = client.search(search_polygon=polygon.strip(), page=1)
                group_ids = []
                for v in _deep_find_keys(search_result, {"data"}):
                    if isinstance(v, list):
                        group_ids.extend([str(x) for x in v if isinstance(x, (str, int))])
                alternatives = {
                    "candidate_group_ids": group_ids[:10],
                    "raw_rows": _first_non_empty(_deep_find_keys(search_result, {"rows", "datarows"})),
                }
            except Exception as e:
                alternatives = {"error": str(e)}

    response: Dict[str, Any] = {
        "result": result,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "key_constraints": zoning_summary["constraints"],
        "source": {
            "gridics": {
                "zoneCombinationName": zoning_summary.get("zone_combination_name"),
                "typology": zoning_summary.get("typology"),
                "calculationStatus": zoning_summary.get("calculation_status"),
                "notifications": zoning_summary.get("notes"),
                "marketCheck": market_status,
            }
        },
        "next_steps": next_steps,
    }

    if alternatives is not None:
        response["alternatives"] = alternatives

    return 200, response
