"""Email template defaults and effective-resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EmailTemplate, TenantClient

GRIDICS_OWNER_ORGANIZATION_ID = "gridics"

DEFAULT_EMAIL_TEMPLATE_DEFINITIONS = [
    {
        "code": "submitted",
        "trigger_state": "submitted",
        "name": "Request Submitted",
        "description": "Sent immediately after a zoning verification request is submitted.",
        "category": "request_updates",
        "subject_template": "Your request {{request_id}} has been received",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>We received your zoning verification request for {{property_address}}.</p>"
            "<p>We will send another update when processing begins.</p>"
        ),
    },
    {
        "code": "payment_pending",
        "trigger_state": "payment_pending",
        "name": "Payment Pending",
        "description": "Sent when checkout has started but payment is not complete yet.",
        "category": "request_updates",
        "subject_template": "Payment required for request {{request_id}}",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>Your request {{request_id}} is waiting for payment before review can begin.</p>"
            "<p>Please complete checkout to keep your request moving.</p>"
        ),
    },
    {
        "code": "paid",
        "trigger_state": "paid",
        "name": "Payment Confirmed",
        "description": "Sent after payment is successfully captured.",
        "category": "request_updates",
        "subject_template": "Payment confirmed for request {{request_id}}",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>Payment for request {{request_id}} has been confirmed.</p>"
            "<p>Your request is now moving into the review workflow.</p>"
        ),
    },
    {
        "code": "awaiting_additional_info",
        "trigger_state": "awaiting_additional_info",
        "name": "Additional Information Required",
        "description": "Sent when staff needs more details from the requester.",
        "category": "request_updates",
        "subject_template": "More information is needed for request {{request_id}}",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>We need additional information to continue review of request {{request_id}}.</p>"
            "<p>Please reply with the requested documents or details so we can resume processing.</p>"
        ),
    },
    {
        "code": "approved",
        "trigger_state": "approved",
        "name": "Request Approved",
        "description": "Sent when the request has been approved and finalized.",
        "category": "request_updates",
        "subject_template": "Your request {{request_id}} has been approved",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>Your request {{request_id}} has been approved.</p>"
            "<p>We will send the final letter as soon as delivery is complete.</p>"
        ),
    },
    {
        "code": "rejected",
        "trigger_state": "rejected",
        "name": "Request Rejected",
        "description": "Sent when the request cannot be completed.",
        "category": "request_updates",
        "subject_template": "Update for request {{request_id}}",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>Your request {{request_id}} has been closed without approval.</p>"
            "<p>Please contact staff if you need clarification on the decision.</p>"
        ),
    },
    {
        "code": "delivered",
        "trigger_state": "delivered",
        "name": "Letter Delivered",
        "description": "Sent when the final approved letter has been delivered.",
        "category": "request_updates",
        "subject_template": "Your zoning letter for request {{request_id}} is ready",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>Your final zoning verification letter for request {{request_id}} has been delivered.</p>"
            "<p>You can now review the completed document.</p>"
        ),
    },
    {
        "code": "cancelled",
        "trigger_state": "cancelled",
        "name": "Request Cancelled",
        "description": "Sent when the request is cancelled before completion.",
        "category": "request_updates",
        "subject_template": "Request {{request_id}} was cancelled",
        "body_template": (
            "<p>Hello {{requester_name}},</p>"
            "<p>Request {{request_id}} has been cancelled.</p>"
            "<p>If you still need a zoning verification letter, you can submit a new request.</p>"
        ),
    },
]


@dataclass(slots=True)
class EffectiveEmailTemplate:
    template: EmailTemplate
    default_template: EmailTemplate
    override_template: EmailTemplate | None


def ensure_default_email_templates(db: Session) -> None:
    existing = {
        template.code: template
        for template in db.scalars(
            select(EmailTemplate).where(EmailTemplate.is_system_default.is_(True))
        ).all()
    }

    created = False
    for definition in DEFAULT_EMAIL_TEMPLATE_DEFINITIONS:
        if definition["code"] in existing:
            continue
        db.add(
            EmailTemplate(
                jurisdiction_id=None,
                tenant_client_id=None,
                owner_organization_id=GRIDICS_OWNER_ORGANIZATION_ID,
                base_template_id=None,
                code=definition["code"],
                trigger_state=definition["trigger_state"],
                name=definition["name"],
                description=definition["description"],
                category=definition["category"],
                subject_template=definition["subject_template"],
                body_template=definition["body_template"],
                status="active",
                version=1,
                created_by_user_id=None,
                is_system_default=True,
            )
        )
        created = True

    if created:
        db.commit()


def get_default_email_templates(db: Session) -> list[EmailTemplate]:
    ensure_default_email_templates(db)
    return db.scalars(
        select(EmailTemplate)
        .where(EmailTemplate.is_system_default.is_(True))
        .order_by(EmailTemplate.trigger_state.asc(), EmailTemplate.name.asc())
    ).all()


def get_effective_email_templates(db: Session, tenant_client: TenantClient) -> list[EffectiveEmailTemplate]:
    defaults = get_default_email_templates(db)
    overrides = db.scalars(
        select(EmailTemplate)
        .where(EmailTemplate.tenant_client_id == tenant_client.id)
        .order_by(EmailTemplate.updated_at.desc())
    ).all()
    override_by_code = {template.code: template for template in overrides}
    effective_templates: list[EffectiveEmailTemplate] = []

    for default_template in defaults:
        override_template = override_by_code.get(default_template.code)
        effective_templates.append(
            EffectiveEmailTemplate(
                template=override_template or default_template,
                default_template=default_template,
                override_template=override_template,
            )
        )

    extra_override_codes = sorted(set(override_by_code) - {template.code for template in defaults})
    for code in extra_override_codes:
        override_template = override_by_code[code]
        effective_templates.append(
            EffectiveEmailTemplate(
                template=override_template,
                default_template=override_template,
                override_template=override_template,
            )
        )

    return effective_templates


def get_active_email_template_for_client(
    db: Session,
    *,
    tenant_client: TenantClient | None,
    template_code: str,
) -> EmailTemplate | None:
    ensure_default_email_templates(db)
    if tenant_client is not None:
        override_template = db.scalar(
            select(EmailTemplate)
            .where(
                EmailTemplate.tenant_client_id == tenant_client.id,
                EmailTemplate.code == template_code,
            )
            .order_by(EmailTemplate.updated_at.desc())
        )
        if override_template is not None:
            return override_template if override_template.status == "active" else None

    return db.scalar(
        select(EmailTemplate)
        .where(
            EmailTemplate.is_system_default.is_(True),
            EmailTemplate.code == template_code,
            EmailTemplate.status == "active",
        )
        .order_by(EmailTemplate.updated_at.desc())
    )
