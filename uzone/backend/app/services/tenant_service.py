"""Tenant resolution and cached public configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import JurisdictionHomePageContent, TenantClient, TenantDomain
from app.services.cache_service import get_cache_service


@dataclass(slots=True)
class TenantPublicConfig:
    client_id: str
    clerk_organization_id: str | None
    city_name: str
    department_name: str
    standard_letter_fee_cents: int
    comprehensive_letter_fee_cents: int
    expedited_fee_cents: int
    support_phone: str | None
    support_email: str | None
    contact_address: str | None
    jurisdiction_id: str | None
    agent_url: str | None
    zoning_code_url: str | None
    home_page_content: dict


AGENT_URL_SETTING_KEY = "agent_url"
ZONING_CODE_URL_SETTING_KEY = "zoning_code_url"

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


def merge_tenant_experience_settings(
    existing_settings: dict | None,
    *,
    agent_url: str | None,
    zoning_code_url: str | None,
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

    return next_settings


def build_default_home_page_content(client: TenantClient) -> dict:
    city_name = client.city_name.strip() or "Your City"
    department_name = client.department_name.strip() or "Planning & Zoning Department"
    support_email = client.support_email.strip() if client.support_email else None
    support_phone = client.support_phone.strip() if client.support_phone else None
    contact_address = client.contact_address.strip() if client.contact_address else None
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
        if "jurisdiction_home_page_content" in str(exc):
            db.rollback()
            return None
        raise


def has_home_page_content_storage(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and inspect(bind).has_table("jurisdiction_home_page_content"))


def _to_public_config(
    db: Session,
    client: TenantClient,
) -> TenantPublicConfig:
    agent_url, zoning_code_url = get_tenant_experience_settings(client.settings_json)
    home_page_content_record = get_home_page_content_record(db, client.jurisdiction_id)
    return TenantPublicConfig(
        client_id=client.client_id,
        clerk_organization_id=client.clerk_organization_id,
        city_name=client.city_name,
        department_name=client.department_name,
        standard_letter_fee_cents=client.standard_letter_fee_cents,
        comprehensive_letter_fee_cents=client.comprehensive_letter_fee_cents,
        expedited_fee_cents=client.expedited_fee_cents,
        support_phone=client.support_phone,
        support_email=client.support_email,
        contact_address=client.contact_address,
        jurisdiction_id=client.jurisdiction_id,
        agent_url=agent_url,
        zoning_code_url=zoning_code_url,
        home_page_content=get_home_page_content_payload(home_page_content_record, client),
    )


def resolve_tenant_public_config(
    db: Session,
    *,
    host: str | None = None,
    client_id: str | None = None,
    organization_id: str | None = None,
) -> TenantPublicConfig | None:
    normalized_host = normalize_hostname(host)
    normalized_client_id = client_id.strip().lower() if client_id else None
    normalized_organization_id = organization_id.strip() if organization_id else None
    key = f"tenant-public:{_cache_key(host=normalized_host, client_id=normalized_client_id, organization_id=normalized_organization_id)}"
    cache = get_cache_service()
    cached = cache.get_json(key)
    if cached is not cache.cache_miss:
        if cached is None:
            return None
        return TenantPublicConfig(**cached)

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
