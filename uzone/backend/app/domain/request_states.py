"""Request lifecycle helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transition:
    from_status: str
    to_status: str
    reason_code: str
    reason_text: str


REQUEST_TRANSITIONS: dict[tuple[str, str], str] = {
    ("draft", "submitted"): "submit_request",
    ("submitted", "payment_pending"): "start_checkout",
    ("payment_pending", "paid"): "confirm_payment",
    ("paid", "pending_review"): "queue_request",
    ("pending_review", "in_progress"): "start_review",
    ("in_progress", "awaiting_additional_info"): "request_more_info",
    ("awaiting_additional_info", "in_progress"): "resume_review",
    ("in_progress", "awaiting_final_signature"): "send_to_signer",
    ("awaiting_final_signature", "approved"): "approve_request",
    ("approved", "delivered"): "deliver_request",
    ("pending_review", "rejected"): "reject_request",
    ("in_progress", "rejected"): "reject_request",
    ("submitted", "cancelled"): "cancel_request",
    ("payment_pending", "cancelled"): "cancel_request",
    ("paid", "cancelled"): "cancel_request",
}


def ensure_transition_allowed(from_status: str, to_status: str) -> None:
    if (from_status, to_status) not in REQUEST_TRANSITIONS:
        raise ValueError(f"Invalid request transition: {from_status} -> {to_status}")

