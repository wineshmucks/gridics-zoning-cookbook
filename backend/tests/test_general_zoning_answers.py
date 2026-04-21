from __future__ import annotations

from app.agents.zoning_agent import ZoningChatOrchestrator
from app.schemas.chat_request import AnswerDraft, ChatRequest, GuardrailResult
from app.services.grounding_service import GroundingService


class FakeComposer:
    def __init__(self) -> None:
        self.calls = []

    def compose(self, **kwargs):
        self.calls.append(kwargs)
        return AnswerDraft(
            direct_answer="T4 generally allows more intensity than T3.",
            why=[
                "The retrieved zoning code materials describe T4 as a higher-intensity district than T3.",
            ],
            cited_evidence_ids=["code-1"],
            confidence="medium",
            follow_up_suggestion="Set a property if you want a parcel-specific answer.",
        )


class FakeKnowledgeService:
    def retrieve(self, **kwargs):
        return {
            "results": [
                {
                    "citation": {
                        "id": "code-1",
                        "source_type": "zoning_code",
                        "label": "Transect district comparison",
                        "section": "Section 3.2",
                        "excerpt": "T4 permits greater development intensity than T3.",
                        "url": "https://example.com/code#3.2",
                        "metadata": {},
                    },
                    "label": "Transect district comparison",
                    "excerpt": "T4 permits greater development intensity than T3.",
                }
            ]
        }


class FakePropertyService:
    def get_property_context(self, **kwargs):
        raise AssertionError("Property service should not be called when no property is selected.")


def test_general_question_without_property_returns_grounded_answer() -> None:
    composer = FakeComposer()
    orchestrator = ZoningChatOrchestrator(
        composer=composer,
        property_service=FakePropertyService(),
        knowledge_service=FakeKnowledgeService(),
        grounding_service=GroundingService(),
    )

    response = orchestrator.handle(
        ChatRequest(
            jurisdiction_id="miami",
            jurisdiction_name="Miami",
            question="What is the difference between T3 and T4?",
        )
    )

    assert response.used_property_context is False
    assert response.grounding_status == "grounded"
    assert "No property selected" in response.answer
    assert response.citations[0].id == "code-1"
    assert composer.calls[0]["property_context"] is None
    assert composer.calls[0]["evidence"].property_context_summary == []
    assert composer.calls[0]["evidence"].knowledge_summary


def test_property_specific_question_without_property_stays_general() -> None:
    composer = FakeComposer()
    orchestrator = ZoningChatOrchestrator(
        composer=composer,
        property_service=FakePropertyService(),
        knowledge_service=FakeKnowledgeService(),
        grounding_service=GroundingService(),
    )

    response = orchestrator.handle(
        ChatRequest(
            jurisdiction_id="miami",
            jurisdiction_name="Miami",
            question="Can I build an ADU here?",
        )
    )

    assert response.used_property_context is False
    assert "No property selected" in response.answer
    assert composer.calls[0]["property_context"] is None
