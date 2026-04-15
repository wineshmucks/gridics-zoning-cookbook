"""Reusable response templates for guardrails and low-confidence outcomes."""

from __future__ import annotations


def insufficient_evidence_message(*, has_property_context: bool) -> str:
    if has_property_context:
        return (
            "I found parcel context, but I don't yet have enough cited zoning-code evidence "
            "to answer confidently. Please provide more detail or ask for a specific zoning topic."
        )
    return (
        "I don't have enough cited zoning evidence to answer confidently yet. "
        "Please provide more context or a specific property."
    )


def missing_address_details_message() -> str:
    return (
        "Gridics couldn't resolve this address from the information provided. "
        "Please confirm the full property address, including city, state, and ZIP code."
    )


def jurisdiction_lock_message(*, locked_label: str) -> str:
    return (
        f"This conversation is currently locked to {locked_label}. "
        "If you want to switch jurisdictions, please confirm and start a new property context."
    )
