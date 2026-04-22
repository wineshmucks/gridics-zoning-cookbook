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

from app.schemas.assistant_guardrails import AssistantTurnContract
from app.schemas.gridics import GridicsBuilding, GridicsDataRow, GridicsResponse
from app.services.agentic.confirmation_service import (
    build_pending_confirmation_prompt,
    classify_pending_property_confirmation_response,
)
from app.services.agentic.jurisdiction_resolver import resolve_jurisdiction_for_property_request
from app.services.agentic.policy_service import evaluate_policy_decision
from app.services.agentic.response_templates import (
    insufficient_evidence_message,
    jurisdiction_lock_message,
    missing_address_details_message,
)
from app.services.agentic.response_grounding import (
    build_evidence_pack,
    citation_completeness_report,
    grounding_verdict,
)


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
_RECENT_STANDARDIZED_ADDRESS_SESSION_KEY = "recent_standardized_address"
_PENDING_PROPERTY_CONFIRMATION_SESSION_KEY = "pending_property_confirmation"
_JURISDICTION_LOCK_SESSION_KEY = "jurisdiction_lock"
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
    state_code: str | None
    zip_code: str | None
    address_source: str | None
    reused_active_property: bool
    confirmation_state: str | None = None
    confirmation_prompt: str | None = None
    confirmation_reason: str | None = None
    confirmation_requested_address: str | None = None
    confirmation_resolved_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def lookup_ready(self) -> bool:
        # Gridics can resolve from coordinates alone, or from an address/state context.
        has_coordinates = self.latitude is not None and self.longitude is not None
        return bool(has_coordinates or (self.state_code and self.standardized_address))


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
                    "received": True,
                    "status_code": getattr(resp, "status", 200),
                    "response_length": len(body),
                }
                self.call_log.append(trace_entry)
                return parsed
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            trace_entry["response"] = {
                "received": True,
                "status_code": exc.code,
                "response_length": len(payload),
            }
            self.call_log.append(trace_entry)
            raise RuntimeError(f"Gridics HTTP {exc.code}: {payload}") from exc
        except urllib.error.URLError as exc:
            trace_entry["error"] = f"Gridics connection error: {exc.reason}"
            self.call_log.append(trace_entry)
            raise RuntimeError(f"Gridics connection error: {exc.reason}") from exc

    def get_property_record(self, *, state_code: str, address: str, zip_code: str | None) -> dict[str, Any]:
        return self._get(
            "/property-record",
            {"state_env": state_code, "address": address, "zipCode": zip_code},
        )

    def get_property_record_by_coordinates(self, *, latitude: float, longitude: float, state_env: str | None = None) -> dict[str, Any]:
        return self._get(
            "/property-record",
            {"lat": latitude, "lon": longitude, "state_env": state_env},
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


_CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _normalize_client_id(candidate: str | None) -> str | None:
    if not isinstance(candidate, str):
        return None
    resolved = candidate.strip()
    if not resolved:
        return None
    if resolved.lower() in {"default", "null", "none", "unknown"}:
        return None
    return resolved


def _looks_like_client_id(candidate: str | None) -> bool:
    resolved = _normalize_client_id(candidate)
    if not resolved:
        return False
    if any(separator in resolved for separator in {",", " "}):
        return False
    return bool(_CLIENT_ID_PATTERN.fullmatch(resolved))


def _resolve_client_id(client_id: str | None, run_context: Any = None) -> str:
    resolved_client_id = _normalize_client_id(client_id)
    if resolved_client_id and not _looks_like_client_id(resolved_client_id):
        resolved_client_id = None

    dependencies = getattr(run_context, "dependencies", None)
    if isinstance(dependencies, dict):
        dependency_client_id = _normalize_client_id(dependencies.get("client_id"))
        if dependency_client_id and _looks_like_client_id(dependency_client_id):
            resolved_client_id = resolved_client_id or dependency_client_id

    if not resolved_client_id:
        raise ValueError("client_id is required to query customer zoning knowledge.")

    return resolved_client_id


def _load_tenant_client(resolved_client_id: str):
    try:
        from sqlalchemy import select

        from app.db.models import TenantClient
        from app.db.session import SessionLocal
    except Exception:
        return None

    try:
        with SessionLocal() as db:
            return db.scalar(select(TenantClient).where(TenantClient.client_id == resolved_client_id))
    except Exception:
        return None


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


def _get_pending_property_confirmation(run_context: Any) -> dict[str, Any] | None:
    session_state = _get_session_state(run_context)
    pending_context = session_state.get(_PENDING_PROPERTY_CONFIRMATION_SESSION_KEY)
    return pending_context if isinstance(pending_context, dict) else None


def _get_recent_standardized_address(run_context: Any) -> str | None:
    session_state = _get_session_state(run_context)
    recent_context = session_state.get(_RECENT_STANDARDIZED_ADDRESS_SESSION_KEY)
    if not isinstance(recent_context, dict):
        return None
    standardized_address = str(recent_context.get("standardized_address") or "").strip()
    return standardized_address or None


def _prefer_recent_standardized_address(address: str | None, run_context: Any) -> str | None:
    normalized_address = str(address or "").strip()
    if not normalized_address:
        return _get_recent_standardized_address(run_context)

    recent_standardized_address = _get_recent_standardized_address(run_context)
    if not recent_standardized_address:
        return normalized_address

    normalized_recent = _normalize_address_for_comparison(recent_standardized_address)
    normalized_current = _normalize_address_for_comparison(normalized_address)

    if normalized_current == normalized_recent:
        return recent_standardized_address

    if normalized_current and normalized_recent.startswith(normalized_current):
        return recent_standardized_address

    return normalized_address


def _pending_property_confirmation_matches(
    *,
    query: str,
    pending_context: dict[str, Any] | None,
) -> bool:
    if not pending_context:
        return False

    candidate_address = _extract_address_from_query(query) or query
    resolved_address = str(pending_context.get("resolved_address") or "").strip() or None
    if not candidate_address or not resolved_address:
        return False

    return not _addresses_differ(candidate_address, resolved_address)


def _set_active_property_context(
    run_context: Any,
    *,
    standardized_address: str,
    state_code: str | None,
    zip_code: str,
    zoning_summary: dict[str, Any],
    latitude: float | None = None,
    longitude: float | None = None,
) -> None:
    session_state = getattr(run_context, "session_state", None)
    if not isinstance(session_state, dict):
        return

    active_context: dict[str, Any] = {
        "standardized_address": standardized_address,
        "zip_code": zip_code,
        "zone_combination_name": zoning_summary.get("zone_combination_name"),
        "typology": zoning_summary.get("typology"),
        "constraints": zoning_summary.get("constraints"),
        "latitude": latitude,
        "longitude": longitude,
    }
    if state_code:
        active_context["state_code"] = state_code
    session_state[_ACTIVE_PROPERTY_SESSION_KEY] = active_context


def _set_pending_property_confirmation(
    run_context: Any,
    *,
    requested_address: str | None,
    resolved_address: str | None,
    state_code: str | None,
    zip_code: str | None,
) -> None:
    session_state = getattr(run_context, "session_state", None)
    if not isinstance(session_state, dict):
        return
    session_state[_PENDING_PROPERTY_CONFIRMATION_SESSION_KEY] = {
        "requested_address": requested_address,
        "resolved_address": resolved_address,
        "state_code": state_code,
        "zip_code": zip_code,
    }


def _clear_pending_property_confirmation(run_context: Any) -> None:
    session_state = getattr(run_context, "session_state", None)
    if not isinstance(session_state, dict):
        return
    session_state.pop(_PENDING_PROPERTY_CONFIRMATION_SESSION_KEY, None)


def _get_jurisdiction_lock(run_context: Any) -> dict[str, Any] | None:
    session_state = _get_session_state(run_context)
    lock = session_state.get(_JURISDICTION_LOCK_SESSION_KEY)
    return lock if isinstance(lock, dict) else None


def _set_jurisdiction_lock(
    run_context: Any,
    *,
    tenant_client: Any,
    resolved_city: str | None,
    resolved_state: str | None,
) -> None:
    session_state = getattr(run_context, "session_state", None)
    if not isinstance(session_state, dict):
        return
    tenant_label = str(getattr(tenant_client, "city_name", "") or "").strip()
    lock_label = tenant_label or str(resolved_city or "").strip() or "current jurisdiction"
    session_state[_JURISDICTION_LOCK_SESSION_KEY] = {
        "label": lock_label,
        "city": str(resolved_city or "").strip() or None,
        "state": str(resolved_state or "").strip().lower() or None,
    }


def _confidence_band(*, grounding: dict[str, Any] | None, citation_check: dict[str, Any] | None) -> str:
    if grounding and not grounding.get("answer_ready", False):
        return "needs_verification"
    if citation_check and not citation_check.get("is_complete", True):
        return "needs_verification"
    evidence_count = int((grounding or {}).get("evidence_count") or 0)
    if evidence_count >= 3:
        return "high_confidence"
    if evidence_count >= 1:
        return "medium_confidence"
    return "needs_verification"


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
            "how high",
        "how many stories",
        "how many floors",
        "how many levels",
        "what height",
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


def _normalize_address_for_comparison(address: str | None) -> str:
    if not isinstance(address, str):
        return ""
    normalized = _standardize_address(address).lower()
    normalized = re.sub(r"[^a-z0-9]+", "", normalized)
    return normalized


def _addresses_differ(requested: str | None, resolved: str | None) -> bool:
    requested_normalized = _normalize_address_for_comparison(requested)
    resolved_normalized = _normalize_address_for_comparison(resolved)
    if not requested_normalized or not resolved_normalized:
        return False
    return requested_normalized != resolved_normalized


def _infer_state_code(address: str) -> str | None:
    match = re.search(r"\b([A-Z]{2})\b(?:\s+\d{5}(?:-\d{4})?)?$", address.upper())
    if not match:
        return None
    return _STATE_MAP.get(match.group(1))


def _infer_zip(address: str) -> str | None:
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", address)
    return match.group(1) if match else None


def _extract_gridics_street_address(address: str) -> str:
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0]
    return address.strip(" ,")


