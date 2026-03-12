"""Agno tools backed by UZone services."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


_STATE_MAP = {
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
_GRIDICS_BASE_URL = os.getenv("GRIDICS_BASE_URL", "https://api.gridics.com/v1")
_GRIDICS_TIMEOUT_SECONDS = int(os.getenv("GRIDICS_TIMEOUT_SECONDS", "20"))
_STREET_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|way|"
    r"place|pl|terrace|ter|circle|cir|parkway|pkwy|highway|hwy"
    r")\.?\b",
    flags=re.IGNORECASE,
)
_ADDRESS_START_PATTERN = re.compile(r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9.\-']*(?:\s+[A-Za-z0-9.\-']+){0,10}")
_ADDRESS_STOP_PATTERN = re.compile(
    r"\b("
    r"zoned?|allow(?:ed|s)?|permit(?:ted|s)?|can|could|would|what|how|is|are|do(?:es)?|"
    r"setback|height|lot|adu|duplex|triplex|fourplex|residential|commercial|industrial"
    r")\b",
    flags=re.IGNORECASE,
)
_ACTIVE_PROPERTY_SESSION_KEY = "active_property_context"
_FOLLOW_UP_PROPERTY_PATTERN = re.compile(
    r"\b("
    r"here|there|this (?:property|parcel|lot|site|address)|that (?:property|parcel|lot|site|address)|"
    r"it|this one|that one|on this (?:property|site|lot|parcel)|for this (?:property|site|lot|parcel)"
    r")\b",
    flags=re.IGNORECASE,
)


@dataclass
class _GridicsClient:
    api_key: str
    base_url: str = _GRIDICS_BASE_URL
    timeout_seconds: int = _GRIDICS_TIMEOUT_SECONDS
    call_log: list[dict[str, Any]] = field(default_factory=list)

    def _build_url(self, path: str, params: dict[str, Any]) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        return url

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = self._build_url(path, params)
        trace_entry: dict[str, Any] = {
            "request": {
                "method": "GET",
                "path": path,
                "url": url,
                "params": {k: v for k, v in params.items() if v is not None},
                "headers": {
                    "x-api-key": "***redacted***",
                    "accept": "application/json",
                },
            }
        }

        req = urllib.request.Request(url, method="GET")
        req.add_header("x-api-key", self.api_key)
        req.add_header("accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                trace_entry["response"] = {
                    "status_code": getattr(resp, "status", 200),
                    "body": body,
                    "json": parsed,
                }
                self.call_log.append(trace_entry)
                return parsed
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            trace_entry["response"] = {"status_code": exc.code, "body": payload}
            self.call_log.append(trace_entry)
            raise RuntimeError(f"Gridics HTTP {exc.code}: {payload}") from exc
        except urllib.error.URLError as exc:
            trace_entry["error"] = f"Gridics connection error: {exc.reason}"
            self.call_log.append(trace_entry)
            raise RuntimeError(f"Gridics connection error: {exc.reason}") from exc

    def get_property_record(self, *, state_env: str, address: str, zip_code: str) -> dict[str, Any]:
        return self._get(
            "/property-record",
            {"state_env": state_env, "address": address, "zipCode": zip_code},
        )


def _get_gridics_api_key() -> str:
    key = os.getenv("GRIDICS_API_KEY", "").strip() or os.getenv("GRIDICS_CONSUMER_KEY", "").strip()
    if not key:
        raise ValueError("Set GRIDICS_API_KEY (or GRIDICS_CONSUMER_KEY)")
    return key


def _request_classification_payload(question_type: str, routing_reason: str) -> dict[str, str]:
    return {
        "type": question_type,
        "label": "specific address" if question_type == "specific_address" else "general zoning",
        "reason": routing_reason,
    }


def _address_resolution_payload(
    *,
    detected_address: str | None,
    standardized_address: str | None,
    state_env: str | None,
    zip_code: str | None,
    address_source: str | None,
) -> dict[str, Any]:
    return {
        "input_address": detected_address,
        "standardized_address": standardized_address,
        "resolved_state_env": state_env,
        "resolved_zip_code": zip_code,
        "address_source": address_source,
        "lookup_ready": bool(standardized_address and state_env and zip_code),
    }


def _follow_up_context_payload(
    *,
    question_type: str,
    standardized_address: str | None = None,
    state_env: str | None = None,
    zip_code: str | None = None,
    zoning_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if question_type != "specific_address":
        return {
            "context_type": "general_zoning",
            "active_location": None,
            "reuse_for_follow_ups": False,
            "guidance": "Do not assume a property context for follow-up questions unless the user provides a specific address.",
        }

    constraints = zoning_summary.get("constraints") if isinstance(zoning_summary, dict) else None
    return {
        "context_type": "specific_address",
        "active_location": {
            "standardized_address": standardized_address,
            "state_env": state_env,
            "zip_code": zip_code,
            "zone_combination_name": zoning_summary.get("zone_combination_name") if zoning_summary else None,
            "typology": zoning_summary.get("typology") if zoning_summary else None,
            "constraints": constraints,
        },
        "reuse_for_follow_ups": True,
        "guidance": (
            "Use this property as the default context for follow-up zoning questions until the user supplies a different address."
        ),
    }


def _resolve_client_id(client_id: str | None, run_context: Any = None) -> str:
    resolved_client_id = client_id.strip() if isinstance(client_id, str) and client_id.strip() else None
    if resolved_client_id and resolved_client_id.lower() in {"default", "null", "none", "unknown"}:
        resolved_client_id = None

    dependencies = getattr(run_context, "dependencies", None)
    if not resolved_client_id and isinstance(dependencies, dict):
        dependency_client_id = dependencies.get("client_id")
        if isinstance(dependency_client_id, str) and dependency_client_id.strip():
            resolved_client_id = dependency_client_id.strip()

    if not resolved_client_id:
        raise ValueError("client_id is required to query customer zoning knowledge.")

    return resolved_client_id


def _extract_address_from_query(query: str) -> str | None:
    match = _ADDRESS_START_PATTERN.search(query)
    if not match:
        return None

    candidate = query[match.start() :]
    candidate = re.split(r"[?!\n]", candidate, maxsplit=1)[0].strip(" ,.;:")
    candidate = _ADDRESS_STOP_PATTERN.split(candidate, maxsplit=1)[0].strip(" ,.;:")

    if not candidate or not _STREET_SUFFIX_PATTERN.search(candidate):
        return None

    return candidate


def _classify_question(query: str, address: str | None = None) -> str:
    if address:
        return "specific_address"
    if _extract_address_from_query(query):
        return "specific_address"
    return "general_zoning"


def _get_session_state(run_context: Any) -> dict[str, Any]:
    session_state = getattr(run_context, "session_state", None)
    return session_state if isinstance(session_state, dict) else {}


def _get_active_property_context(run_context: Any) -> dict[str, Any] | None:
    session_state = _get_session_state(run_context)
    active_context = session_state.get(_ACTIVE_PROPERTY_SESSION_KEY)
    return active_context if isinstance(active_context, dict) else None


def _set_active_property_context(
    run_context: Any,
    *,
    standardized_address: str,
    state_env: str,
    zip_code: str,
    zoning_summary: dict[str, Any],
) -> None:
    session_state = getattr(run_context, "session_state", None)
    if not isinstance(session_state, dict):
        return

    session_state[_ACTIVE_PROPERTY_SESSION_KEY] = {
        "standardized_address": standardized_address,
        "state_env": state_env,
        "zip_code": zip_code,
        "zone_combination_name": zoning_summary.get("zone_combination_name"),
        "typology": zoning_summary.get("typology"),
        "constraints": zoning_summary.get("constraints"),
    }


def _should_reuse_active_property(query: str, active_context: dict[str, Any] | None) -> bool:
    if not active_context:
        return False

    normalized_query = query.strip().lower()
    if not normalized_query:
        return False

    if _FOLLOW_UP_PROPERTY_PATTERN.search(normalized_query):
        return True

    if any(
        phrase in normalized_query
        for phrase in (
            "what can be built",
            "what is allowed",
            "what's allowed",
            "what are the setbacks",
            "what uses are allowed",
            "can i build",
            "can you build",
            "how tall",
            "how many units",
            "is it zoned",
        )
    ):
        return True

    return False


def _build_gridics_client():
    return _GridicsClient(
        api_key=_get_gridics_api_key(),
        base_url=_GRIDICS_BASE_URL,
        timeout_seconds=_GRIDICS_TIMEOUT_SECONDS,
    )


def _standardize_address(address: str) -> str:
    standardized = re.sub(
        r"\b(?:apt|apartment|unit|suite|ste|#)\s*[\w-]+\b",
        "",
        address,
        flags=re.IGNORECASE,
    )
    standardized = re.sub(r"\s*,\s*", ", ", standardized)
    standardized = re.sub(r"\s+", " ", standardized).strip(" ,")
    return standardized


def _infer_state_env(address: str) -> str | None:
    match = re.search(r"\b([A-Z]{2})\b(?:\s+\d{5}(?:-\d{4})?)?$", address.upper())
    if not match:
        return None
    return _STATE_MAP.get(match.group(1))


def _infer_zip(address: str) -> str | None:
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", address)
    return match.group(1) if match else None


def _extract_gridics_zoning_summary(payload: dict[str, Any]) -> dict[str, Any]:
    def normalize_key(key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    def deep_find_keys(obj: Any, target_keys: set[str]) -> list[Any]:
        matches: list[Any] = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                if normalize_key(key) in target_keys:
                    matches.append(value)
                matches.extend(deep_find_keys(value, target_keys))
        elif isinstance(obj, list):
            for item in obj:
                matches.extend(deep_find_keys(item, target_keys))
        return matches

    def first_non_empty(values: list[Any]) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None

    def safe_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                return float(match.group(0))
        return None

    def flatten_messages(value: Any) -> list[str]:
        out: list[str] = []
        if isinstance(value, str):
            if value.strip():
                out.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                out.extend(flatten_messages(item))
        elif isinstance(value, dict):
            for item in value.values():
                out.extend(flatten_messages(item))
        return out

    zone = first_non_empty(deep_find_keys(payload, {"zonecombinationname", "zone", "zonename", "subzone"}))
    typology = first_non_empty(deep_find_keys(payload, {"typology", "buildingtypology", "type"}))
    calc_status = first_non_empty(
        deep_find_keys(payload, {"calculationstatus", "calculationstatusmessage", "status"})
    )

    notes_values = deep_find_keys(payload, {"notifications", "messages", "warnings", "notes"})
    notes: list[str] = []
    for value in notes_values:
        notes.extend(flatten_messages(value))

    max_far = safe_float(first_non_empty(deep_find_keys(payload, {"maxfar", "farmax", "allowablefar", "far"})))
    max_units = safe_float(
        first_non_empty(deep_find_keys(payload, {"maxunits", "dwellingunitsmax", "maximumunits"}))
    )
    max_height = safe_float(
        first_non_empty(deep_find_keys(payload, {"maxheight", "maximumheight", "maxheightft"}))
    )
    front_setback = safe_float(
        first_non_empty(deep_find_keys(payload, {"frontsetback", "frontsetbackft", "setbackfront"}))
    )
    side_setback = safe_float(
        first_non_empty(deep_find_keys(payload, {"sidesetback", "sidesetbackft", "setbackside"}))
    )
    rear_setback = safe_float(
        first_non_empty(deep_find_keys(payload, {"rearsetback", "rearsetbackft", "setbackrear"}))
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


def _build_augmented_knowledge_query(
    *,
    query: str,
    standardized_address: str,
    zoning_summary: dict[str, Any],
) -> str:
    zone_name = zoning_summary.get("zone_combination_name") or "unknown zone"
    typology = zoning_summary.get("typology") or "unknown typology"
    constraints = zoning_summary.get("constraints") or {}
    constraint_bits = [
        f"max FAR={constraints.get('max_far')}" if constraints.get("max_far") is not None else None,
        f"max units={constraints.get('max_units')}" if constraints.get("max_units") is not None else None,
        f"max height ft={constraints.get('max_height_ft')}" if constraints.get("max_height_ft") is not None else None,
    ]
    rendered_constraints = ", ".join(bit for bit in constraint_bits if bit)

    parts = [
        query.strip(),
        f"Address: {standardized_address}",
        f"Gridics zone: {zone_name}",
        f"Gridics typology: {typology}",
    ]
    if rendered_constraints:
        parts.append(f"Observed constraints: {rendered_constraints}")
    return "\n".join(parts)


def _needs_constraints_lookup(zoning_summary: dict[str, Any]) -> bool:
    constraints = zoning_summary.get("constraints") or {}
    keys = (
        "max_far",
        "max_units",
        "max_height_ft",
        "front_setback_ft",
        "side_setback_ft",
        "rear_setback_ft",
    )
    return any(constraints.get(key) is None for key in keys)


def _build_constraints_knowledge_query(
    *,
    query: str,
    standardized_address: str,
    zoning_summary: dict[str, Any],
) -> str:
    zone_name = zoning_summary.get("zone_combination_name") or "unknown zone"
    typology = zoning_summary.get("typology") or "unknown typology"
    return "\n".join(
        [
            query.strip(),
            f"Address: {standardized_address}",
            f"Gridics zone: {zone_name}",
            f"Gridics typology: {typology}",
            (
                "Find numeric development standards and dimensional controls for this property and zoning district, "
                "especially maximum building height, FAR, dwelling units, lot coverage, open space, "
                "front setback, side setback, rear setback, parking, and any section references."
            ),
        ]
    )


def query_customer_zoning_code(
    query: str,
    limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
) -> dict:
    """Query zoning knowledge for one specific tenant by client_id."""
    resolved_client_id = _resolve_client_id(client_id, run_context)

    from sqlalchemy import select

    from app.db.models import TenantClient
    from app.db.session import SessionLocal
    from app.services.zoning_knowledge_service import query_customer_zoning_knowledge

    with SessionLocal() as db:
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == resolved_client_id))
        if tenant_client is None:
            raise ValueError(f"Unknown tenant client_id '{resolved_client_id}'")
        return query_customer_zoning_knowledge(db, tenant_client, query=query, limit=limit)


def analyze_customer_zoning_request(
    query: str,
    address: str | None = None,
    state_env: str | None = None,
    zip_code: str | None = None,
    knowledge_limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
) -> dict:
    """Route a zoning question to either general knowledge or an address-aware Gridics workflow."""
    question = query.strip()
    if not question:
        raise ValueError("Query text is required.")

    resolved_client_id = _resolve_client_id(client_id, run_context)
    provided_address = address.strip() if isinstance(address, str) and address.strip() else None
    extracted_address = None if provided_address else _extract_address_from_query(question)
    active_property_context = _get_active_property_context(run_context)
    reused_active_property = False
    resolved_address = provided_address or extracted_address
    if not resolved_address and _should_reuse_active_property(question, active_property_context):
        resolved_address = str(active_property_context.get("standardized_address") or "").strip() or None
        reused_active_property = bool(resolved_address)
    question_type = _classify_question(question, resolved_address)

    if question_type == "general_zoning":
        routing_reason = "No property address was detected, so the request was handled as a general zoning question."
        return {
            "question_type": question_type,
            "routing_reason": routing_reason,
            "request_classification": _request_classification_payload(question_type, routing_reason),
            "follow_up_context": _follow_up_context_payload(question_type=question_type),
            "knowledge": query_customer_zoning_code(
                query=question,
                limit=knowledge_limit,
                client_id=resolved_client_id,
            ),
        }

    standardized_address = _standardize_address(resolved_address or "")
    resolved_state_env = (
        state_env.strip().lower()
        if isinstance(state_env, str) and state_env.strip()
        else (
            str(active_property_context.get("state_env")).strip().lower()
            if reused_active_property and active_property_context and active_property_context.get("state_env")
            else _infer_state_env(standardized_address)
        )
    )
    resolved_zip_code = (
        zip_code.strip()
        if isinstance(zip_code, str) and zip_code.strip()
        else (
            str(active_property_context.get("zip_code")).strip()
            if reused_active_property and active_property_context and active_property_context.get("zip_code")
            else _infer_zip(standardized_address)
        )
    )

    address_context = {
        "address_source": "argument" if provided_address else ("session" if reused_active_property else "query"),
        "detected_address": resolved_address,
        "standardized_address": standardized_address,
        "state_env": resolved_state_env,
        "zip_code": resolved_zip_code,
    }

    if not resolved_state_env or not resolved_zip_code:
        routing_reason = "A property address was detected, but it was missing enough location detail for a Gridics lookup."
        return {
            "question_type": question_type,
            "routing_reason": routing_reason,
            "request_classification": _request_classification_payload(question_type, routing_reason),
            "address_context": address_context,
            "address_resolution": _address_resolution_payload(
                detected_address=resolved_address,
                standardized_address=standardized_address,
                state_env=resolved_state_env,
                zip_code=resolved_zip_code,
                address_source=address_context["address_source"],
            ),
            "follow_up_context": _follow_up_context_payload(
                question_type=question_type,
                standardized_address=standardized_address,
                state_env=resolved_state_env,
                zip_code=resolved_zip_code,
                zoning_summary=None,
            ),
            "needs_address_clarification": True,
            "clarification_prompt": "Please provide the full property address, including state and ZIP code.",
        }

    client = _build_gridics_client()
    property_record = client.get_property_record(
        state_env=resolved_state_env,
        address=standardized_address,
        zip_code=resolved_zip_code,
    )
    zoning_summary = _extract_gridics_zoning_summary(property_record)
    knowledge_query = _build_augmented_knowledge_query(
        query=question,
        standardized_address=standardized_address,
        zoning_summary=zoning_summary,
    )
    primary_knowledge = query_customer_zoning_code(
        query=knowledge_query,
        limit=knowledge_limit,
        client_id=resolved_client_id,
    )
    constraints_knowledge = (
        query_customer_zoning_code(
            query=_build_constraints_knowledge_query(
                query=question,
                standardized_address=standardized_address,
                zoning_summary=zoning_summary,
            ),
            limit=knowledge_limit,
            client_id=resolved_client_id,
        )
        if _needs_constraints_lookup(zoning_summary)
        else None
    )

    _set_active_property_context(
        run_context,
        standardized_address=standardized_address,
        state_env=resolved_state_env,
        zip_code=resolved_zip_code,
        zoning_summary=zoning_summary,
    )

    routing_reason = (
        "No new property address was provided, so the request reused the active property context from the current session."
        if reused_active_property
        else "A property address was detected, so the request was enriched with parcel-specific Gridics zoning data."
    )
    return {
        "question_type": question_type,
        "routing_reason": routing_reason,
        "request_classification": _request_classification_payload(question_type, routing_reason),
        "address_context": address_context,
        "address_resolution": _address_resolution_payload(
            detected_address=resolved_address,
            standardized_address=standardized_address,
            state_env=resolved_state_env,
            zip_code=resolved_zip_code,
            address_source=address_context["address_source"],
        ),
        "follow_up_context": _follow_up_context_payload(
            question_type=question_type,
            standardized_address=standardized_address,
            state_env=resolved_state_env,
            zip_code=resolved_zip_code,
            zoning_summary=zoning_summary,
        ),
        "gridics": {
            "zone_combination_name": zoning_summary.get("zone_combination_name"),
            "typology": zoning_summary.get("typology"),
            "calculation_status": zoning_summary.get("calculation_status"),
            "constraints": zoning_summary.get("constraints"),
            "notes": zoning_summary.get("notes"),
        },
        "knowledge": primary_knowledge,
        "constraints_knowledge": constraints_knowledge,
    }
