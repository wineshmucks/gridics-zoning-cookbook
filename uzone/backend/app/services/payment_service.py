"""Configurable payment provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import time

import httpx

from app.core.config import settings


@dataclass
class PaymentCheckoutResult:
    provider: str
    external_id: str
    checkout_url: str | None
    status: str


class PaymentProvider:
    name: str

    def create_checkout(self, *, request_public_id: str, amount_cents: int, currency: str) -> PaymentCheckoutResult:
        raise NotImplementedError


class ManualPaymentProvider(PaymentProvider):
    name = "manual"

    def create_checkout(self, *, request_public_id: str, amount_cents: int, currency: str) -> PaymentCheckoutResult:
        return PaymentCheckoutResult(
            provider=self.name,
            external_id=f"manual_{request_public_id}",
            checkout_url=None,
            status="checkout_created",
        )


class StripePaymentProvider(PaymentProvider):
    name = "stripe"

    def create_checkout(self, *, request_public_id: str, amount_cents: int, currency: str) -> PaymentCheckoutResult:
        if not settings.stripe_secret_key:
            raise ValueError("Stripe provider selected but UZONE_STRIPE_SECRET_KEY is not configured")
        response = httpx.post(
            "https://api.stripe.com/v1/payment_intents",
            auth=(settings.stripe_secret_key, ""),
            data={
                "amount": amount_cents,
                "currency": currency.lower(),
                "automatic_payment_methods[enabled]": "true",
                "metadata[request_public_id]": request_public_id,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        return PaymentCheckoutResult(
            provider=self.name,
            external_id=payload["id"],
            checkout_url=None,
            status=payload.get("status", "checkout_created"),
        )


def available_payment_providers() -> dict[str, PaymentProvider]:
    providers: dict[str, PaymentProvider] = {"manual": ManualPaymentProvider()}
    if "stripe" in [item.strip() for item in settings.payment_providers.split(",") if item.strip()]:
        providers["stripe"] = StripePaymentProvider()
    return providers


def get_payment_provider(provider_name: str | None = None) -> PaymentProvider:
    name = provider_name or settings.default_payment_provider
    providers = available_payment_providers()
    if name not in providers:
        raise ValueError(f"Unsupported payment provider '{name}'")
    return providers[name]


def verify_stripe_webhook(payload: bytes, signature_header: str | None) -> dict:
    if not settings.stripe_webhook_secret:
        raise ValueError("UZONE_STRIPE_WEBHOOK_SECRET is not configured")
    if not signature_header:
        raise ValueError("Missing Stripe signature header")
    parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        raise ValueError("Invalid Stripe signature header")
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Stripe signature mismatch")
    if abs(time.time() - int(timestamp)) > 300:
        raise ValueError("Stripe webhook timestamp outside tolerance")
    return json.loads(payload.decode("utf-8"))