def _normalize_zip_code(zip_code: str | int | None) -> str | None:
    if isinstance(zip_code, int):
        return str(zip_code)
    if isinstance(zip_code, str):
        normalized = zip_code.strip()
        return normalized or None
    return None


def _coerce_float(value: float | int | str | None) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _request_classification_payload(question_type: str, routing_reason: str) -> dict[str, str]:
    return {
        "type": question_type,
        "label": "specific address" if question_type == "specific_address" else "general zoning",
        "reason": routing_reason,
    }


def _assistant_turn_payload(
    *,
    intent_type: str,
    policy_decision: dict[str, Any],
    jurisdiction_status: str,
    needs_clarification: bool = False,
    clarification_type: str = "none",
    confidence: float = 0.85,
) -> dict[str, Any]:
    return AssistantTurnContract(
        intent_type=intent_type,  # type: ignore[arg-type]
        jurisdiction_status=jurisdiction_status,  # type: ignore[arg-type]
        needs_clarification=needs_clarification,
        clarification_type=clarification_type,  # type: ignore[arg-type]
        policy_decision=policy_decision,
        confidence=confidence,
    ).model_dump()


def _address_resolution_payload(resolution: _ResolvedAddress) -> dict[str, Any]:
    payload = {
        "input_address": resolution.detected_address,
        "standardized_address": resolution.standardized_address,
        "resolved_state_code": resolution.state_code,
        "resolved_zip_code": resolution.zip_code,
        "address_source": resolution.address_source,
        "lookup_ready": resolution.lookup_ready,
    }
    if resolution.latitude is not None and resolution.longitude is not None:
        payload["latitude"] = resolution.latitude
        payload["longitude"] = resolution.longitude
    return payload


