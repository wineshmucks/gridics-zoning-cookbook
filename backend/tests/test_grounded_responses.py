from __future__ import annotations

from app.agents.zoning_agent import ZoningChatOrchestrator
from app.schemas.chat_request import AnswerDraft, ChatRequest
from app.services.grounding_service import GroundingService


class FlakyComposer:
    def __init__(self) -> None:
        self.calls = 0

    def compose(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return AnswerDraft(
                direct_answer="ADUs are allowed.",
                why=["This answer forgot to include citations."],
                cited_evidence_ids=[],
                confidence="high",
            )
        return AnswerDraft(
            direct_answer="The retrieved code suggests ADUs may be allowed, subject to district-specific standards.",
            why=["The zoning code result discusses ADU standards for the jurisdiction."],
            cited_evidence_ids=["code-1"],
            confidence="medium",
        )


class FakeKnowledgeService:
    def retrieve(self, **kwargs):
        return {
            "results": [
                {
                    "citation": {
                        "id": "code-1",
                        "source_type": "zoning_code",
                        "label": "ADU standards",
                        "section": "Sec. 6.1",
                        "excerpt": "Accessory dwelling units are permitted where listed in the use table.",
                        "url": "https://example.com/code#6.1",
                        "metadata": {},
                    },
                    "label": "ADU standards",
                    "excerpt": "Accessory dwelling units are permitted where listed in the use table.",
                }
            ]
        }


class FakePropertyService:
    def get_property_context(self, **kwargs):
        raise AssertionError("Property service should not be called.")


def test_grounding_service_regenerates_once_when_citations_are_missing() -> None:
    composer = FlakyComposer()
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
            question="Is an ADU allowed?",
        )
    )

    assert composer.calls == 2
    assert response.grounding_status == "grounded"
    assert response.citations[0].id == "code-1"
