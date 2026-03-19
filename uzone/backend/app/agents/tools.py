"""Agno tools backed by UZone services."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from app.schemas.gridics import GridicsBuilding, GridicsDataRow, GridicsResponse


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

_TYPOLOGY_MAP = {
    1: "Single-Family Residential",
    2: "Duplex",
    3: "Multi-Family",
    4: "Commercial",
    5: "Industrial",
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
_ANALYZE_RETRY_ATTEMPTS = max(1, int(os.getenv("UZONE_ANALYZE_RETRY_ATTEMPTS", "2")))
_ANALYZE_RETRY_DELAY_SECONDS = max(0.0, float(os.getenv("UZONE_ANALYZE_RETRY_DELAY_SECONDS", "0.35")))


@dataclass
class _ResolvedAddress:
    question_type: str
    provided_address: str | None
    detected_address: str | None
    standardized_address: str | None
    state_env: str | None
    zip_code: str | None
    address_source: str | None
    reused_active_property: bool

    @property
    def lookup_ready(self) -> bool:
        return bool(self.standardized_address and self.state_env and self.zip_code)


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


def _build_gridics_client() -> _GridicsClient:
    return _GridicsClient(
        api_key=_get_gridics_api_key(),
        base_url=_GRIDICS_BASE_URL,
        timeout_seconds=_GRIDICS_TIMEOUT_SECONDS,
    )


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
    if address or _extract_address_from_query(query):
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

    return any(
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


def _normalize_zip_code(zip_code: str | int | None) -> str | None:
    if isinstance(zip_code, int):
        return str(zip_code)
    if isinstance(zip_code, str):
        normalized = zip_code.strip()
        return normalized or None
    return None


def _request_classification_payload(question_type: str, routing_reason: str) -> dict[str, str]:
    return {
        "type": question_type,
        "label": "specific address" if question_type == "specific_address" else "general zoning",
        "reason": routing_reason,
    }


def _address_resolution_payload(resolution: _ResolvedAddress) -> dict[str, Any]:
    return {
        "input_address": resolution.detected_address,
        "standardized_address": resolution.standardized_address,
        "resolved_state_env": resolution.state_env,
        "resolved_zip_code": resolution.zip_code,
        "address_source": resolution.address_source,
        "lookup_ready": resolution.lookup_ready,
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
        "guidance": "Use this property as the default context for follow-up zoning questions until the user supplies a different address.",
    }


def _format_typology(typology: str | int | None) -> str | None:
    if typology is None:
        return None
    if isinstance(typology, int):
        return f"{typology} - {_TYPOLOGY_MAP.get(typology, 'Other')}"
    return str(typology)


def _first_numeric(values: list[Any]) -> float | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                return float(match.group(0))
        if isinstance(value, list):
            nested = _first_numeric(value)
            if nested is not None:
                return nested
    return None


def _flatten_messages(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        if value.strip():
            out.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_messages(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_flatten_messages(item))
    return out


def _extract_gridics_notes(raw_payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in {"notifications", "messages", "warnings", "notes"}:
                    notes.extend(_flatten_messages(value))
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(raw_payload)
    return notes


def _extract_gridics_record(payload: dict[str, Any]) -> tuple[GridicsDataRow, GridicsBuilding]:
    parsed = GridicsResponse.model_validate(payload)
    if not parsed.data:
        raise ValueError("Gridics could not resolve the address. No data rows returned.")

    data_row = parsed.data[0]
    if not data_row.Buildings:
        raise ValueError(f"Gridics found the parcel for '{data_row.Address}' but no zoning/building data was attached.")

    return data_row, data_row.Buildings[0]


def _extract_gridics_zoning_summary(payload: dict[str, Any]) -> dict[str, Any]:
    data_row, building = _extract_gridics_record(payload)
    envelope = building.Envelope

    return {
        "resolved_address": data_row.Address,
        "zone_combination_name": building.ZoningAllowance.ZoneCombinationName,
        "typology": _format_typology(building.ZoningAllowance.BuildingTypologyId),
        "calculation_status": data_row.CalculationStatus,
        "notes": _extract_gridics_notes(payload),
        "overlays": [overlay.Name for overlay in building.Overlays],
        "uses": [
            {
                "allowance": use.AllowedUsesName,
                "label": use.CalibrationUsesLabel,
                "type_name": use.TypeName,
            }
            for use in building.Uses
        ],
        "envelope_metrics": {
            "lot_area_sqft": envelope.LotAreaFeet,
            "lot_area_acres": envelope.LotAreaAcres,
            "max_density_units": envelope.DensityUnits,
            "max_height_stories": envelope.TotalBuidingHeight,
            "max_building_area_sqft": envelope.MaxBuildingAreaAllowed,
            "effective_lot_coverage": envelope.EffectiveLotCoverage,
        },
        "constraints": {
            "max_far": _first_numeric([envelope.FloorAreaRatio, envelope.FloorAreaRatioCapacity]),
            "max_units": _first_numeric([envelope.DensityUnits]),
            "max_height_ft": _first_numeric([envelope.TotalBuildingHeightFeet, envelope.TotalBuidingHeight]),
            "front_setback_ft": _first_numeric(
                [
                    envelope.EffectivePFrontSetbackPrincipal,
                    envelope.EffectivePFrontSetbackSecondary,
                    building.CalibrationGeneral.PFrontSetbackPrincipalMax,
                    building.CalibrationGeneral.PFrontSetbackSecondaryMax,
                ]
            ),
            "side_setback_ft": _first_numeric([envelope.EffectivePSideSetback, building.CalibrationGeneral.PSideSetbackMax]),
            "rear_setback_ft": _first_numeric([envelope.EffectivePRearSetback, building.CalibrationGeneral.PRearSetbackMax]),
        },
    }


def _format_constraint_value(value: float | None, *, suffix: str = "") -> str:
    if value is None:
        return "Not specified"
    if value.is_integer():
        rendered = str(int(value))
    else:
        rendered = str(value)
    return f"{rendered}{suffix}"


def _build_memo_context(
    *,
    standardized_address: str,
    state_env: str,
    zip_code: str,
    zoning_summary: dict[str, Any],
) -> dict[str, Any]:
    constraints = zoning_summary.get("constraints") or {}
    resolved_address = zoning_summary.get("resolved_address") or standardized_address
    address_suffix = f"{state_env.upper()} {zip_code}"
    if not str(resolved_address).upper().endswith(address_suffix):
        resolved_address = f"{resolved_address}, {address_suffix}"
    return {
        "resolved_address": resolved_address,
        "zone_classification": zoning_summary.get("zone_combination_name"),
        "typology": zoning_summary.get("typology"),
        "dimensional_standards": {
            "Max FAR": _format_constraint_value(constraints.get("max_far")),
            "Max Units": _format_constraint_value(constraints.get("max_units"), suffix=" units"),
            "Max Height": _format_constraint_value(constraints.get("max_height_ft"), suffix=" ft"),
            "Front Setback": _format_constraint_value(constraints.get("front_setback_ft"), suffix=" ft"),
            "Side Setback": _format_constraint_value(constraints.get("side_setback_ft"), suffix=" ft"),
            "Rear Setback": _format_constraint_value(constraints.get("rear_setback_ft"), suffix=" ft"),
        },
        "gridics_system_notes": zoning_summary.get("notes") or [],
        "agent_directives": (
            "Base the memorandum on the structured zoning summary and customer-scoped knowledge. "
            "If parcel-specific Gridics context and broader code references do not align cleanly, explain the discrepancy "
            "professionally and avoid overstating certainty."
        ),
    }


def _clean_knowledge_results(knowledge_dict: dict | None) -> list[dict]:
    """Flatten and trim knowledge results to reduce LLM noise."""
    if not knowledge_dict or not knowledge_dict.get("results"):
        return []

    cleaned: list[dict[str, Any]] = []
    for result in knowledge_dict["results"]:
        meta_data = result.get("meta_data", {})
        if meta_data.get("similarity_score", 1.0) < 0.15:
            continue
        cleaned.append(
            {
                "section_title": meta_data.get("section_title"),
                "source_url": meta_data.get("section_key", meta_data.get("source_url")),
                "content": result.get("content", "")[:1500],
            }
        )
    return cleaned


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
        (
            "Explain this zoning district in plain English for this property, including what is typically allowed here, "
            "what approval or reference sections matter most, and any numeric development standards that apply."
        ),
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


def _resolve_address_context(
    *,
    query: str,
    address: str | None,
    state_env: str | None,
    zip_code: str | int | None,
    run_context: Any,
) -> _ResolvedAddress:
    question = query.strip()
    if not question:
        raise ValueError("Query text is required.")

    provided_address = address.strip() if isinstance(address, str) and address.strip() else None
    extracted_address = None if provided_address else _extract_address_from_query(question)
    active_property_context = _get_active_property_context(run_context)
    resolved_address = provided_address or extracted_address
    reused_active_property = False

    if not resolved_address and _should_reuse_active_property(question, active_property_context):
        resolved_address = str(active_property_context.get("standardized_address") or "").strip() or None
        reused_active_property = bool(resolved_address)

    question_type = _classify_question(question, resolved_address)
    if question_type != "specific_address":
        return _ResolvedAddress(
            question_type=question_type,
            provided_address=provided_address,
            detected_address=None,
            standardized_address=None,
            state_env=None,
            zip_code=None,
            address_source=None,
            reused_active_property=reused_active_property,
        )

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
    normalized_zip_code = _normalize_zip_code(zip_code)
    resolved_zip_code = (
        normalized_zip_code
        if normalized_zip_code
        else (
            str(active_property_context.get("zip_code")).strip()
            if reused_active_property and active_property_context and active_property_context.get("zip_code")
            else _infer_zip(standardized_address)
        )
    )

    return _ResolvedAddress(
        question_type=question_type,
        provided_address=provided_address,
        detected_address=resolved_address,
        standardized_address=standardized_address,
        state_env=resolved_state_env,
        zip_code=resolved_zip_code,
        address_source="argument" if provided_address else ("session" if reused_active_property else "query"),
        reused_active_property=reused_active_property,
    )


def _summarize_attempt_failure(
    *,
    attempt: int,
    stage: str,
    error: Exception,
    query: str,
    client_id: str | None,
    question_type: str | None = None,
    address_context: dict[str, Any] | None = None,
    gridics_call_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "attempt": attempt,
        "stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "query": query,
        "client_id": client_id,
        "question_type": question_type,
        "address_context": address_context,
        "gridics_call_log": gridics_call_log or [],
    }


def _format_failure_details(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True, default=str)


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


def _analyze_customer_zoning_request_once(
    *,
    query: str,
    knowledge_limit: int,
    resolved_client_id: str,
    resolution: _ResolvedAddress,
    run_context: Any,
    gridics_client: _GridicsClient | None,
) -> dict[str, Any]:
    question = query.strip()

    if resolution.question_type == "general_zoning":
        routing_reason = "No property address was detected, so the request was handled as a general zoning question."
        knowledge = query_customer_zoning_code(
            query=question,
            limit=knowledge_limit,
            client_id=resolved_client_id,
        )
        return {
            "question_type": "general_zoning",
            "routing_reason": "No property address was detected, handling as general zoning.",
            "request_classification": _request_classification_payload("general_zoning", routing_reason),
            "follow_up_context": _follow_up_context_payload(question_type="general_zoning"),
            "knowledge": knowledge,
            "regulatory_knowledge": _clean_knowledge_results(knowledge),
        }

    address_context = {
        "address_source": resolution.address_source,
        "detected_address": resolution.detected_address,
        "standardized_address": resolution.standardized_address,
        "state_env": resolution.state_env,
        "zip_code": resolution.zip_code,
    }
    address_resolution = _address_resolution_payload(resolution)

    if not resolution.lookup_ready:
        routing_reason = "A property address was detected, but it was missing enough location detail for a Gridics lookup."
        return {
            "question_type": "specific_address",
            "needs_address_clarification": True,
            "clarification_prompt": "Please provide the full property address, including state and ZIP code.",
            "detected_address": resolution.detected_address,
            "routing_reason": routing_reason,
            "request_classification": _request_classification_payload("specific_address", routing_reason),
            "address_context": address_context,
            "address_resolution": address_resolution,
            "follow_up_context": _follow_up_context_payload(
                question_type="specific_address",
                standardized_address=resolution.standardized_address,
                state_env=resolution.state_env,
                zip_code=resolution.zip_code,
                zoning_summary=None,
            ),
        }

    client = gridics_client or _build_gridics_client()
    property_record = client.get_property_record(
        state_env=resolution.state_env or "",
        address=resolution.standardized_address or "",
        zip_code=resolution.zip_code or "",
    )
    zoning_summary = _extract_gridics_zoning_summary(property_record)

    knowledge_query = _build_augmented_knowledge_query(
        query=question,
        standardized_address=resolution.standardized_address or "",
        zoning_summary=zoning_summary,
    )
    primary_knowledge = query_customer_zoning_code(
        query=knowledge_query,
        limit=knowledge_limit,
        client_id=resolved_client_id,
    )

    constraints_knowledge = None
    cleaned_primary_knowledge = _clean_knowledge_results(primary_knowledge)
    if _needs_constraints_lookup(zoning_summary) or not cleaned_primary_knowledge:
        constraints_knowledge = query_customer_zoning_code(
            query=_build_constraints_knowledge_query(
                query=question,
                standardized_address=resolution.standardized_address or "",
                zoning_summary=zoning_summary,
            ),
            limit=knowledge_limit,
            client_id=resolved_client_id,
        )

    zone_name = zoning_summary.get("zone_combination_name") or "specified"
    uses_query = f"What are the permitted, conditional, and restricted uses for the {zone_name} zoning district?"
    uses_knowledge = query_customer_zoning_code(
        query=uses_query,
        limit=3,
        client_id=resolved_client_id,
    )

    _set_active_property_context(
        run_context,
        standardized_address=resolution.standardized_address or "",
        state_env=resolution.state_env or "",
        zip_code=resolution.zip_code or "",
        zoning_summary=zoning_summary,
    )

    memo_context = _build_memo_context(
        standardized_address=resolution.standardized_address or "",
        state_env=resolution.state_env or "",
        zip_code=resolution.zip_code or "",
        zoning_summary=zoning_summary,
    )

    routing_reason = (
        "Reused active property context from session."
        if resolution.reused_active_property
        else "Enriched with parcel-specific Gridics zoning data."
    )
    request_reason = (
        "Reused the active property context from the session for this follow-up question."
        if resolution.reused_active_property
        else "A property address was detected, so the request was enriched with parcel-specific Gridics zoning data."
    )

    return {
        "question_type": "specific_address",
        "routing_reason": routing_reason,
        "request_classification": _request_classification_payload("specific_address", request_reason),
        "address_context": address_context,
        "address_resolution": address_resolution,
        "follow_up_context": _follow_up_context_payload(
            question_type="specific_address",
            standardized_address=resolution.standardized_address,
            state_env=resolution.state_env,
            zip_code=resolution.zip_code,
            zoning_summary=zoning_summary,
        ),
        "gridics": zoning_summary,
        "memo_context": memo_context,
        "property_profile": {
            "address": memo_context["resolved_address"],
            "zone_classification": memo_context["zone_classification"],
            "typology": memo_context["typology"],
            "calculation_status": zoning_summary.get("calculation_status"),
        },
        "dimensional_standards": memo_context["dimensional_standards"],
        "critical_notes": memo_context["gridics_system_notes"],
        "knowledge": primary_knowledge,
        "regulatory_knowledge": cleaned_primary_knowledge,
        "constraints_knowledge": {"results": _clean_knowledge_results(constraints_knowledge)} if constraints_knowledge else None,
        "uses_knowledge": {"results": _clean_knowledge_results(uses_knowledge)},
        "agent_directives": memo_context["agent_directives"],
    }


def analyze_customer_zoning_request(
    query: str,
    address: str | None = None,
    state_env: str | None = None,
    zip_code: str | int | None = None,
    knowledge_limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
) -> dict:
    """
    Analyze a tenant-scoped zoning request using customer knowledge and Gridics data.

    The tool returns a structured dictionary suitable for downstream agent use, including
    address resolution, parcel context, memo-friendly summaries, and trimmed knowledge hits.
    """
    failures: list[dict[str, Any]] = []

    for attempt in range(1, _ANALYZE_RETRY_ATTEMPTS + 1):
        stage = "initializing"
        resolved_client_id: str | None = None
        resolution: _ResolvedAddress | None = None
        client: _GridicsClient | None = None

        try:
            stage = "resolving_client_id"
            resolved_client_id = _resolve_client_id(client_id, run_context)

            resolution = _resolve_address_context(
                query=query,
                address=address,
                state_env=state_env,
                zip_code=zip_code,
                run_context=run_context,
            )

            if resolution.question_type == "specific_address" and resolution.lookup_ready:
                client = _build_gridics_client()

            stage = "analyzing_request"
            result = _analyze_customer_zoning_request_once(
                query=query,
                knowledge_limit=knowledge_limit,
                resolved_client_id=resolved_client_id,
                resolution=resolution,
                run_context=run_context,
                gridics_client=client,
            )

            if failures:
                result["retry_debug"] = {
                    "recovered": True,
                    "attempts": attempt,
                    "failed_attempts": failures,
                }

            return result

        except Exception as exc:
            failure = _summarize_attempt_failure(
                attempt=attempt,
                stage=stage,
                error=exc,
                query=query,
                client_id=resolved_client_id,
                question_type=resolution.question_type if resolution else None,
                address_context=(
                    {
                        "address_source": resolution.address_source,
                        "detected_address": resolution.detected_address,
                        "standardized_address": resolution.standardized_address,
                        "state_env": resolution.state_env,
                        "zip_code": resolution.zip_code,
                    }
                    if resolution and resolution.question_type == "specific_address"
                    else None
                ),
                gridics_call_log=client.call_log if client is not None else None,
            )
            failures.append(failure)
            if attempt < _ANALYZE_RETRY_ATTEMPTS:
                time.sleep(_ANALYZE_RETRY_DELAY_SECONDS)
                continue

            details = {
                "message": f"analyze_customer_zoning_request failed after {attempt} attempt(s)",
                "failures": failures,
            }
            raise RuntimeError(_format_failure_details(details)) from exc

    raise RuntimeError("analyze_customer_zoning_request failed before any attempt was executed.")
