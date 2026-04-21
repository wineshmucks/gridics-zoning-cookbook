from app.agents.guardrails import evaluate_zoning_scope


def test_guardrail_allows_zoning_questions() -> None:
    result = evaluate_zoning_scope("What are the setback requirements in T3?")

    assert result.in_scope is True
    assert result.category in {"zoning", "uncertain"}
    assert result.confidence >= 0.55


def test_guardrail_refuses_non_zoning_questions() -> None:
    result = evaluate_zoning_scope("What are the best restaurants nearby?")

    assert result.in_scope is False
    assert result.category == "non_zoning"
    assert "zoning" in result.reason.lower() or "land use" in result.reason.lower()

