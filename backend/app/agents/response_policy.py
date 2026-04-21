"""Prompt loading and safe response policy helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.schemas.chat_request import ChatRequest, GuardrailResult

_PROMPT_DIR = Path(__file__).with_name("prompts")


@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def build_refusal_response(request: ChatRequest, guardrail: GuardrailResult) -> str:
    _ = load_prompt("refusal_policy.txt")
    return (
        "Direct answer:\n"
        "I can only help with zoning and land use questions.\n\n"
        "Why:\n"
        f"- {guardrail.reason}\n"
        "- Supported topics include zoning districts, permitted uses, setbacks, parking, overlays, height, density, and similar code questions.\n\n"
        "Property context used:\n"
        "- No property selected\n\n"
        "References:\n"
        "- User question only; no zoning evidence was retrieved because the request was out of scope.\n\n"
        "Uncertainty / caveats:\n"
        "- Try asking something like 'What is allowed in T3?', 'Is an ADU allowed?', or 'What setbacks apply to this property?'\n"
    )

