"""Tenant resolution and cached public configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Jurisdiction, JurisdictionHomePageContent, TenantClient, TenantDomain
from app.agents.assistant_defaults import ASSISTANT_TARGET_ID_ALIASES
from app.services.cache_service import get_cache_service


@dataclass(slots=True)
class TenantPublicConfig:
    client_id: str
    clerk_organization_id: str | None
    city_name: str
    department_name: str
    public_site_title: str | None
    path_alias: str | None
    logo_path: str | None
    standard_letter_fee_cents: int
    comprehensive_letter_fee_cents: int
    expedited_fee_cents: int
    support_phone: str | None
    support_email: str | None
    contact_address: str | None
    jurisdiction_id: str | None
    agent_url: str | None
    zoning_code_url: str | None
    market: str | None
    assistant_disclaimer_text: str
    home_page_content: dict
    surface_configs: dict[str, dict]


AGENT_URL_SETTING_KEY = "agent_url"
ZONING_CODE_URL_SETTING_KEY = "zoning_code_url"
MARKET_SETTING_KEY = "market"
SURFACE_CONFIGS_SETTING_KEY = "surface_configs"
HEADER_LOGO_PATH_SETTING_KEY = "header_logo_path"
PATH_ALIAS_SETTING_KEY = "path_alias"
ASSISTANT_PROVIDER_KEYS_SETTING_KEY = "assistant_provider_keys"
ASSISTANT_MODEL_TARGETS_SETTING_KEY = "assistant_model_targets"
ASSISTANT_AGENT_PROMPTS_SETTING_KEY = "assistant_agent_prompts"
ASSISTANT_DISCLAIMER_TEXT_SETTING_KEY = "assistant_disclaimer_text"
SUPPORTED_ASSISTANT_PROVIDERS = ("gemini", "openrouter", "openai", "groq")
DEFAULT_ASSISTANT_DISCLAIMER_TEXT = (
    "This AI assistant may make mistakes. Please verify important zoning, permitting, and code "
    "information with official jurisdiction staff, adopted ordinances, and other authoritative sources "
    "before relying on it."
)
RESERVED_PUBLIC_PATH_SEGMENTS = {
    "_next",
    "_internal",
    "api",
    "account",
    "admin",
    "assistant",
    "request",
    "requests",
    "staff",
    "super-admin",
    "select-jurisdiction",
}

SurfaceName = Literal["assistant", "letters"]


def _normalize_assistant_provider_keys(value: object) -> dict[str, str | None]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str | None] = {}
    for provider in SUPPORTED_ASSISTANT_PROVIDERS:
        raw = value.get(provider)
        if isinstance(raw, str):
            stripped = raw.strip()
            normalized[provider] = stripped or None
        elif raw is None:
            normalized[provider] = None
    return normalized


def _normalize_assistant_target_id(target_id: str) -> str:
    return ASSISTANT_TARGET_ID_ALIASES.get(target_id, target_id)


def _normalize_assistant_model_provider(provider: object) -> str | None:
    if not isinstance(provider, str):
        return None
    normalized = provider.strip().lower()
    if normalized == "gemini":
        return "gemini"
    return None


def _normalize_assistant_model_targets(value: object) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, dict[str, str | None]] = {}
    for target_id, raw_target in value.items():
        if not isinstance(target_id, str) or not isinstance(raw_target, dict):
            continue
        canonical_target_id = _normalize_assistant_target_id(target_id)
        if target_id != canonical_target_id and canonical_target_id in normalized:
            continue
        provider = _normalize_assistant_model_provider(raw_target.get("provider"))
        if isinstance(raw_target.get("provider"), str) and raw_target.get("provider").strip() and provider is None:
            continue
        model_id = raw_target.get("model_id")
        base_url = raw_target.get("base_url")
        normalized[canonical_target_id] = {
            "provider": provider,
            "model_id": model_id.strip() if isinstance(model_id, str) and model_id.strip() else None,
            "base_url": base_url.strip() if isinstance(base_url, str) and base_url.strip() else None,
        }
    return normalized


def _normalize_assistant_agent_prompts(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for target_id, raw_prompt in value.items():
        if not isinstance(target_id, str):
            continue
        canonical_target_id = _normalize_assistant_target_id(target_id)
        if target_id != canonical_target_id and canonical_target_id in normalized:
            continue
        if not isinstance(raw_prompt, str):
            continue
        prompt = raw_prompt.strip()
        if prompt:
            normalized[canonical_target_id] = prompt
    return normalized

def normalize_hostname(host: str | None) -> str | None:
    if not host:
        return None
    return host.split(":", 1)[0].strip().lower() or None


def _cache_key(*, host: str | None, client_id: str | None, organization_id: str | None = None) -> str:
    if client_id:
        return f"client:{client_id.lower()}"
    if organization_id:
        return f"org:{organization_id.lower()}"
    if host:
        return f"host:{host.lower()}"
    return "default"


def invalidate_tenant_cache() -> None:
    get_cache_service().delete_prefix("tenant-public:")


def get_tenant_experience_settings(settings_json: dict | None) -> tuple[str | None, str | None]:
    if not isinstance(settings_json, dict):
        return None, None

    agent_url = settings_json.get(AGENT_URL_SETTING_KEY)
    zoning_code_url = settings_json.get(ZONING_CODE_URL_SETTING_KEY)
    return (
        agent_url if isinstance(agent_url, str) and agent_url.strip() else None,
        zoning_code_url if isinstance(zoning_code_url, str) and zoning_code_url.strip() else None,
    )


def get_tenant_market(settings_json: dict | None) -> str | None:
    if not isinstance(settings_json, dict):
        return None

    raw_market = settings_json.get(MARKET_SETTING_KEY)
    if not isinstance(raw_market, str):
        return None

    market = raw_market.strip()
    return market or None


def get_tenant_logo_path(settings_json: dict | None) -> str | None:
    if not isinstance(settings_json, dict):
        return None

    logo_path = settings_json.get(HEADER_LOGO_PATH_SETTING_KEY)
    return logo_path if isinstance(logo_path, str) and logo_path.strip() else None


def normalize_tenant_path_alias(value: str | None) -> str | None:
    if not value:
        return None

    parts = [part.strip().lower() for part in value.split("/") if part.strip()]
    if not parts:
        return None
    if parts[0] in RESERVED_PUBLIC_PATH_SEGMENTS:
        raise ValueError(f"The alias cannot start with '/{parts[0]}'.")
    return "/" + "/".join(parts)


def get_tenant_path_alias(settings_json: dict | None) -> str | None:
    if not isinstance(settings_json, dict):
        return None

    raw_alias = settings_json.get(PATH_ALIAS_SETTING_KEY)
    if not isinstance(raw_alias, str):
        return None
    try:
        return normalize_tenant_path_alias(raw_alias)
    except ValueError:
        return None


def merge_tenant_branding_settings(existing_settings: dict | None, *, logo_path: str | None) -> dict:
    next_settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}

    if logo_path:
        next_settings[HEADER_LOGO_PATH_SETTING_KEY] = logo_path
    else:
        next_settings.pop(HEADER_LOGO_PATH_SETTING_KEY, None)

    return next_settings


def merge_tenant_path_alias_settings(existing_settings: dict | None, *, path_alias: str | None) -> dict:
    next_settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}

    if path_alias:
        next_settings[PATH_ALIAS_SETTING_KEY] = path_alias
    else:
        next_settings.pop(PATH_ALIAS_SETTING_KEY, None)

    return next_settings


def merge_tenant_market_settings(existing_settings: dict | None, *, market: str | None) -> dict:
    next_settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}

    if market:
        next_settings[MARKET_SETTING_KEY] = market.strip()
    else:
        next_settings.pop(MARKET_SETTING_KEY, None)

    return next_settings


def get_tenant_assistant_settings(
    settings_json: dict | None,
) -> tuple[dict[str, str | None], dict[str, dict[str, str | None]]]:
    if not isinstance(settings_json, dict):
        return (
            {provider: None for provider in SUPPORTED_ASSISTANT_PROVIDERS},
            {},
        )

    provider_keys = _normalize_assistant_provider_keys(settings_json.get(ASSISTANT_PROVIDER_KEYS_SETTING_KEY))
    for provider in SUPPORTED_ASSISTANT_PROVIDERS:
        provider_keys.setdefault(provider, None)
    model_targets = _normalize_assistant_model_targets(settings_json.get(ASSISTANT_MODEL_TARGETS_SETTING_KEY))
    return provider_keys, model_targets


def get_tenant_assistant_agent_prompts(settings_json: dict | None) -> dict[str, str]:
    if not isinstance(settings_json, dict):
        return {}

    return _normalize_assistant_agent_prompts(settings_json.get(ASSISTANT_AGENT_PROMPTS_SETTING_KEY))


def merge_assistant_provider_keys(
    baseline: dict[str, str | None],
    overrides: dict[str, str | None],
) -> dict[str, str | None]:
    merged = {provider: baseline.get(provider) for provider in SUPPORTED_ASSISTANT_PROVIDERS}
    for provider, value in overrides.items():
        if provider in SUPPORTED_ASSISTANT_PROVIDERS and value:
            merged[provider] = value
    return merged


def merge_assistant_model_targets(
    baseline: dict[str, dict[str, str | None]],
    overrides: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, str | None]]:
    merged: dict[str, dict[str, str | None]] = {
        target_id: {
            "provider": target.get("provider"),
            "model_id": target.get("model_id"),
            "base_url": target.get("base_url"),
        }
        for target_id, target in baseline.items()
    }

    for target_id, override in overrides.items():
        current = merged.get(target_id, {"provider": None, "model_id": None, "base_url": None})
        merged[target_id] = {
            "provider": override.get("provider") or current.get("provider"),
            "model_id": override.get("model_id") or current.get("model_id"),
            "base_url": override.get("base_url") or current.get("base_url"),
        }

    return merged


def merge_assistant_agent_prompts(
    baseline: dict[str, str],
    overrides: dict[str, str],
) -> dict[str, str]:
    return {**baseline, **overrides}


def get_effective_assistant_disclaimer_text(
    platform_settings_json: dict | None,
    tenant_settings_json: dict | None,
) -> str:
    tenant_text = get_tenant_assistant_disclaimer_text(tenant_settings_json)
    platform_text = get_tenant_assistant_disclaimer_text(platform_settings_json)

    if (
        isinstance(tenant_settings_json, dict)
        and tenant_settings_json.get(ASSISTANT_DISCLAIMER_TEXT_SETTING_KEY)
    ):
        return tenant_text
    if (
        isinstance(platform_settings_json, dict)
        and platform_settings_json.get(ASSISTANT_DISCLAIMER_TEXT_SETTING_KEY)
    ):
        return platform_text
    return DEFAULT_ASSISTANT_DISCLAIMER_TEXT


def get_tenant_assistant_disclaimer_text(settings_json: dict | None) -> str:
    if not isinstance(settings_json, dict):
        return DEFAULT_ASSISTANT_DISCLAIMER_TEXT

    disclaimer_text = settings_json.get(ASSISTANT_DISCLAIMER_TEXT_SETTING_KEY)
    if not isinstance(disclaimer_text, str) or not disclaimer_text.strip():
        return DEFAULT_ASSISTANT_DISCLAIMER_TEXT

    return disclaimer_text.strip()


def merge_tenant_experience_settings(
    existing_settings: dict | None,
    *,
    agent_url: str | None,
    zoning_code_url: str | None,
    assistant_disclaimer_text: str | None = None,
    assistant_provider_keys: dict[str, str | None] | None = None,
    assistant_model_targets: dict[str, dict[str, str | None]] | None = None,
    assistant_agent_prompts: dict[str, str | None] | None = None,
) -> dict:
    next_settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}

    if agent_url:
        next_settings[AGENT_URL_SETTING_KEY] = agent_url
    else:
        next_settings.pop(AGENT_URL_SETTING_KEY, None)

    if zoning_code_url:
        next_settings[ZONING_CODE_URL_SETTING_KEY] = zoning_code_url
    else:
        next_settings.pop(ZONING_CODE_URL_SETTING_KEY, None)

    if assistant_disclaimer_text:
        next_settings[ASSISTANT_DISCLAIMER_TEXT_SETTING_KEY] = assistant_disclaimer_text.strip()
    else:
        next_settings.pop(ASSISTANT_DISCLAIMER_TEXT_SETTING_KEY, None)

    if assistant_provider_keys is not None:
        normalized_provider_keys = _normalize_assistant_provider_keys(assistant_provider_keys)
        if any(value for value in normalized_provider_keys.values()):
            next_settings[ASSISTANT_PROVIDER_KEYS_SETTING_KEY] = normalized_provider_keys
        else:
            next_settings.pop(ASSISTANT_PROVIDER_KEYS_SETTING_KEY, None)

    if assistant_model_targets is not None:
        normalized_model_targets = _normalize_assistant_model_targets(assistant_model_targets)
        if any(
            target.get("provider") or target.get("model_id") or target.get("base_url")
            for target in normalized_model_targets.values()
        ):
            next_settings[ASSISTANT_MODEL_TARGETS_SETTING_KEY] = normalized_model_targets
        else:
            next_settings.pop(ASSISTANT_MODEL_TARGETS_SETTING_KEY, None)

    if assistant_agent_prompts is not None:
        normalized_agent_prompts = _normalize_assistant_agent_prompts(assistant_agent_prompts)
        if normalized_agent_prompts:
            next_settings[ASSISTANT_AGENT_PROMPTS_SETTING_KEY] = normalized_agent_prompts
        else:
            next_settings.pop(ASSISTANT_AGENT_PROMPTS_SETTING_KEY, None)

    return next_settings


def build_default_home_page_content(client: TenantClient, *, surface: SurfaceName = "letters") -> dict:
    city_name = client.city_name.strip() or "Your City"
    department_name = client.department_name.strip() or "Planning & Zoning Department"
    support_email = client.support_email.strip() if client.support_email else None
    support_phone = client.support_phone.strip() if client.support_phone else None
    contact_address = client.contact_address.strip() if client.contact_address else None

    if surface == "assistant":
        return {
            "hero": {
                "badge": "Gridics Agentic Assistant",
                "title": f"Welcome to the {city_name} Assistant",
                "subtitle": (
                    f"Ask questions, research zoning code, and work through {department_name.lower()} "
                    "guidance through a modern AI experience."
                ),
                "primary_button_text": "Open Assistant",
                "secondary_button_text": "Choose Jurisdiction",
                "learn_more_text": "How It Works",
                "stats": [
                    {"label": "Mode", "value": "Jurisdiction Aware", "icon": "◔"},
                    {"label": "Answers", "value": "Grounded in Code", "icon": "◈"},
                    {"label": "Coverage", "value": "Market-Specific", "icon": "◉"},
                ],
            },
            "services": [
                {
                    "id": "assistant-qa",
                    "title": "Ask a Question",
                    "description": "Get fast answers about zoning, permitted uses, and next steps.",
                    "processing_time": "Instant",
                    "fee": "Included",
                },
                {
                    "id": "assistant-code",
                    "title": "Review Code",
                    "description": "See citations and code references tied to the current jurisdiction.",
                    "processing_time": "Instant",
                    "fee": "Included",
                },
                {
                    "id": "assistant-handoff",
                    "title": "Escalate to Staff",
                    "description": "When needed, use the assistant to prepare a clean handoff for staff review.",
                    "processing_time": "As needed",
                    "fee": "Included",
                },
            ],
            "about": {
                "title": "What can the assistant help with?",
                "body": (
                    f"The {city_name} assistant helps residents, staff, and external users ask better "
                    "zoning questions and find cited answers faster."
                ),
            },
            "faq": [
                {
                    "id": "assistant-market",
                    "question": "How does the assistant know which market this belongs to?",
                    "answer": (
                        "The jurisdiction is tagged with a market so the assistant can scope answers "
                        "to the right Gridics market."
                    ),
                },
                {
                    "id": "assistant-citations",
                    "question": "Will responses include citations?",
                    "answer": "Yes. The assistant is designed to return source-backed answers whenever possible.",
                },
                {
                    "id": "assistant-support",
                    "question": "What if the assistant is unsure?",
                    "answer": "It should explain the gap and guide the user toward staff review or better context.",
                },
            ],
            "contact": {
                "title": "Need help using the assistant?",
                "body": (
                    f"Contact the {department_name} if you need help with assistant access, market setup, "
                    "or jurisdiction-specific guidance."
                ),
                "email": support_email,
                "phone": support_phone,
                "address": contact_address,
            },
        }

    return {
        "hero": {
            "badge": "Official City Documentation",
            "title": f"Welcome to the {city_name}",
            "subtitle": (
                f"Request zoning verification letters and access {department_name.lower()} "
                "services through a modern online portal."
            ),
            "primary_button_text": "Request a Letter",
            "secondary_button_text": "Ask the Zoning Assistant",
            "learn_more_text": "Learn More",
            "stats": [
                {"label": "Processing Time", "value": "Under 3 Days", "icon": "◔"},
                {"label": "Security", "value": "PCI Compliant", "icon": "◈"},
                {"label": "Updates", "value": "Real-Time Tracking", "icon": "◉"},
            ],
        },
        "services": [
            {
                "id": "zoning-verification-letters",
                "title": "Zoning Verification Letters",
                "description": "Official documentation for property zoning classifications and permitted uses.",
                "processing_time": "2-3 business days",
                "fee": "Varies by request",
            },
            {
                "id": "building-permits",
                "title": "Building Permits",
                "description": "Permits for construction, renovation, and property modifications.",
                "processing_time": "5-10 business days",
                "fee": "Varies by project",
            },
            {
                "id": "business-licenses",
                "title": "Business Licenses",
                "description": "Licensing for new and existing business operations within city limits.",
                "processing_time": "3-5 business days",
                "fee": "See fee schedule",
            },
        ],
        "about": {
            "title": "What is a Zoning Verification Letter?",
            "body": (
                f"An official document from the {city_name} {department_name} that confirms "
                "zoning classification, permitted uses, and related property details."
            ),
        },
        "faq": [
            {
                "id": "turnaround",
                "question": "How long does it take to receive my letter?",
                "answer": (
                    "Standard processing typically takes fewer than 3 business days. "
                    "Expedited processing may be available for an additional fee."
                ),
            },
            {
                "id": "payment-methods",
                "question": "What payment methods are accepted?",
                "answer": "We accept major credit cards through a secure online checkout flow.",
            },
            {
                "id": "delivery",
                "question": "How will I receive my zoning verification letter?",
                "answer": "Approved letters are typically delivered digitally, with mail options when configured.",
            },
        ],
        "contact": {
            "title": "Need help with your request?",
            "body": (
                f"Contact the {department_name} if you need assistance with zoning letters, "
                "application status, or related municipal services."
            ),
            "email": support_email,
            "phone": support_phone,
            "address": contact_address,
        },
    }


def build_default_surface_rules(client: TenantClient, *, surface: SurfaceName) -> list[str]:
    if surface == "assistant":
        return [
            "Use the assistant for jurisdiction-aware zoning questions tied to the current market.",
            "If a question does not apply to the active market, say so before answering.",
            "Prefer source-backed answers and cite code or policy references when available.",
        ]

    city_name = client.city_name.strip() or "Your City"
    return [
        f"Use the {city_name} letters workflow for zoning verification requests and property lookups.",
        "Keep the request focused on the selected jurisdiction.",
        "Use the public request flow for official letter generation and tracking.",
    ]


def build_default_surface_config(client: TenantClient, *, surface: SurfaceName) -> dict:
    return {
        "home_page_content": build_default_home_page_content(client, surface=surface),
        "rules": build_default_surface_rules(client, surface=surface),
    }


def _normalize_surface_config(value: object, *, client: TenantClient, surface: SurfaceName) -> dict:
    default_config = build_default_surface_config(client, surface=surface)
    if not isinstance(value, dict):
        return default_config

    home_page_content = value.get("home_page_content")
    rules = value.get("rules")
    next_config = {
        "home_page_content": default_config["home_page_content"],
        "rules": default_config["rules"],
    }
    if isinstance(home_page_content, dict):
        next_config["home_page_content"] = home_page_content
    if isinstance(rules, list):
        next_config["rules"] = [item.strip() for item in rules if isinstance(item, str) and item.strip()]
    return next_config


def get_tenant_surface_configs(settings_json: dict | None, client: TenantClient) -> dict[str, dict]:
    default_configs: dict[str, dict] = {
        "assistant": build_default_surface_config(client, surface="assistant"),
        "letters": build_default_surface_config(client, surface="letters"),
    }
    if not isinstance(settings_json, dict):
        return default_configs

    raw_configs = settings_json.get(SURFACE_CONFIGS_SETTING_KEY)
    if not isinstance(raw_configs, dict):
        return default_configs

    return {
        "assistant": _normalize_surface_config(raw_configs.get("assistant"), client=client, surface="assistant"),
        "letters": _normalize_surface_config(raw_configs.get("letters"), client=client, surface="letters"),
    }


def get_home_page_content_payload(
    record: JurisdictionHomePageContent | None,
    client: TenantClient,
) -> dict:
    if record is None:
        return build_default_home_page_content(client)

    return {
        "hero": dict(record.hero_json or {}),
        "services": list(record.services_json or []),
        "about": dict(record.about_json or {}),
        "faq": list(record.faq_json or []),
        "contact": dict(record.contact_json or {}),
    }


def get_home_page_content_record(
    db: Session,
    jurisdiction_id: str | None,
) -> JurisdictionHomePageContent | None:
    if not jurisdiction_id:
        return None

    try:
        return db.scalar(
            select(JurisdictionHomePageContent).where(
                JurisdictionHomePageContent.jurisdiction_id == jurisdiction_id
            )
        )
    except ProgrammingError as exc:
        # Allow environments that have the code deployed before the new migration runs
        # to fall back to generated default content instead of returning a 500.
        if "shared_jurisdiction_home_page_content" in str(exc):
            db.rollback()
            return None
        raise


def has_home_page_content_storage(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and inspect(bind).has_table("shared_jurisdiction_home_page_content"))


def _to_public_config(
    db: Session,
    client: TenantClient,
) -> TenantPublicConfig:
    from app.services.platform_settings_service import get_platform_assistant_settings_json

    agent_url, zoning_code_url = get_tenant_experience_settings(client.settings_json)
    home_page_content_record = get_home_page_content_record(db, client.jurisdiction_id)
    platform_settings_json = get_platform_assistant_settings_json(db)
    jurisdiction_public_site_title = None
    if client.jurisdiction_id:
        jurisdiction = db.get(Jurisdiction, client.jurisdiction_id)
        if jurisdiction is not None and isinstance(jurisdiction.public_site_title, str):
            site_title = jurisdiction.public_site_title.strip()
            jurisdiction_public_site_title = site_title or None
    return TenantPublicConfig(
        client_id=client.client_id,
        clerk_organization_id=client.clerk_organization_id,
        city_name=client.city_name,
        department_name=client.department_name,
        public_site_title=jurisdiction_public_site_title,
        path_alias=get_tenant_path_alias(client.settings_json),
        logo_path=get_tenant_logo_path(client.settings_json),
        standard_letter_fee_cents=client.standard_letter_fee_cents,
        comprehensive_letter_fee_cents=client.comprehensive_letter_fee_cents,
        expedited_fee_cents=client.expedited_fee_cents,
        support_phone=client.support_phone,
        support_email=client.support_email,
        contact_address=client.contact_address,
        jurisdiction_id=client.jurisdiction_id,
        agent_url=agent_url,
        zoning_code_url=zoning_code_url,
        market=get_tenant_market(client.settings_json),
        assistant_disclaimer_text=get_effective_assistant_disclaimer_text(platform_settings_json, client.settings_json),
        home_page_content=get_home_page_content_payload(home_page_content_record, client),
        surface_configs=get_tenant_surface_configs(client.settings_json, client),
    )


def resolve_tenant_public_config(
    db: Session,
    *,
    host: str | None = None,
    client_id: str | None = None,
    organization_id: str | None = None,
    path_alias: str | None = None,
) -> TenantPublicConfig | None:
    normalized_host = normalize_hostname(host)
    normalized_client_id = client_id.strip().lower() if client_id else None
    normalized_organization_id = organization_id.strip() if organization_id else None
    normalized_path_alias = normalize_tenant_path_alias(path_alias) if path_alias else None
    cache_key_value = (
        f"alias:{normalized_path_alias.lower()}"
        if normalized_path_alias
        else _cache_key(host=normalized_host, client_id=normalized_client_id, organization_id=normalized_organization_id)
    )
    key = f"tenant-public:{cache_key_value}"
    cache = get_cache_service()
    cached = cache.get_json(key)
    if cached is not cache.cache_miss:
        if cached is None:
            return None
        try:
            return TenantPublicConfig(**cached)
        except TypeError:
            cache.delete(key)

    client: TenantClient | None = None
    if normalized_client_id:
        client = db.scalar(
            select(TenantClient).where(
                func.lower(TenantClient.client_id) == normalized_client_id,
                TenantClient.is_active.is_(True),
            )
        )
    elif normalized_organization_id:
        normalized_organization_id_lower = normalized_organization_id.lower()
        client = db.scalar(
            select(TenantClient).where(
                (func.lower(TenantClient.clerk_organization_id) == normalized_organization_id_lower)
                | (func.lower(TenantClient.client_id) == normalized_organization_id_lower),
                TenantClient.is_active.is_(True),
            )
        )
    elif normalized_path_alias:
        candidates = db.scalars(
            select(TenantClient).where(TenantClient.is_active.is_(True))
        ).all()
        client = next(
            (
                candidate
                for candidate in candidates
                if get_tenant_path_alias(candidate.settings_json) == normalized_path_alias
            ),
            None,
        )
    elif normalized_host:
        client = db.scalar(
            select(TenantClient)
            .join(TenantDomain, TenantDomain.tenant_client_id == TenantClient.id)
            .where(
                TenantDomain.hostname == normalized_host,
                TenantClient.is_active.is_(True),
            )
        )
        # For single-tenant deployments, fall back to the first active tenant when
        # the custom domain has not been explicitly mapped yet.
        if client is None:
            client = db.scalar(
                select(TenantClient)
                .where(TenantClient.is_active.is_(True))
                .order_by(TenantClient.created_at.asc())
            )
    else:
        client = db.scalar(
            select(TenantClient).where(TenantClient.is_active.is_(True)).order_by(TenantClient.created_at.asc())
        )

    result = _to_public_config(db, client) if client else None
    cache.set_json(
        key,
        asdict(result) if result is not None else None,
        ttl_seconds=settings.tenant_config_ttl_seconds,
    )
    return result


def tenant_public_config_to_dict(config: TenantPublicConfig) -> dict:
    return asdict(config)
