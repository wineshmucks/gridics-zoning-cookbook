"""Evaluation helpers for assistant guardrails and jurisdiction checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.jurisdiction_resolver import resolve_jurisdiction_for_property_request
from app.services.policy_service import evaluate_policy_decision


@dataclass
class EvalResult:
    total_cases: int
    passed_cases: int
    policy_accuracy: float
    jurisdiction_accuracy: float
    failed_case_ids: list[str]
    category_accuracy: dict[str, float]


def _tenant_stub(payload: dict[str, Any] | None):
    tenant = payload or {}
    return type(
        "TenantStub",
        (),
        {
            "city_name": str(tenant.get("city_name") or ""),
            "settings_json": tenant.get("settings_json") if isinstance(tenant.get("settings_json"), dict) else {},
        },
    )()


def evaluate_guardrail_cases(cases: list[dict[str, Any]]) -> EvalResult:
    policy_checks = 0
    policy_pass = 0
    jurisdiction_checks = 0
    jurisdiction_pass = 0
    failed_case_ids: list[str] = []
    category_total: dict[str, int] = {}
    category_pass: dict[str, int] = {}

    for case in cases:
        case_id = str(case.get("id") or "unknown")
        category = str(case.get("category") or "general")
        category_total[category] = category_total.get(category, 0) + 1
        case_passed = True
        tenant_client = _tenant_stub(case.get("tenant"))
        expected_policy = case.get("expected_policy_decision")
        expected_jurisdiction = case.get("expected_jurisdiction_status")

        policy = evaluate_policy_decision(
            query=str(case.get("query") or ""),
            question_type=str(case.get("question_type") or "general_zoning"),
            tenant_client=tenant_client,
            resolved_city=str(case.get("resolved_city") or "") or None,
            resolved_state=str(case.get("resolved_state") or "") or None,
        )
        if expected_policy:
            policy_checks += 1
            if policy.get("decision") == expected_policy:
                policy_pass += 1
            else:
                failed_case_ids.append(case_id)
                case_passed = False

        if expected_jurisdiction:
            jurisdiction_checks += 1
            result = resolve_jurisdiction_for_property_request(
                tenant_client=tenant_client,
                standardized_address=str(case.get("standardized_address") or ""),
                lookup_ready=bool(case.get("lookup_ready", True)),
                resolved_city=str(case.get("resolved_city") or "") or None,
                resolved_state=str(case.get("resolved_state") or "") or None,
            )
            if result.get("jurisdiction_status") == expected_jurisdiction:
                jurisdiction_pass += 1
            else:
                if case_id not in failed_case_ids:
                    failed_case_ids.append(case_id)
                case_passed = False

        if case_passed:
            category_pass[category] = category_pass.get(category, 0) + 1

    total = len(cases)
    policy_accuracy = (policy_pass / policy_checks) if policy_checks else 1.0
    jurisdiction_accuracy = (jurisdiction_pass / jurisdiction_checks) if jurisdiction_checks else 1.0
    passed_cases = total - len(failed_case_ids)
    category_accuracy = {
        name: (category_pass.get(name, 0) / count if count else 1.0)
        for name, count in category_total.items()
    }
    return EvalResult(
        total_cases=total,
        passed_cases=passed_cases,
        policy_accuracy=policy_accuracy,
        jurisdiction_accuracy=jurisdiction_accuracy,
        failed_case_ids=failed_case_ids,
        category_accuracy=category_accuracy,
    )
