"""Tenant resolution and cached public configuration."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import TenantClient, TenantDomain


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


AGENT_URL_SETTING_KEY = "agent_url"
ZONING_CODE_URL_SETTING_KEY = "zoning_code_url"


_cache_lock = Lock()
_tenant_cache: dict[str, tuple[float, TenantPublicConfig | None]] = {}


def normalize_hostname(host: str | None) -> str | None:
    if not host:
        return None
    return host.split(":", 1)[0].strip().lower() or None


def _cache_key(*, host: str | None, client_id: str | None) -> str:
    if client_id:
        return f"client:{client_id.lower()}"
    if host:
      return f"host:{host.lower()}"
    return "default"


def _get_cached(key: str) -> TenantPublicConfig | None | object:
    with _cache_lock:
        cached = _tenant_cache.get(key)
        if cached is None:
            return _CACHE_MISS
        expires_at, value = cached
        if expires_at < time.time():
            _tenant_cache.pop(key, None)
            return _CACHE_MISS
        return value


def _put_cached(key: str, value: TenantPublicConfig | None) -> None:
    with _cache_lock:
        _tenant_cache[key] = (time.time() + settings.tenant_config_ttl_seconds, value)


def invalidate_tenant_cache() -> None:
    with _cache_lock:
        _tenant_cache.clear()


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


def _to_public_config(client: TenantClient) -> TenantPublicConfig:
    agent_url, zoning_code_url = get_tenant_experience_settings(client.settings_json)
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
    )


def resolve_tenant_public_config(
    db: Session,
    *,
    host: str | None = None,
    client_id: str | None = None,
) -> TenantPublicConfig | None:
    normalized_host = normalize_hostname(host)
    normalized_client_id = client_id.strip().lower() if client_id else None
    key = _cache_key(host=normalized_host, client_id=normalized_client_id)
    cached = _get_cached(key)
    if cached is not _CACHE_MISS:
        return cached

    client: TenantClient | None = None
    if normalized_client_id:
        client = db.scalar(
            select(TenantClient).where(
                TenantClient.client_id == normalized_client_id,
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

    result = _to_public_config(client) if client else None
    _put_cached(key, result)
    return result


_CACHE_MISS = object()


def tenant_public_config_to_dict(config: TenantPublicConfig) -> dict:
    return asdict(config)
