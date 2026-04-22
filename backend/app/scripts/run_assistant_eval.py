"""Run guardrail evaluation cases and enforce release thresholds."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.agentic.assistant_eval_service import evaluate_guardrail_cases


def main() -> int:
    cases_path = BACKEND_ROOT / "evals" / "assistant_guardrail_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    result = evaluate_guardrail_cases(cases)

    policy_threshold = float(os.getenv("ASSISTANT_EVAL_POLICY_THRESHOLD", "0.95"))
    jurisdiction_threshold = float(os.getenv("ASSISTANT_EVAL_JURISDICTION_THRESHOLD", "0.95"))

    print(
        json.dumps(
            {
                "total_cases": result.total_cases,
                "passed_cases": result.passed_cases,
                "policy_accuracy": round(result.policy_accuracy, 4),
                "jurisdiction_accuracy": round(result.jurisdiction_accuracy, 4),
                "failed_case_ids": result.failed_case_ids,
                "category_accuracy": result.category_accuracy,
                "policy_threshold": policy_threshold,
                "jurisdiction_threshold": jurisdiction_threshold,
            },
            indent=2,
        )
    )

    if result.policy_accuracy < policy_threshold or result.jurisdiction_accuracy < jurisdiction_threshold:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
