from __future__ import annotations

from app.agents.zoning_agent import ZoningChatOrchestrator, _build_answer_input
from app.schemas.chat_request import AnswerDraft, ChatRequest, GuardrailResult
from app.schemas.property_context import PropertyContextFact, PropertyContextResult
from app.services.grounding_service import GroundingService


class FakeComposer:
    def __init__(self) -> None:
        self.calls = []

    def compose(self, **kwargs):
        self.calls.append(kwargs)
        return AnswerDraft(
            direct_answer="The available property data shows a 10-foot front setback and a 5-foot side setback.",
            why=[
                "The Gridics parcel response included front and side setback values.",
                "The zoning code results provide the governing standards for the district.",
            ],
            property_context_used=["Address: 3148 Mary St", "Zoning district: T4"],
            cited_evidence_ids=["property-data-1", "code-1"],
            uncertainty=["Rear setback was not returned in the parcel lookup."],
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
                        "label": "Setback standards",
                        "section": "Sec. 4.5",
                        "excerpt": "Front and side setbacks apply by district.",
                        "url": "https://example.com/code#4.5",
                        "metadata": {},
                    },
                    "label": "Setback standards",
                    "excerpt": "Front and side setbacks apply by district.",
                }
            ]
        }


class FakePropertyService:
    def __init__(self) -> None:
        self.calls = []

    def get_property_context(self, **kwargs):
        self.calls.append(kwargs)
        return PropertyContextResult(
            status="partial",
            jurisdiction_id="miami",
            jurisdiction_name="Miami",
            address="3148 Mary St",
            latitude=25.7,
            longitude=-80.2,
            zoning_district="T4",
            setbacks_ft={"front_principal": 10.0, "side": 5.0, "rear": None},
            facts_for_prompt=[
                PropertyContextFact(label="Address", value="3148 Mary St"),
                PropertyContextFact(label="Zoning district", value="T4"),
            ],
            citations=[
                {
                    "id": "property-data-1",
                    "source_type": "gridics_property",
                    "label": "Gridics property data",
                    "excerpt": "Gridics property data for 3148 Mary St",
                    "section": None,
                    "url": None,
                    "metadata": {"status": "partial"},
                }
            ],
            missing_fields=["rear setback"],
        )


def test_property_specific_question_uses_property_context() -> None:
    composer = FakeComposer()
    property_service = FakePropertyService()
    orchestrator = ZoningChatOrchestrator(
        composer=composer,
        property_service=property_service,
        knowledge_service=FakeKnowledgeService(),
        grounding_service=GroundingService(),
    )

    response = orchestrator.handle(
        ChatRequest(
            jurisdiction_id="miami",
            jurisdiction_name="Miami",
            question="What are the setback requirements for this property?",
            property_selected=True,
            property_address="3148 Mary St",
            property_lat=25.7,
            property_lng=-80.2,
        )
    )

    assert response.used_property_context is True
    assert "Address: 3148 Mary St" in response.answer
    assert any(citation.id == "property-data-1" for citation in response.citations)
    assert property_service.calls == [
        {
            "lat": 25.7,
            "lng": -80.2,
            "jurisdiction_id": "miami",
            "jurisdiction_name": "Miami",
            "address": "3148 Mary St",
        }
    ]
    assert composer.calls[0]["property_context"] is not None
    assert composer.calls[0]["evidence"].property_context_summary
    assert composer.calls[0]["evidence"].knowledge_summary


def test_property_context_is_rendered_into_prompt_input() -> None:
    property_context = FakePropertyService().get_property_context(
        lat=25.7,
        lng=-80.2,
        jurisdiction_id="miami",
        address="3148 Mary St",
    )
    prompt = _build_answer_input(
        request=ChatRequest(
            jurisdiction_id="miami",
            jurisdiction_name="Miami",
            question="What are the setback requirements for this property?",
            property_selected=True,
            property_address="3148 Mary St",
            property_lat=25.7,
            property_lng=-80.2,
        ),
        guardrail=GuardrailResult(
            in_scope=True,
            reason="zoning",
            confidence=0.9,
            category="zoning",
        ),
        evidence=orchestrator_evidence_fixture(),
        property_context=property_context,
    )

    assert "Property context:" in prompt
    assert "Address: 3148 Mary St" in prompt
    assert "Coordinates: 25.700000, -80.200000" in prompt
    assert "Jurisdiction: Miami" in prompt
    assert "Zoning district: T4" in prompt
    assert "Property data status: partial" in prompt
    assert "Missing property fields: rear setback" in prompt


def orchestrator_evidence_fixture():
    return ZoningChatOrchestrator._build_evidence(
        knowledge_payload=FakeKnowledgeService().retrieve(),
        property_context=FakePropertyService().get_property_context(
            lat=25.7,
            lng=-80.2,
            jurisdiction_id="miami",
            address="3148 Mary St",
        ),
    )
