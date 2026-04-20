"""Workflow and reporting schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuoteLineItem(BaseModel):
    code: str
    name: str
    amount_cents: int
    currency: str


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    fee_schedule_id: str
    status: str
    line_items_json: list | dict
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    generated_at: datetime
    expires_at: datetime | None
    created_at: datetime


class PaymentCheckoutCreate(BaseModel):
    actor_user_id: str | None = None
    provider: str = Field(default="manual", min_length=1, max_length=100)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    quote_id: str
    provider: str
    provider_payment_id: str | None
    provider_checkout_id: str | None
    status: str
    amount_cents: int
    currency: str
    paid_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    receipt_url: str | None
    created_at: datetime
    updated_at: datetime


class LetterDraftCreate(BaseModel):
    actor_user_id: str | None = None


class LetterDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    template_id: str
    status: str
    generated_body: str
    editable_sections_json: list | dict | None
    generated_from_snapshot_id: str | None
    created_by_user_id: str | None
    updated_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class ApprovalAction(BaseModel):
    actor_user_id: str | None = None
    reason_text: str | None = None


class DeliveryAction(BaseModel):
    actor_user_id: str | None = None
    destination: str = Field(min_length=1)
    provider_reference: str | None = None


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    letter_version_id: str
    delivery_method: str
    status: str
    destination: str
    provider_reference: str | None
    delivered_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class ReportSummary(BaseModel):
    total_requests: int
    submitted_requests: int
    paid_requests: int
    in_progress_requests: int
    approved_requests: int
    delivered_requests: int
    total_revenue_cents: int
