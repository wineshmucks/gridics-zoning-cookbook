"""Configurable email delivery adapters."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmailEvent, PropertySnapshot, Request, TenantClient
from app.services.email_template_service import get_active_email_template_for_client
from app.services.template_service import render_template


@dataclass
class EmailSendResult:
    provider: str
    provider_message_id: str | None
    status: str


class EmailProvider:
    name: str

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> EmailSendResult:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    name = "console"

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> EmailSendResult:
        print(f"[email:{self.name}] to={to} subject={subject}\n{html}")
        return EmailSendResult(provider=self.name, provider_message_id=None, status="sent")


class ResendEmailProvider(EmailProvider):
    name = "resend"

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> EmailSendResult:
        if not settings.resend_api_key:
            raise ValueError("Resend provider selected but UZONE_RESEND_API_KEY is not configured")
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        return EmailSendResult(provider=self.name, provider_message_id=payload.get("id"), status="sent")


class PostmarkEmailProvider(EmailProvider):
    name = "postmark"

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> EmailSendResult:
        if not settings.postmark_server_token:
            raise ValueError("Postmark provider selected but UZONE_POSTMARK_SERVER_TOKEN is not configured")
        response = httpx.post(
            "https://api.postmarkapp.com/email",
            headers={
                "X-Postmark-Server-Token": settings.postmark_server_token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "From": settings.email_from,
                "To": to,
                "Subject": subject,
                "HtmlBody": html,
                "TextBody": text or "",
                "MessageStream": "outbound",
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        return EmailSendResult(
            provider=self.name,
            provider_message_id=str(payload.get("MessageID")),
            status="sent",
        )


class MandrillEmailProvider(EmailProvider):
    name = "mandrill"

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> EmailSendResult:
        if not settings.mandrill_api_key:
            raise ValueError("Mandrill provider selected but UZONE_MANDRILL_API_KEY is not configured")
        response = httpx.post(
            "https://mandrillapp.com/api/1.0/messages/send.json",
            json={
                "key": settings.mandrill_api_key,
                "message": {
                    "from_email": settings.email_from,
                    "to": [{"email": to, "type": "to"}],
                    "subject": subject,
                    "html": html,
                    "text": text or "",
                },
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        first = payload[0] if isinstance(payload, list) and payload else {}
        return EmailSendResult(
            provider=self.name,
            provider_message_id=str(first.get("_id")) if first.get("_id") is not None else None,
            status=str(first.get("status") or "sent"),
        )


def get_email_provider() -> EmailProvider:
    provider = settings.email_provider.strip().lower()
    if provider == "console":
        return ConsoleEmailProvider()
    if provider == "resend":
        return ResendEmailProvider()
    if provider == "postmark":
        return PostmarkEmailProvider()
    if provider == "mandrill":
        return MandrillEmailProvider()
    raise ValueError(f"Unsupported email provider '{provider}'")


def send_templated_email(
    db: Session,
    *,
    request: Request,
    template_code: str,
    variables: dict[str, str],
) -> EmailEvent | None:
    tenant_client = db.scalar(
        select(TenantClient)
        .where(
            TenantClient.jurisdiction_id == request.jurisdiction_id,
            TenantClient.is_active.is_(True),
        )
        .order_by(TenantClient.created_at.asc())
    )
    template = get_active_email_template_for_client(
        db,
        tenant_client=tenant_client,
        template_code=template_code,
    )
    if template is None:
        return None

    subject = render_template(template.subject_template, variables)
    body = render_template(template.body_template, variables)
    result = get_email_provider().send(
        to=request.requester_email,
        subject=subject,
        html=body,
        text=body,
    )
    event = EmailEvent(
        request_id=request.id,
        template_id=template.id,
        recipient_email=request.requester_email,
        subject_rendered=subject,
        body_rendered=body,
        provider=result.provider,
        provider_message_id=result.provider_message_id,
        status=result.status,
    )
    db.add(event)
    return event


def build_request_email_variables(db: Session, request: Request, extra_variables: dict[str, str] | None = None) -> dict[str, str]:
    property_snapshot = db.get(PropertySnapshot, request.property_snapshot_id)
    variables = {
        "request_id": request.public_id,
        "requester_name": f"{request.requester_first_name} {request.requester_last_name}".strip(),
        "requester_email": request.requester_email,
        "property_address": property_snapshot.address if property_snapshot is not None else "",
        "apn": property_snapshot.apn if property_snapshot and property_snapshot.apn else "",
        "zoning_code": property_snapshot.zoning_code if property_snapshot and property_snapshot.zoning_code else "",
        "zoning_name": property_snapshot.zoning_name if property_snapshot and property_snapshot.zoning_name else "",
        "delivery_method": request.delivery_method,
        "letter_type": request.letter_type,
        "processing_type": request.processing_type,
        "status": request.status,
    }
    if extra_variables:
        variables.update({key: value for key, value in extra_variables.items() if value is not None})
    return variables


def send_request_status_email(
    db: Session,
    *,
    request: Request,
    extra_variables: dict[str, str] | None = None,
) -> EmailEvent | None:
    return send_templated_email(
        db,
        request=request,
        template_code=request.status,
        variables=build_request_email_variables(db, request, extra_variables),
    )
