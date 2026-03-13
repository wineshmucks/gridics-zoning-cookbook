"""Fee structure helpers and quote generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeeSchedule, FeeScheduleItem, Quote, Request, TenantClient


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


DEFAULT_STANDARD_FEE_CENTS = 7500
DEFAULT_COMPREHENSIVE_FEE_CENTS = 15000
DEFAULT_RUSH_FEE_CENTS = 5000
DEFAULT_CERTIFIED_COPY_FEE_CENTS = 1500
DEFAULT_MAIL_FEE_CENTS = 800
DEFAULT_MAIL_INTERNATIONAL_FEE_CENTS = 2500


DEFAULT_FEE_ITEMS: tuple[dict, ...] = (
    {
        "code": "standard_letter",
        "name": "Zoning Verification Letter (Standard)",
        "category": "base_fees",
        "fee_type": "base",
        "description": "Standard zoning verification letter with regular turnaround.",
        "currency": "USD",
        "applies_to_letter_type": "standard",
        "applies_to_processing_type": None,
        "applies_to_delivery_method": None,
        "tax_mode": "none",
        "charge_unit": "per_request",
        "display_order": 10,
        "metadata_json": {
            "processing_time_label": "5-7 business days",
            "tax_label": "No tax",
            "summary_label": "Standard processing",
        },
    },
    {
        "code": "comprehensive_letter",
        "name": "Zoning Verification Letter (Comprehensive)",
        "category": "base_fees",
        "fee_type": "base",
        "description": "Expanded zoning verification letter for more detailed review workflows.",
        "currency": "USD",
        "applies_to_letter_type": "comprehensive",
        "applies_to_processing_type": None,
        "applies_to_delivery_method": None,
        "tax_mode": "none",
        "charge_unit": "per_request",
        "display_order": 20,
        "metadata_json": {
            "processing_time_label": "5-7 business days",
            "tax_label": "No tax",
            "summary_label": "Comprehensive review",
        },
    },
    {
        "code": "rush_processing",
        "name": "Rush Processing Fee",
        "category": "expedited_fees",
        "fee_type": "rush",
        "description": "Additional charge for expedited request handling.",
        "currency": "USD",
        "applies_to_letter_type": None,
        "applies_to_processing_type": "expedited",
        "applies_to_delivery_method": None,
        "tax_mode": "none",
        "charge_unit": "per_request",
        "display_order": 30,
        "metadata_json": {
            "processing_time_label": "24-48 hours",
            "availability_label": "Business days only",
            "summary_label": "Rush add-on",
        },
    },
    {
        "code": "certified_copy",
        "name": "Certified Copy Fee",
        "category": "additional_services",
        "fee_type": "addon",
        "description": "Per-copy fee for stamped and certified printed copies.",
        "currency": "USD",
        "applies_to_letter_type": None,
        "applies_to_processing_type": None,
        "applies_to_delivery_method": None,
        "tax_mode": "none",
        "charge_unit": "per_copy",
        "display_order": 40,
        "metadata_json": {
            "max_quantity": 10,
            "bulk_discount_label": "No discount",
            "summary_label": "Per certified copy",
        },
    },
    {
        "code": "physical_mail_delivery",
        "name": "Physical Mail Delivery",
        "category": "additional_services",
        "fee_type": "addon",
        "description": "Postal delivery fee for mailing printed letters to the requester.",
        "currency": "USD",
        "applies_to_letter_type": None,
        "applies_to_processing_type": None,
        "applies_to_delivery_method": "mail",
        "tax_mode": "none",
        "charge_unit": "per_request",
        "display_order": 50,
        "metadata_json": {
            "delivery_method_label": "USPS First Class",
            "international_amount_cents": DEFAULT_MAIL_INTERNATIONAL_FEE_CENTS,
            "summary_label": "Mailed delivery",
        },
    },
)


def resolve_active_fee_schedule(db: Session, jurisdiction_id: str) -> FeeSchedule | None:
    now = _utcnow()
    return db.scalar(
        select(FeeSchedule)
        .where(
            FeeSchedule.jurisdiction_id == jurisdiction_id,
            FeeSchedule.status == "active",
            (FeeSchedule.effective_start_at.is_(None) | (FeeSchedule.effective_start_at <= now)),
            (FeeSchedule.effective_end_at.is_(None) | (FeeSchedule.effective_end_at >= now)),
        )
        .order_by(FeeSchedule.created_at.desc())
    )


def list_fee_schedule_items(db: Session, fee_schedule_id: str) -> list[FeeScheduleItem]:
    return db.scalars(
        select(FeeScheduleItem)
        .where(FeeScheduleItem.fee_schedule_id == fee_schedule_id)
        .order_by(FeeScheduleItem.display_order.asc(), FeeScheduleItem.created_at.asc())
    ).all()


def _default_amount_for_code(tenant_client: TenantClient, code: str) -> int:
    if code == "standard_letter":
        return tenant_client.standard_letter_fee_cents or DEFAULT_STANDARD_FEE_CENTS
    if code == "comprehensive_letter":
        return tenant_client.comprehensive_letter_fee_cents or DEFAULT_COMPREHENSIVE_FEE_CENTS
    if code == "rush_processing":
        return tenant_client.expedited_fee_cents or DEFAULT_RUSH_FEE_CENTS
    if code == "certified_copy":
        return DEFAULT_CERTIFIED_COPY_FEE_CENTS
    if code == "physical_mail_delivery":
        return DEFAULT_MAIL_FEE_CENTS
    return 0


def _default_item_payload(tenant_client: TenantClient, template: dict) -> dict:
    payload = dict(template)
    payload["amount_cents"] = _default_amount_for_code(tenant_client, template["code"])
    payload["metadata_json"] = dict(template.get("metadata_json") or {})
    return payload


def sync_tenant_fee_summary_fields(tenant_client: TenantClient, items: list[FeeScheduleItem]) -> None:
    items_by_code = {item.code: item for item in items}
    tenant_client.standard_letter_fee_cents = (
        items_by_code["standard_letter"].amount_cents if "standard_letter" in items_by_code else 0
    )
    tenant_client.comprehensive_letter_fee_cents = (
        items_by_code["comprehensive_letter"].amount_cents if "comprehensive_letter" in items_by_code else 0
    )
    tenant_client.expedited_fee_cents = (
        items_by_code["rush_processing"].amount_cents if "rush_processing" in items_by_code else 0
    )


def ensure_active_fee_schedule_for_tenant(db: Session, tenant_client: TenantClient) -> tuple[FeeSchedule, list[FeeScheduleItem]]:
    if not tenant_client.jurisdiction_id:
        raise ValueError("Tenant client must be linked to a jurisdiction before configuring fees")

    schedule = resolve_active_fee_schedule(db, tenant_client.jurisdiction_id)
    changed = False
    if schedule is None:
        schedule = FeeSchedule(
            jurisdiction_id=tenant_client.jurisdiction_id,
            name=f"{tenant_client.city_name} Active Fee Schedule",
            status="active",
            effective_start_at=_utcnow(),
        )
        db.add(schedule)
        db.flush()
        changed = True

    items = list_fee_schedule_items(db, schedule.id)
    existing_by_code = {item.code: item for item in items}

    for template in DEFAULT_FEE_ITEMS:
        if template["code"] in existing_by_code:
            continue
        item = FeeScheduleItem(
            fee_schedule_id=schedule.id,
            **_default_item_payload(tenant_client, template),
            is_active=True,
        )
        db.add(item)
        changed = True

    if changed:
        db.flush()

    items = list_fee_schedule_items(db, schedule.id)
    existing_summary = (
        tenant_client.standard_letter_fee_cents,
        tenant_client.comprehensive_letter_fee_cents,
        tenant_client.expedited_fee_cents,
    )
    sync_tenant_fee_summary_fields(tenant_client, items)
    summary_changed = existing_summary != (
        tenant_client.standard_letter_fee_cents,
        tenant_client.comprehensive_letter_fee_cents,
        tenant_client.expedited_fee_cents,
    )
    if changed or summary_changed:
        db.commit()
        db.refresh(schedule)
        items = list_fee_schedule_items(db, schedule.id)
    return schedule, items


def update_fee_structure_for_tenant(
    db: Session,
    tenant_client: TenantClient,
    *,
    name: str | None,
    items: list[dict],
) -> tuple[FeeSchedule, list[FeeScheduleItem]]:
    schedule, existing_items = ensure_active_fee_schedule_for_tenant(db, tenant_client)
    if name:
        schedule.name = name

    existing_by_code = {item.code: item for item in existing_items}
    for payload in items:
        metadata_json = dict(payload.get("metadata_json") or {})
        existing = existing_by_code.get(payload["code"])
        if existing is None:
            existing = FeeScheduleItem(
                fee_schedule_id=schedule.id,
                metadata_json=metadata_json,
                **{key: value for key, value in payload.items() if key != "metadata_json"},
            )
            db.add(existing)
            continue

        existing.name = payload["name"]
        existing.category = payload["category"]
        existing.fee_type = payload["fee_type"]
        existing.description = payload.get("description")
        existing.amount_cents = payload["amount_cents"]
        existing.currency = payload["currency"]
        existing.applies_to_letter_type = payload.get("applies_to_letter_type")
        existing.applies_to_processing_type = payload.get("applies_to_processing_type")
        existing.applies_to_delivery_method = payload.get("applies_to_delivery_method")
        existing.tax_mode = payload.get("tax_mode")
        existing.charge_unit = payload.get("charge_unit")
        existing.display_order = payload["display_order"]
        existing.is_active = payload["is_active"]
        existing.metadata_json = metadata_json

    db.flush()
    updated_items = list_fee_schedule_items(db, schedule.id)
    sync_tenant_fee_summary_fields(tenant_client, updated_items)
    db.commit()
    db.refresh(schedule)
    updated_items = list_fee_schedule_items(db, schedule.id)
    return schedule, updated_items


def build_quote_for_request(db: Session, request: Request) -> Quote:
    fee_schedule = resolve_active_fee_schedule(db, request.jurisdiction_id)
    if fee_schedule is None:
        raise ValueError("No active fee schedule found for jurisdiction")

    items = db.scalars(
        select(FeeScheduleItem)
        .where(
            FeeScheduleItem.fee_schedule_id == fee_schedule.id,
            FeeScheduleItem.is_active.is_(True),
        )
        .order_by(FeeScheduleItem.display_order.asc(), FeeScheduleItem.created_at.asc())
    ).all()

    line_items: list[dict] = []
    subtotal_cents = 0
    tax_cents = 0
    for item in items:
        if item.applies_to_letter_type and item.applies_to_letter_type != request.letter_type:
            continue
        if item.applies_to_processing_type and item.applies_to_processing_type != request.processing_type:
            continue
        if item.applies_to_delivery_method and item.applies_to_delivery_method != request.delivery_method:
            continue

        subtotal_cents += item.amount_cents
        line_items.append(
            {
                "code": item.code,
                "name": item.name,
                "amount_cents": item.amount_cents,
                "currency": item.currency,
            }
        )

    return Quote(
        request_id=request.id,
        fee_schedule_id=fee_schedule.id,
        status="finalized",
        line_items_json=line_items,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=subtotal_cents + tax_cents,
        currency="USD",
        expires_at=_utcnow() + timedelta(days=7),
    )
