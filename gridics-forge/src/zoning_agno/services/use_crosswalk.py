from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UseCrosswalkMatch:
    canonical_key: str
    score: float


_CROSSWALK_PATH = Path(__file__).resolve().parent.parent / "data" / "use_crosswalk.json"
_DERIVATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "use_derivations.json"


@lru_cache(maxsize=1)
def load_use_crosswalk() -> dict[str, list[str]]:
    with _CROSSWALK_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {str(key): [str(value) for value in values] for key, values in payload.items()}


@lru_cache(maxsize=1)
def load_use_derivations() -> dict[str, list[str]]:
    with _DERIVATIONS_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {str(key): [str(value) for value in values] for key, values in payload.items()}


def canonicalize_use_label(label: str | None) -> UseCrosswalkMatch | None:
    if not label:
        return None
    normalized = _normalize_use_label(label)
    best_key: str | None = None
    best_score = 0.0
    for canonical_key, aliases in load_use_crosswalk().items():
        for alias in aliases:
            alias_norm = _normalize_use_label(alias)
            score = _label_similarity(normalized, alias_norm)
            if score > best_score:
                best_score = score
                best_key = canonical_key
    if best_key is None or best_score < 0.72:
        return None
    return UseCrosswalkMatch(canonical_key=best_key, score=best_score)


def use_labels_share_canonical_concept(left: str | None, right: str | None) -> bool:
    left_match = canonicalize_use_label(left)
    right_match = canonicalize_use_label(right)
    return bool(left_match and right_match and left_match.canonical_key == right_match.canonical_key)


def _label_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if left_tokens and right_tokens and (left_tokens <= right_tokens or right_tokens <= left_tokens):
        return 0.95
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens) if left_tokens and right_tokens else 0.0
    ratio = SequenceMatcher(None, left, right).ratio()
    return max(overlap, ratio)


def _normalize_use_label(value: str) -> str:
    normalized = re.sub(r"\([^)]*\)", "", value.lower())
    normalized = normalized.replace("&", " and ").replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("commercial", "commercial")
    normalized = re.sub(r"\bdwelling\b", "", normalized)
    normalized = re.sub(r"\bunit\b", " unit ", normalized)
    normalized = re.sub(r"\boperation\b", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())
