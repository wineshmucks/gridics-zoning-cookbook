"""Public request API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RequestCreate(BaseModel):
    jurisdiction_id: str
    requester_user_id: str
    property_id: str
    property_snapshot_id: str
    letter_type: str = Field(pattern="^(standard|comprehensive)$")
    processing_type: str = Field(pattern="^(standard|expedited)$")
    delivery_method: str = Field(pattern="^(email|mail)$")
    requester_first_name: str = Field(min_length=1, max_length=100)
    requester_last_name: str = Field(min_length=1, max_length=100)
    requester_email: EmailStr
    requester_phone: str | None = Field(default=None, max_length=50)
    requester_organization: str | None = Field(default=None, max_length=255)
    mailing_address_json: dict | None = None
    special_instructions: str | None = None


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    public_id: str
    jurisdiction_id: str
    requester_user_id: str
    property_id: str
    property_snapshot_id: str
    letter_type: str
    processing_type: str
    delivery_method: str
    status: str
    payment_status: str
    assigned_to_user_id: str | None
    requester_first_name: str
    requester_last_name: str
    requester_email: EmailStr
    requester_phone: str | None
    requester_organization: str | None
    mailing_address_json: dict | None
    special_instructions: str | None
    submitted_at: datetime | None
    paid_at: datetime | None
    due_at: datetime | None
    approved_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    rejected_at: datetime | None
    total_amount_cents: int
    currency: str
    current_quote_id: str | None
    current_draft_id: str | None
    final_letter_version_id: str | None
    created_at: datetime
    updated_at: datetime


class RequestSubmit(BaseModel):
    actor_user_id: str | None = None


class RequestAssign(BaseModel):
    assigned_to_user_id: str
    assigned_by_user_id: str | None = None
    assignment_reason: str | None = None


class RequestStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    from_status: str | None
    to_status: str
    reason_code: str | None
    reason_text: str | None
    acted_by_user_id: str | None
    created_at: datetime


class RequestNoteCreate(BaseModel):
    author_user_id: str | None = None
    note_type: str = Field(pattern="^(internal|customer_message|system)$")
    visibility: str = Field(pattern="^(staff_only|customer_visible)$")
    body: str = Field(min_length=1)


class RequestNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    author_user_id: str
    note_type: str
    visibility: str
    body: str
    created_at: datetime
    updated_at: datetime


class RequestPaymentConfirm(BaseModel):
    actor_user_id: str | None = None
    reason_text: str | None = None


class RequestStartReview(BaseModel):
    actor_user_id: str | None = None
    reason_text: str | None = None