def _follow_up_context_payload(
    *,
    question_type: str,
    standardized_address: str | None = None,
    state_code: str | None = None,
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
    envelope_metrics = zoning_summary.get("envelope_metrics") if isinstance(zoning_summary, dict) else None
    max_height_ft = constraints.get("max_height_ft") if isinstance(constraints, dict) else None
    max_height_stories = envelope_metrics.get("max_height_stories") if isinstance(envelope_metrics, dict) else None
    story_equivalent = max_height_stories
    if story_equivalent is None and isinstance(max_height_ft, (int, float)) and max_height_ft > 0:
        story_equivalent = round(float(max_height_ft) / 12.0, 1)
    return {
        "context_type": "specific_address",
        "active_location": {
            "standardized_address": standardized_address,
            "state_code": state_code,
            "zip_code": zip_code,
            "zone_combination_name": zoning_summary.get("zone_combination_name") if zoning_summary else None,
            "typology": zoning_summary.get("typology") if zoning_summary else None,
            "constraints": constraints,
            "max_height_ft": max_height_ft,
            "max_height_stories": max_height_stories,
            "story_equivalent": story_equivalent,
        },
        "reuse_for_follow_ups": True,
        "guidance": "Use this property as the default context for follow-up zoning questions until the user supplies a different address. If the user asks how many stories, reuse the active property height context instead of asking for a new address.",
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
        "resolved_city": data_row.City,
        "resolved_state": data_row.State,
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
    state_code: str | None,
    zip_code: str,
    zoning_summary: dict[str, Any],
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    constraints = zoning_summary.get("constraints") or {}
    envelope_metrics = zoning_summary.get("envelope_metrics") or {}
    resolved_address = zoning_summary.get("resolved_address") or standardized_address
    resolved_state = str(zoning_summary.get("resolved_state") or "").strip().upper() or None
    suffix_parts = [part for part in [resolved_state or (state_code.upper() if state_code else None), zip_code] if part]
    address_suffix = " ".join(suffix_parts)
    if address_suffix and not str(resolved_address).upper().endswith(address_suffix):
        resolved_address = f"{resolved_address}, {address_suffix}"
    max_height_ft = constraints.get("max_height_ft")
    max_height_stories = envelope_metrics.get("max_height_stories")
    story_equivalent = max_height_stories
    if story_equivalent is None and isinstance(max_height_ft, (int, float)) and max_height_ft > 0:
        story_equivalent = round(float(max_height_ft) / 12.0, 1)
    return {
        "resolved_address": resolved_address,
        "zone_classification": zoning_summary.get("zone_combination_name"),
        "typology": zoning_summary.get("typology"),
        "dimensional_standards": {
            "Max FAR": _format_constraint_value(constraints.get("max_far")),
            "Max Units": _format_constraint_value(constraints.get("max_units"), suffix=" units"),
            "Max Height": _format_constraint_value(constraints.get("max_height_ft"), suffix=" ft"),
            "Max Stories": _format_constraint_value(max_height_stories),
            "Approx. Stories": _format_constraint_value(story_equivalent),
            "Front Setback": _format_constraint_value(constraints.get("front_setback_ft"), suffix=" ft"),
            "Side Setback": _format_constraint_value(constraints.get("side_setback_ft"), suffix=" ft"),
            "Rear Setback": _format_constraint_value(constraints.get("rear_setback_ft"), suffix=" ft"),
        },
        "gridics_system_notes": zoning_summary.get("notes") or [],
        "story_equivalent": story_equivalent,
        "source_references": sources or [],
        "source_citations": [
            str(item.get("citation_markdown") or f"[{item.get('section_title') or 'Untitled section'}]({item.get('section_url') or item.get('page_url') or ''})").strip()
            for item in (sources or [])
            if isinstance(item, dict) and (item.get("section_url") or item.get("page_url"))
        ],
        "agent_directives": (
            "Base the memorandum on the structured zoning summary and customer-scoped knowledge. "
            "If parcel-specific Gridics context and broader code references do not align cleanly, explain the discrepancy "
            "professionally and avoid overstating certainty."
        ),
    }


def _address_mismatch_confirmation_payload(
    *,
    requested_address: str | None,
    resolved_address: str | None,
    zoning_summary: dict[str, Any],
) -> dict[str, Any]:
    resolved_city = str(zoning_summary.get("resolved_city") or "").strip() or None
    resolved_state = str(zoning_summary.get("resolved_state") or "").strip() or None
    resolved_parts = [resolved_address]
    if resolved_city:
        resolved_parts.append(resolved_city)
    if resolved_state:
        resolved_parts.append(resolved_state.upper())
    resolved_rendered = ", ".join(part for part in resolved_parts if part)
    return {
        "needs_confirmation": True,
        "question_type": "specific_address",
        "requested_address": requested_address,
        "resolved_address": resolved_address,
        "resolved_location": resolved_rendered,
        "message": (
            f"The address you entered appears to resolve to {resolved_address}, not {requested_address}. "
            "Please confirm the address you want me to use before I continue."
        ),
        "confidence_band": "needs_verification",
        "jurisdiction_status": "needs_confirmation",
        "assistant_turn": _assistant_turn_payload(
            intent_type="specific_address",
            policy_decision={
                "decision": "clarify",
                "reason_code": "resolved_address_differs",
                "reason": "The resolved parcel differs from the requested address and needs confirmation.",
            },
            jurisdiction_status="needs_confirmation",
            needs_clarification=True,
            clarification_type="address_confirmation",
            confidence=0.95,
        ),
    }


def _build_source_references(evidence_pack: list[dict[str, str]]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in evidence_pack:
        if not isinstance(item, dict):
            continue
        section_title = str(item.get("section_title") or "Untitled section").strip()
        section_url = str(item.get("section_url") or "").strip()
        page_url = str(item.get("page_url") or "").strip()
        source_url = section_url or page_url
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)
        source: dict[str, str] = {
            "section_title": section_title,
            "section_url": section_url or page_url,
            "page_url": page_url or section_url or source_url,
            "citation_markdown": str(item.get("citation_markdown") or f"[{section_title}]({section_url or page_url})").strip(),
        }
        source_title = str(item.get("source_title") or "").strip()
        source_anchor = str(item.get("source_anchor") or "").strip()
        if source_title:
            source["source_title"] = source_title
        if source_anchor:
            source["source_anchor"] = source_anchor
        sources.append(source)
    return sources


def _clean_knowledge_results(knowledge_dict: dict | None) -> list[dict]:
    """Flatten and trim knowledge results to reduce LLM noise."""
    if not knowledge_dict or not knowledge_dict.get("results"):
        return []

    cleaned: list[dict[str, Any]] = []
    for result in knowledge_dict["results"]:
        meta_data = result.get("meta_data", {})
        if meta_data.get("similarity_score", 1.0) < 0.15:
            continue
        page_url = meta_data.get("page_url") or meta_data.get("source_url")
        source_anchor = meta_data.get("source_anchor")
        section_url = meta_data.get("section_url")
        if not section_url and page_url:
            section_url = f"{page_url}#{source_anchor}" if source_anchor else page_url
        cleaned.append(
            {
                "section_title": meta_data.get("section_title"),
                "page_url": page_url,
                "section_url": section_url,
                "source_title": meta_data.get("source_title"),
                "source_anchor": source_anchor,
                "source_url": page_url,
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
    state_code: str | None,
    zip_code: str | int | None,
    run_context: Any,
    latitude: float | int | str | None = None,
    longitude: float | int | str | None = None,
    tenant_client: Any = None,
) -> _ResolvedAddress:
    question = query.strip()
    if not question:
        raise ValueError("Query text is required.")

    tenant_settings = getattr(tenant_client, "settings_json", {}) or {}
    tenant_default_zip = str(tenant_settings.get("default_zip_code") or "").strip() or None

    provided_address = address.strip() if isinstance(address, str) and address.strip() else None
    resolved_latitude = _coerce_float(latitude)
    resolved_longitude = _coerce_float(longitude)
    if resolved_latitude is not None and resolved_longitude is not None:
        return _ResolvedAddress(
            question_type="specific_address",
            provided_address=provided_address,
            detected_address=provided_address,
            standardized_address=provided_address or "selected property",
            state_code=None,
            zip_code=_normalize_zip_code(zip_code) or tenant_default_zip,
            address_source="mapbox_coordinates",
            reused_active_property=False,
            latitude=resolved_latitude,
            longitude=resolved_longitude,
        )

    extracted_address = None if provided_address else _extract_address_from_query(question)
    active_property_context = _get_active_property_context(run_context)
    pending_property_confirmation = _get_pending_property_confirmation(run_context)
    resolved_address = provided_address or extracted_address
    reused_active_property = False
    reused_pending_confirmation = False

    if pending_property_confirmation:
        pending_resolved_address = str(pending_property_confirmation.get("resolved_address") or "").strip() or None
        pending_requested_address = str(pending_property_confirmation.get("requested_address") or "").strip() or None
        confirmation_decision = classify_pending_property_confirmation_response(
            query=question,
            pending_context=pending_property_confirmation,
            tenant_client=tenant_client,
        )
        normalized_question = question.strip().lower()
        if confirmation_decision.get("decision") != "confirm_pending" and pending_resolved_address:
            affirmative_replies = {"yes", "yes continue", "go ahead", "continue", "confirm", "confirmed", "y"}
            if normalized_question in affirmative_replies or normalized_question.startswith("yes,") or normalized_question.startswith("go ahead"):
                confirmation_decision = {"decision": "confirm_pending"}
        if resolved_address and _pending_property_confirmation_matches(
            query=resolved_address,
            pending_context=pending_property_confirmation,
        ):
            if pending_resolved_address:
                resolved_address = pending_resolved_address
                reused_pending_confirmation = True
        elif not resolved_address:
            if confirmation_decision.get("decision") == "confirm_pending" and pending_resolved_address:
                resolved_address = pending_resolved_address
                reused_pending_confirmation = True
            elif confirmation_decision.get("decision") == "clarify":
                clarification_prompt = str(
                    confirmation_decision.get("clarification_prompt")
                    or build_pending_confirmation_prompt(
                        pending_context=pending_property_confirmation,
                        reason=str(confirmation_decision.get("reason") or "").strip() or None,
                    )
                ).strip()
                return _ResolvedAddress(
                    question_type="specific_address",
                    provided_address=provided_address,
                    detected_address=None,
                    standardized_address=None,
                    state_code=None,
                    zip_code=None,
                    address_source="confirmation",
                    reused_active_property=False,
                    confirmation_state="clarify",
                    confirmation_prompt=clarification_prompt or None,
                    confirmation_reason=str(confirmation_decision.get("reason") or "").strip() or None,
                    confirmation_requested_address=pending_requested_address,
                    confirmation_resolved_address=pending_resolved_address,
                )

    if not resolved_address and _should_reuse_active_property(question, active_property_context):
        resolved_address = str(active_property_context.get("standardized_address") or "").strip() or None
        reused_active_property = bool(resolved_address)
        if resolved_latitude is None:
            resolved_latitude = _coerce_float(active_property_context.get("latitude"))
        if resolved_longitude is None:
            resolved_longitude = _coerce_float(active_property_context.get("longitude"))

    recent_standardized_address = _get_recent_standardized_address(run_context)
    reused_recent_standardized_address = False
    if resolved_address and recent_standardized_address:
        preferred_address = _prefer_recent_standardized_address(resolved_address, run_context)
        reused_recent_standardized_address = preferred_address != str(resolved_address or "").strip()
        resolved_address = preferred_address

    question_type = _classify_question(question, resolved_address)
    if question_type != "specific_address":
        return _ResolvedAddress(
            question_type=question_type,
            provided_address=provided_address,
            detected_address=None,
            standardized_address=None,
            state_code=None,
            zip_code=None,
            address_source=None,
            reused_active_property=reused_active_property,
        )

    standardized_address = _standardize_address(resolved_address or "")
    if resolved_latitude is not None and resolved_longitude is not None:
        resolved_state_code = None
    elif isinstance(state_code, str) and state_code.strip():
        resolved_state_code = state_code.strip().lower()
    elif reused_pending_confirmation and pending_property_confirmation and pending_property_confirmation.get("state_code"):
        resolved_state_code = str(pending_property_confirmation.get("state_code")).strip().lower()
    elif reused_active_property and active_property_context and active_property_context.get("state_code"):
        resolved_state_code = str(active_property_context.get("state_code")).strip().lower()
    else:
        resolved_state_code = _infer_state_code(standardized_address)

    normalized_zip_code = _normalize_zip_code(zip_code)
    if normalized_zip_code:
        resolved_zip_code = normalized_zip_code
    elif reused_pending_confirmation and pending_property_confirmation and pending_property_confirmation.get("zip_code"):
        resolved_zip_code = str(pending_property_confirmation.get("zip_code")).strip()
    elif reused_active_property and active_property_context and active_property_context.get("zip_code"):
        resolved_zip_code = str(active_property_context.get("zip_code")).strip()
    else:
        resolved_zip_code = _infer_zip(standardized_address) or tenant_default_zip

    if not normalized_zip_code and not _infer_zip(standardized_address) and tenant_default_zip:
        address_source = "tenant_default_zip"
    elif reused_recent_standardized_address:
        address_source = "session"
    elif provided_address:
        address_source = "confirmation" if reused_pending_confirmation else "argument"
    elif reused_active_property:
        address_source = "session"
    elif reused_pending_confirmation:
        address_source = "confirmation"
    else:
        address_source = "query"

    return _ResolvedAddress(
        question_type=question_type,
        provided_address=provided_address,
        detected_address=resolved_address,
        standardized_address=standardized_address,
        state_code=resolved_state_code,
        zip_code=resolved_zip_code,
        address_source=address_source,
        reused_active_property=reused_active_property,
        latitude=resolved_latitude,
        longitude=resolved_longitude,
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


def _specific_address_context_payload(resolution: _ResolvedAddress) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "address_source": resolution.address_source,
        "detected_address": resolution.detected_address,
        "standardized_address": resolution.standardized_address,
        "state_code": resolution.state_code,
        "zip_code": resolution.zip_code,
    }
    if resolution.latitude is not None and resolution.longitude is not None:
        payload["latitude"] = resolution.latitude
        payload["longitude"] = resolution.longitude
    return payload


def _general_zoning_response(
    *,
    question: str,
    knowledge_limit: int,
    resolved_client_id: str,
    tenant_client: Any,
) -> dict[str, Any]:
    policy_decision = evaluate_policy_decision(
        query=question,
        question_type="general_zoning",
        tenant_client=tenant_client,
    )
    if policy_decision["decision"] in {"deny", "clarify"}:
        return {
            "question_type": "general_zoning",
            "policy_decision": policy_decision,
            "assistant_turn": _assistant_turn_payload(
                intent_type="out_of_scope" if policy_decision["decision"] == "deny" else "general_zoning",
                policy_decision=policy_decision,
                jurisdiction_status="not_applicable",
                needs_clarification=policy_decision["decision"] == "clarify",
                clarification_type="scope" if policy_decision["decision"] == "clarify" else "none",
                confidence=0.9 if policy_decision["decision"] == "deny" else 0.7,
            ),
            "request_classification": _request_classification_payload(
                "general_zoning",
                "Detected as general zoning question.",
            ),
            "follow_up_context": _follow_up_context_payload(question_type="general_zoning"),
            "response_guardrail": {
                "message": policy_decision["reason"],
            },
        }

    routing_reason = "No property address was detected, so the request was handled as a general zoning question."
    knowledge = query_customer_zoning_code(
        query=question,
        limit=knowledge_limit,
        client_id=resolved_client_id,
    )
    evidence_pack = build_evidence_pack(knowledge)
    source_references = _build_source_references(evidence_pack)
    grounding = grounding_verdict(evidence_pack, min_refs=1)
    citation_check = citation_completeness_report(
        evidence_pack=evidence_pack,
        knowledge_payloads=[knowledge],
    )
    has_any_knowledge = bool((knowledge.get("results") or []) if isinstance(knowledge, dict) else [])
    if not grounding["answer_ready"] and not has_any_knowledge:
        return {
            "question_type": "general_zoning",
            "routing_reason": "No property address was detected, handling as general zoning.",
            "request_classification": _request_classification_payload("general_zoning", routing_reason),
            "policy_decision": policy_decision,
            "assistant_turn": _assistant_turn_payload(
                intent_type="general_zoning",
                policy_decision=policy_decision,
                jurisdiction_status="not_applicable",
                confidence=0.7,
            ),
            "follow_up_context": _follow_up_context_payload(question_type="general_zoning"),
            "knowledge": knowledge,
            "evidence_pack": evidence_pack,
            "source_references": source_references,
            "grounding": grounding,
            "citation_check": citation_check,
            "response_guardrail": {
                "message": insufficient_evidence_message(has_property_context=False)
            },
            "confidence_band": "needs_verification",
        }
    return {
        "question_type": "general_zoning",
        "routing_reason": "No property address was detected, handling as general zoning.",
        "request_classification": _request_classification_payload("general_zoning", routing_reason),
        "policy_decision": policy_decision,
        "assistant_turn": _assistant_turn_payload(
            intent_type="general_zoning",
            policy_decision=policy_decision,
            jurisdiction_status="not_applicable",
            confidence=0.85,
        ),
        "follow_up_context": _follow_up_context_payload(question_type="general_zoning"),
        "knowledge": knowledge,
        "evidence_pack": evidence_pack,
        "source_references": source_references,
        "grounding": grounding,
        "citation_check": citation_check,
        "regulatory_knowledge": _clean_knowledge_results(knowledge),
        "confidence_band": _confidence_band(grounding=grounding, citation_check=citation_check),
    }


def _pending_confirmation_response(
    *,
    question: str,
    resolution: _ResolvedAddress,
    tenant_client: Any,
) -> dict[str, Any]:
    policy_decision = evaluate_policy_decision(
        query=question,
        question_type="specific_address",
        tenant_client=tenant_client,
    )
    clarification_prompt = resolution.confirmation_prompt or build_pending_confirmation_prompt(
        pending_context={
            "requested_address": resolution.confirmation_requested_address,
            "resolved_address": resolution.confirmation_resolved_address,
        }
    )
    return {
        "question_type": "specific_address",
        "policy_decision": policy_decision,
        "assistant_turn": _assistant_turn_payload(
            intent_type="specific_address",
            policy_decision=policy_decision,
            jurisdiction_status="needs_confirmation",
            needs_clarification=True,
            clarification_type="address_confirmation",
            confidence=0.95,
        ),
        "needs_address_clarification": True,
        "clarification_prompt": clarification_prompt,
        "clarification_candidates": [resolution.confirmation_resolved_address]
        if resolution.confirmation_resolved_address
        else [],
        "jurisdiction_resolution": {
            "jurisdiction_status": "needs_confirmation",
            "is_ambiguous": True,
            "clarification_type": "address_confirmation",
            "clarification_prompt": clarification_prompt,
            "clarification_candidates": [resolution.confirmation_resolved_address]
            if resolution.confirmation_resolved_address
            else [],
        },
        "confidence_band": "needs_verification",
        "detected_address": resolution.confirmation_resolved_address,
        "routing_reason": "A pending parcel confirmation still needs a yes/no or replacement-address response.",
        "request_classification": _request_classification_payload(
            "specific_address",
            "Pending parcel confirmation requires a direct user response before analysis can continue.",
        ),
        "address_context": {
            "address_source": "confirmation",
            "detected_address": resolution.confirmation_resolved_address,
            "standardized_address": resolution.confirmation_resolved_address,
            "state_code": resolution.state_code,
            "zip_code": resolution.zip_code,
        },
        "address_resolution": {
            "input_address": resolution.confirmation_requested_address,
            "standardized_address": resolution.confirmation_resolved_address,
            "resolved_state_code": resolution.state_code,
            "resolved_zip_code": resolution.zip_code,
            "address_source": "confirmation",
            "lookup_ready": False,
        },
        "response_guardrail": {
            "needs_confirmation": True,
            "question_type": "specific_address",
            "requested_address": resolution.confirmation_requested_address,
            "resolved_address": resolution.confirmation_resolved_address,
            "resolved_location": resolution.confirmation_resolved_address,
            "message": clarification_prompt,
            "confidence_band": "needs_verification",
            "jurisdiction_status": "needs_confirmation",
            "assistant_turn": _assistant_turn_payload(
                intent_type="specific_address",
                policy_decision=policy_decision,
                jurisdiction_status="needs_confirmation",
                needs_clarification=True,
                clarification_type="address_confirmation",
                confidence=0.95,
            ),
        },
        "follow_up_context": _follow_up_context_payload(
            question_type="specific_address",
            standardized_address=resolution.confirmation_resolved_address,
            state_code=resolution.state_code,
            zip_code=resolution.zip_code,
            zoning_summary=None,
        ),
    }


def _missing_lookup_details_response(
    *,
    question: str,
    resolution: _ResolvedAddress,
    tenant_client: Any,
) -> dict[str, Any]:
    policy_decision = evaluate_policy_decision(
        query=question,
        question_type="specific_address",
        tenant_client=tenant_client,
    )
    jurisdiction_resolution = resolve_jurisdiction_for_property_request(
        tenant_client=tenant_client,
        standardized_address=resolution.standardized_address,
        lookup_ready=False,
    )
    routing_reason = "A property address was detected, but it was missing enough location detail for a Gridics lookup."
    return {
        "question_type": "specific_address",
        "policy_decision": policy_decision,
        "assistant_turn": _assistant_turn_payload(
            intent_type="specific_address",
            policy_decision=policy_decision,
            jurisdiction_status=str(jurisdiction_resolution.get("jurisdiction_status") or "unresolved"),
            needs_clarification=True,
            clarification_type=str(jurisdiction_resolution.get("clarification_type") or "address_missing_details"),
            confidence=0.9,
        ),
        "needs_address_clarification": True,
        "clarification_prompt": jurisdiction_resolution.get("clarification_prompt")
        or missing_address_details_message(),
        "clarification_candidates": jurisdiction_resolution.get("clarification_candidates") or [],
        "jurisdiction_resolution": jurisdiction_resolution,
        "confidence_band": "needs_verification",
        "detected_address": resolution.detected_address,
        "routing_reason": routing_reason,
        "request_classification": _request_classification_payload("specific_address", routing_reason),
        "address_context": _specific_address_context_payload(resolution),
        "address_resolution": _address_resolution_payload(resolution),
        "follow_up_context": _follow_up_context_payload(
            question_type="specific_address",
            standardized_address=resolution.standardized_address,
            state_code=resolution.state_code,
            zip_code=resolution.zip_code,
            zoning_summary=None,
        ),
    }


def _jurisdiction_block_response(
    *,
    question: str,
    resolution: _ResolvedAddress,
    zoning_summary: dict[str, Any],
    policy_decision: dict[str, Any],
    jurisdiction_resolution: dict[str, Any],
) -> dict[str, Any]:
    return {
        "question_type": "specific_address",
        "policy_decision": policy_decision,
        "assistant_turn": _assistant_turn_payload(
            intent_type="specific_address",
            policy_decision=policy_decision,
            jurisdiction_status=str(jurisdiction_resolution.get("jurisdiction_status") or "out_of_jurisdiction"),
            needs_clarification=True,
            clarification_type=str(jurisdiction_resolution.get("clarification_type") or "jurisdiction_mismatch"),
            confidence=0.95,
        ),
        "jurisdiction_resolution": jurisdiction_resolution,
        "request_classification": _request_classification_payload(
            "specific_address",
            "Property question detected but blocked by jurisdiction guardrail.",
        ),
        "address_context": _specific_address_context_payload(resolution),
        "address_resolution": _address_resolution_payload(resolution),
        "follow_up_context": _follow_up_context_payload(
            question_type="specific_address",
            standardized_address=resolution.standardized_address,
            state_code=resolution.state_code,
            zip_code=resolution.zip_code,
            zoning_summary=zoning_summary,
        ),
        "response_guardrail": {
            "message": jurisdiction_resolution.get("clarification_prompt") or policy_decision["reason"]
        },
        "confidence_band": "needs_verification",
    }


def _property_insufficient_evidence_response(
    *,
    resolution: _ResolvedAddress,
    zoning_summary: dict[str, Any],
    policy_decision: dict[str, Any],
    jurisdiction_resolution: dict[str, Any],
    routing_reason: str,
    request_reason: str,
    evidence_pack: list[dict[str, str]],
    source_references: list[dict[str, str]],
    grounding: dict[str, Any],
    citation_check: dict[str, Any],
) -> dict[str, Any]:
    return {
        "question_type": "specific_address",
        "routing_reason": routing_reason,
        "policy_decision": policy_decision,
        "assistant_turn": _assistant_turn_payload(
            intent_type="specific_address",
            policy_decision=policy_decision,
            jurisdiction_status=str(jurisdiction_resolution.get("jurisdiction_status") or "in_jurisdiction"),
            needs_clarification=True,
            clarification_type="scope",
            confidence=0.7,
        ),
        "jurisdiction_resolution": jurisdiction_resolution,
        "request_classification": _request_classification_payload("specific_address", request_reason),
        "address_context": _specific_address_context_payload(resolution),
        "address_resolution": _address_resolution_payload(resolution),
        "follow_up_context": _follow_up_context_payload(
            question_type="specific_address",
            standardized_address=resolution.standardized_address,
            state_code=resolution.state_code,
            zip_code=resolution.zip_code,
            zoning_summary=zoning_summary,
        ),
        "gridics": zoning_summary,
        "evidence_pack": evidence_pack,
        "source_references": source_references,
        "grounding": grounding,
        "citation_check": citation_check,
        "response_guardrail": {
            "message": insufficient_evidence_message(has_property_context=True)
        },
        "confidence_band": "needs_verification",
    }


def _property_success_response(
    *,
    resolution: _ResolvedAddress,
    zoning_summary: dict[str, Any],
    policy_decision: dict[str, Any],
    jurisdiction_resolution: dict[str, Any],
    routing_reason: str,
    request_reason: str,
    memo_context: dict[str, Any],
    primary_knowledge: dict[str, Any],
    evidence_pack: list[dict[str, str]],
    source_references: list[dict[str, str]],
    grounding: dict[str, Any],
    citation_check: dict[str, Any],
    cleaned_primary_knowledge: list[dict[str, Any]],
    constraints_knowledge: dict[str, Any] | None,
    uses_knowledge: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "question_type": "specific_address",
        "routing_reason": routing_reason,
        "policy_decision": policy_decision,
        "assistant_turn": _assistant_turn_payload(
            intent_type="specific_address",
            policy_decision=policy_decision,
            jurisdiction_status=str(jurisdiction_resolution.get("jurisdiction_status") or "in_jurisdiction"),
            confidence=0.9,
        ),
        "jurisdiction_resolution": jurisdiction_resolution,
        "request_classification": _request_classification_payload("specific_address", request_reason),
        "address_context": _specific_address_context_payload(resolution),
        "address_resolution": _address_resolution_payload(resolution),
        "follow_up_context": _follow_up_context_payload(
            question_type="specific_address",
            standardized_address=resolution.standardized_address,
            state_code=resolution.state_code,
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
            "story_equivalent": memo_context["story_equivalent"],
        },
        "dimensional_standards": memo_context["dimensional_standards"],
        "critical_notes": memo_context["gridics_system_notes"],
        "story_equivalent": memo_context["story_equivalent"],
        "knowledge": primary_knowledge,
        "evidence_pack": evidence_pack,
        "source_references": source_references,
        "grounding": grounding,
        "citation_check": citation_check,
        "confidence_band": _confidence_band(grounding=grounding, citation_check=citation_check),
        "regulatory_knowledge": cleaned_primary_knowledge,
        "constraints_knowledge": {"results": _clean_knowledge_results(constraints_knowledge)} if constraints_knowledge else None,
        "uses_knowledge": {"results": _clean_knowledge_results(uses_knowledge)},
        "agent_directives": memo_context["agent_directives"],
    }


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
    from app.services.agentic.zoning_knowledge_service import query_customer_zoning_knowledge

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
    tenant_client: Any,
) -> dict[str, Any]:
    question = query.strip()

    if resolution.question_type == "general_zoning":
        return _general_zoning_response(
            question=question,
            knowledge_limit=knowledge_limit,
            resolved_client_id=resolved_client_id,
            tenant_client=tenant_client,
        )

    if resolution.confirmation_state == "clarify":
        return _pending_confirmation_response(
            question=question,
            resolution=resolution,
            tenant_client=tenant_client,
        )

    if not resolution.lookup_ready:
        return _missing_lookup_details_response(
            question=question,
            resolution=resolution,
            tenant_client=tenant_client,
        )

    client = gridics_client or _build_gridics_client()
    gridics_lookup_address = resolution.standardized_address or ""
    if resolution.latitude is not None and resolution.longitude is not None:
        property_record = client.get_property_record_by_coordinates(
            latitude=resolution.latitude,
            longitude=resolution.longitude,
        )
    else:
        property_record = client.get_property_record(
            state_code=resolution.state_code or "",
            address=gridics_lookup_address,
            zip_code=resolution.zip_code or None,
        )
    zoning_summary = _extract_gridics_zoning_summary(property_record)

    policy_decision = evaluate_policy_decision(
        query=question,
        question_type="specific_address",
        tenant_client=tenant_client,
        resolved_city=str(zoning_summary.get("resolved_city") or ""),
        resolved_state=str(zoning_summary.get("resolved_state") or ""),
    )
    jurisdiction_resolution = resolve_jurisdiction_for_property_request(
        tenant_client=tenant_client,
        standardized_address=resolution.standardized_address,
        lookup_ready=True,
        resolved_city=str(zoning_summary.get("resolved_city") or ""),
        resolved_state=str(zoning_summary.get("resolved_state") or ""),
    )
    lock = _get_jurisdiction_lock(run_context)
    if lock and lock.get("state") and str(lock.get("state")).lower() != str(zoning_summary.get("resolved_state") or "").lower():
        jurisdiction_resolution = {
            "jurisdiction_status": "out_of_jurisdiction",
            "is_ambiguous": False,
            "clarification_type": "jurisdiction_mismatch",
            "clarification_prompt": jurisdiction_lock_message(
                locked_label=str(lock.get("label") or "current jurisdiction")
            ),
            "clarification_candidates": [],
        }
    if policy_decision["decision"] == "deny" or jurisdiction_resolution.get("jurisdiction_status") == "out_of_jurisdiction":
        return _jurisdiction_block_response(
            question=question,
            resolution=resolution,
            zoning_summary=zoning_summary,
            policy_decision=policy_decision,
            jurisdiction_resolution=jurisdiction_resolution,
        )

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
    if not cleaned_primary_knowledge:
        constraints_knowledge = query_customer_zoning_code(
            query=_build_constraints_knowledge_query(
                query=question,
                standardized_address=resolution.standardized_address or "",
                zoning_summary=zoning_summary,
            ),
            limit=knowledge_limit,
            client_id=resolved_client_id,
        )

    uses_knowledge = None
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
    evidence_pack = build_evidence_pack(primary_knowledge, constraints_knowledge, uses_knowledge)
    source_references = _build_source_references(evidence_pack)
    grounding = grounding_verdict(evidence_pack, min_refs=1)
    citation_check = citation_completeness_report(
        evidence_pack=evidence_pack,
        knowledge_payloads=[primary_knowledge, constraints_knowledge, uses_knowledge],
    )
    has_any_knowledge = bool(cleaned_primary_knowledge) or bool(_clean_knowledge_results(constraints_knowledge)) or bool(
        _clean_knowledge_results(uses_knowledge)
    )
    if not grounding["answer_ready"] and not has_any_knowledge:
        return _property_insufficient_evidence_response(
            resolution=resolution,
            zoning_summary=zoning_summary,
            policy_decision=policy_decision,
            jurisdiction_resolution=jurisdiction_resolution,
            routing_reason=routing_reason,
            request_reason=request_reason,
            evidence_pack=evidence_pack,
            source_references=source_references,
            grounding=grounding,
            citation_check=citation_check,
        )

    _set_active_property_context(
        run_context,
        standardized_address=resolution.standardized_address or "",
        state_code=resolution.state_code,
        zip_code=resolution.zip_code or "",
        zoning_summary=zoning_summary,
        latitude=resolution.latitude,
        longitude=resolution.longitude,
    )
    _set_jurisdiction_lock(
        run_context,
        tenant_client=tenant_client,
        resolved_city=str(zoning_summary.get("resolved_city") or ""),
        resolved_state=str(zoning_summary.get("resolved_state") or ""),
    )

    memo_context = _build_memo_context(
        standardized_address=resolution.standardized_address or "",
        state_code=resolution.state_code,
        zip_code=resolution.zip_code or "",
        zoning_summary=zoning_summary,
        sources=source_references,
    )
    _clear_pending_property_confirmation(run_context)

    return _property_success_response(
        resolution=resolution,
        zoning_summary=zoning_summary,
        policy_decision=policy_decision,
        jurisdiction_resolution=jurisdiction_resolution,
        routing_reason=routing_reason,
        request_reason=request_reason,
        memo_context=memo_context,
        primary_knowledge=primary_knowledge,
        evidence_pack=evidence_pack,
        source_references=source_references,
        grounding=grounding,
        citation_check=citation_check,
        cleaned_primary_knowledge=cleaned_primary_knowledge,
        constraints_knowledge=constraints_knowledge,
        uses_knowledge=uses_knowledge,
    )


def analyze_customer_zoning_request(
    query: str | None = None,
    address: str | None = None,
    state_code: str | None = None,
    zip_code: str | int | None = None,
    latitude: float | int | str | None = None,
    longitude: float | int | str | None = None,
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

    effective_query = str(query or "").strip()
    if not effective_query:
        effective_query = f"What are the zoning rules for {address}?" if address else "What are the zoning rules for this property?"

    for attempt in range(1, _ANALYZE_RETRY_ATTEMPTS + 1):
        stage = "initializing"
        resolved_client_id: str | None = None
        resolution: _ResolvedAddress | None = None
        client: _GridicsClient | None = None

        try:
            stage = "resolving_client_id"
            resolved_client_id = _resolve_client_id(client_id, run_context)
            tenant_client = _load_tenant_client(resolved_client_id)

            resolution = _resolve_address_context(
                query=effective_query,
                address=address,
                state_code=state_code,
                zip_code=zip_code,
                latitude=latitude,
                longitude=longitude,
                run_context=run_context,
                tenant_client=tenant_client,
            )

            if resolution.question_type == "specific_address" and resolution.lookup_ready:
                client = _build_gridics_client()

            stage = "analyzing_request"
            result = _analyze_customer_zoning_request_once(
                query=effective_query,
                knowledge_limit=knowledge_limit,
                resolved_client_id=resolved_client_id,
                resolution=resolution,
                run_context=run_context,
                gridics_client=client,
                tenant_client=tenant_client,
            )

            if failures:
                result["retry_debug"] = {
                    "recovered": True,
                    "attempts": attempt,
                    "failed_attempts": failures,
                }

            metadata = getattr(run_context, "metadata", None)
            if not isinstance(metadata, dict):
                metadata = {}
            result["conversation_id"] = str(
                metadata.get("conversation_id")
                or metadata.get("session_id")
                or metadata.get("thread_id")
                or ""
            ) or None
            result["message_id"] = str(metadata.get("message_id") or "") or None
            result["run_id"] = str(metadata.get("run_id") or "") or None
            result["agent_id"] = "customer-zoning-agent"

            return result

        except Exception as exc:
            failure = _summarize_attempt_failure(
                attempt=attempt,
                stage=stage,
                error=exc,
                query=effective_query,
                client_id=resolved_client_id,
                question_type=resolution.question_type if resolution else None,
                address_context=(
                    {
                        "address_source": resolution.address_source,
                        "detected_address": resolution.detected_address,
                        "standardized_address": resolution.standardized_address,
                        "state_code": resolution.state_code,
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
