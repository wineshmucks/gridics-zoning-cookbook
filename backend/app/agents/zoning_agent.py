"""Production-oriented zoning assistant orchestration built on Agno."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.team.mode import TeamMode
from agno.team.team import Team

from app.agents.factory import build_agent_model, create_agent
from app.agents.guardrails import evaluate_zoning_scope
from app.agents.response_policy import build_refusal_response, load_prompt
from app.agents.storage import build_agno_session_kwargs, log_agno_run_metrics
from app.schemas.chat_request import AnswerDraft, ChatRequest, ChatResponse, GuardrailResult
from app.schemas.citations import Citation, EvidenceBundle
from app.schemas.property_context import PropertyContextResult
from app.services.grounding_service import GroundingService
from app.services.property_context_service import GridicsPropertyContextService
from app.services.zoning_knowledge_tool_service import ZoningKnowledgeLookupService
from app.tools.gridics_property_tool import get_property_context
from app.tools.zoning_knowledge_tool import retrieve_zoning_knowledge

logger = logging.getLogger(__name__)

AGNO_SESSION_KWARGS = build_agno_session_kwargs(enable_history=True)
_PROMPT_DIR = Path(__file__).with_name("prompts")


def _emit_orchestrator_log(message: str) -> None:
    logger.warning(message)
    print(message, flush=True)


def _render_conversation_history(request: ChatRequest) -> str:
    if not request.conversation_history:
        return "No prior conversation history."
    return "\n".join(f"- {turn.role}: {turn.content}" for turn in request.conversation_history[-6:])


def _looks_property_specific(question: str) -> bool:
    normalized = (question or "").strip().lower()
    markers = [
        "this property",
        "this parcel",
        "here",
        "can i build here",
        "for this property",
        "on this lot",
    ]
    return any(marker in normalized for marker in markers)


def _render_property_prompt_block(property_context: PropertyContextResult | None) -> str:
    """Render deterministic property context for the answer-composer prompt."""

    if property_context is None:
        return "- No property selected"

    lines: list[str] = []
    seen_labels: set[str] = set()
    if property_context.facts_for_prompt:
        for fact in property_context.facts_for_prompt:
            lines.append(f"- {fact.label}: {fact.value}")
            seen_labels.add(fact.label.strip().lower())
    else:
        lines.append("- Property lookup was unavailable")

    if (
        property_context.latitude is not None
        and property_context.longitude is not None
        and "coordinates" not in seen_labels
    ):
        lines.append(f"- Coordinates: {property_context.latitude:.6f}, {property_context.longitude:.6f}")
    if property_context.address and "address" not in seen_labels:
        lines.append(f"- Address: {property_context.address}")
    if property_context.zoning_district and "zoning district" not in seen_labels:
        lines.append(f"- Zoning district: {property_context.zoning_district}")

    if property_context.status:
        lines.append(f"- Property data status: {property_context.status}")
    if property_context.missing_fields:
        lines.append(f"- Missing property fields: {', '.join(property_context.missing_fields)}")

    return "\n".join(lines)


def _build_answer_input(
    *,
    request: ChatRequest,
    guardrail: GuardrailResult,
    evidence: EvidenceBundle,
    property_context: PropertyContextResult | None,
) -> str:
    property_block = _render_property_prompt_block(property_context)
    evidence_lines = []
    for citation in evidence.citations:
        section = f" | section={citation.section}" if citation.section else ""
        excerpt = f" | excerpt={citation.excerpt}" if citation.excerpt else ""
        evidence_lines.append(f"- id={citation.id} | source={citation.source_type} | label={citation.label}{section}{excerpt}")
    evidence_block = "\n".join(evidence_lines) or "- No evidence retrieved"
    request_note = (
        "The user appears to be asking about a specific parcel without a selected property. "
        "Explain that a property selection is required for a precise parcel-level answer and provide any general zoning guidance that is still supported by the retrieved code."
        if property_context is None and _looks_property_specific(request.question)
        else "Answer only from the supplied evidence."
    )

    return (
        f"Jurisdiction: {request.jurisdiction_name} ({request.jurisdiction_id})\n"
        f"Question: {request.question}\n"
        f"Request note: {request_note}\n"
        f"Guardrail: {guardrail.model_dump_json()}\n"
        f"Conversation history:\n{_render_conversation_history(request)}\n"
        f"Property context:\n{property_block}\n"
        f"Evidence:\n{evidence_block}\n"
    )


@dataclass(slots=True)
class AgnoAnswerComposer:
    """Structured-output answer composer backed by Agno."""

    agent: Agent

    def compose(
        self,
        *,
        request: ChatRequest,
        guardrail: GuardrailResult,
        evidence: EvidenceBundle,
        property_context: PropertyContextResult | None,
        stricter: bool = False,
    ) -> AnswerDraft:
        additional_context = load_prompt("answer_policy.txt")
        if stricter:
            additional_context += "\nUse only the supplied evidence IDs. If evidence is thin, lower confidence and say so."
        payload = _build_answer_input(
            request=request,
            guardrail=guardrail,
            evidence=evidence,
            property_context=property_context,
        )
        # Emit debug logs showing the property context and rendered prompt
        try:
            pc_dump = property_context.model_dump() if property_context is not None else None
        except Exception:
            try:
                pc_dump = property_context.dict() if hasattr(property_context, "dict") else str(property_context)
            except Exception:
                pc_dump = str(property_context)
        _emit_orchestrator_log(
            "[AgnoAnswerComposer] composing answer "
            f"jurisdiction={getattr(request, 'jurisdiction_id', None)!r} "
            f"property_status={getattr(property_context, 'status', None)!r} "
            f"property_context={pc_dump!r}"
        )
        _emit_orchestrator_log(
            "[AgnoAnswerComposer] rendered_property_block=" + _render_property_prompt_block(property_context)[:2000]
        )
        _emit_orchestrator_log(
            "[AgnoAnswerComposer] evidence_counts="
            f"citations={len(evidence.citations)} knowledge_summary={len(evidence.knowledge_summary)}"
        )
        response = self.agent.run(
            payload,
            output_schema=AnswerDraft,
            metadata={
                "jurisdiction_id": request.jurisdiction_id,
                "property_selected": request.property_selected,
            },
            additional_context=additional_context,
        )
        content = getattr(response, "content", response)
        # Log a short preview of the model response for debugging
        try:
            preview = content.model_dump_json() if hasattr(content, "model_dump_json") else str(content)
        except Exception:
            preview = str(content)
        _emit_orchestrator_log("[AgnoAnswerComposer] model_response_preview=" + preview[:1000])
        if isinstance(content, AnswerDraft):
            return content
        if isinstance(content, dict):
            return AnswerDraft.model_validate(content)
        return AnswerDraft.model_validate_json(str(content))


@dataclass(slots=True)
class ZoningChatOrchestrator:
    """Deterministic orchestration layer around Agno answer composition."""

    composer: AgnoAnswerComposer
    property_service: GridicsPropertyContextService
    knowledge_service: ZoningKnowledgeLookupService
    grounding_service: GroundingService

    def handle(self, request: ChatRequest) -> ChatResponse:
        _emit_orchestrator_log(
            "[ZoningOrchestrator] request "
            f"jurisdiction_id={request.jurisdiction_id} "
            f"jurisdiction_name={request.jurisdiction_name!r} "
            f"property_selected={request.property_selected} "
            f"property_address={request.property_address!r} "
            f"property_lat={request.property_lat} "
            f"property_lng={request.property_lng} "
            f"question={request.question[:200]!r}"
        )
        guardrail = evaluate_zoning_scope(request.question)
        if not guardrail.in_scope:
            return ChatResponse(
                answer=build_refusal_response(request, guardrail),
                citations=[],
                used_property_context=False,
                grounding_status="refused_out_of_scope",
                confidence="high",
                follow_up_suggestion="Ask about zoning districts, setbacks, overlays, parking, or other land use rules.",
                guardrail=guardrail,
            )

        knowledge_payload = self.knowledge_service.retrieve(
            jurisdiction_id=request.jurisdiction_id,
            question=request.question,
            limit=5,
        )
        property_context: PropertyContextResult | None = None
        if request.property_selected and request.property_lat is not None and request.property_lng is not None:
            property_context = self.property_service.get_property_context(
                lat=request.property_lat,
                lng=request.property_lng,
                jurisdiction_id=request.jurisdiction_id,
                jurisdiction_name=request.jurisdiction_name,
                address=request.property_address,
            )
        elif request.property_selected:
            property_context = PropertyContextResult(
                status="partial",
                jurisdiction_id=request.jurisdiction_id,
                address=request.property_address,
                missing_fields=["property_lat", "property_lng"],
                error_message="A property was selected, but coordinates were not provided.",
            )

        _emit_orchestrator_log(
            "[ZoningOrchestrator] property context "
            f"status={getattr(property_context, 'status', None)!r} "
            f"address={getattr(property_context, 'address', None)!r} "
            f"zoning_district={getattr(property_context, 'zoning_district', None)!r} "
            f"overlays={getattr(property_context, 'overlays', [])!r} "
            f"missing_fields={getattr(property_context, 'missing_fields', [])!r}"
        )

        evidence = self._build_evidence(knowledge_payload=knowledge_payload, property_context=property_context)
        _emit_orchestrator_log(
            "[ZoningOrchestrator] evidence "
            f"knowledge_results={len(knowledge_payload.get('results') or [])} "
            f"citations={len(evidence.citations)} "
            f"property_summary_items={len(evidence.property_context_summary)} "
            f"knowledge_summary_items={len(evidence.knowledge_summary)}"
        )
        draft = self.composer.compose(
            request=request,
            guardrail=guardrail,
            evidence=evidence,
            property_context=property_context,
        )
        validation = self.grounding_service.validate(draft, evidence)
        if validation.status != "grounded":
            draft = self.composer.compose(
                request=request,
                guardrail=guardrail,
                evidence=evidence,
                property_context=property_context,
                stricter=True,
            )
            validation = self.grounding_service.validate(draft, evidence)

        return self.grounding_service.build_response(
            draft=draft,
            evidence=evidence,
            guardrail=guardrail,
            property_context=property_context,
            validation=validation,
        )

    @staticmethod
    def _build_evidence(*, knowledge_payload: dict[str, Any], property_context: PropertyContextResult | None) -> EvidenceBundle:
        citations: list[Citation] = []
        knowledge_summary: list[str] = []
        property_summary: list[str] = []

        if property_context is not None:
            citations.extend(property_context.citations)
            property_summary.extend(f"{fact.label}: {fact.value}" for fact in property_context.facts_for_prompt)

        for result in knowledge_payload.get("results") or []:
            citation_payload = result.get("citation")
            if citation_payload:
                citations.append(Citation.model_validate(citation_payload))
            excerpt = str(result.get("excerpt") or "").strip()
            label = str(result.get("label") or "").strip()
            if label:
                knowledge_summary.append(f"{label}: {excerpt}".strip(": "))

        return EvidenceBundle(
            citations=citations,
            property_context_summary=property_summary,
            knowledge_summary=knowledge_summary,
        )


def build_grounded_answer_agent() -> Agent:
    """Internal structured-output agent used only for grounded answer composition."""

    return create_agent(
        id="customer-zoning-answer-agent",
        name="Gridics Zoning Answer Composer",
        description="Internal grounded zoning answer composer.",
        model=build_agent_model(model_id_override="gemini-2.5-flash-lite", allow_missing_api_key=True),
        db=AGNO_SESSION_KWARGS["db"],
        add_history_to_context=False,
        add_session_state_to_context=False,
        compress_tool_results=True,
        enable_agentic_state=False,
        markdown=True,
        use_instruction_tags=True,
        system_message=load_prompt("system_prompt.txt"),
        instructions=[
            "Generate zoning answers only from the evidence supplied in the user message.",
            "Never invent evidence IDs, parcel facts, or code references.",
            "If no property context was supplied, avoid parcel-specific conclusions.",
            "Return structured JSON matching the AnswerDraft schema.",
        ],
        expected_output="Return structured JSON that matches the AnswerDraft schema.",
        tools=[],
        post_hooks=[log_agno_run_metrics],
    )


def build_zoning_assistant_agent() -> Agent:
    return create_agent(
        id="customer-zoning-agent",
        name="Gridics Zoning Assistant",
        description="Grounded zoning assistant that answers general and property-specific questions with citations.",
        model=build_agent_model(model_id_override="gemini-2.5-flash-lite", allow_missing_api_key=True),
        db=AGNO_SESSION_KWARGS["db"],
        add_history_to_context=AGNO_SESSION_KWARGS["add_history_to_context"],
        num_history_runs=AGNO_SESSION_KWARGS["num_history_runs"],
        store_history_messages=AGNO_SESSION_KWARGS["store_history_messages"],
        session_state={"active_property_context": None},
        add_session_state_to_context=True,
        compress_tool_results=True,
        max_tool_calls_from_history=1,
        tool_call_limit=3,
        enable_agentic_state=False,
        markdown=True,
        use_instruction_tags=True,
        system_message=load_prompt("system_prompt.txt"),
        instructions=[
            "Generate zoning answers only from the evidence supplied in the user message.",
            "Never invent evidence IDs, parcel facts, or code references.",
            "If no property context was supplied, avoid parcel-specific conclusions.",
        ],
        expected_output="Return structured JSON that matches the AnswerDraft schema.",
        tools=[retrieve_zoning_knowledge, get_property_context],
        post_hooks=[log_agno_run_metrics],
    )


def build_code_researcher_agent() -> Agent:
    return create_agent(
        id="code-researcher-agent",
        name="Zoning Knowledge Retriever",
        role="Retrieves authoritative zoning code snippets for the current jurisdiction.",
        model=build_agent_model(model_id_override="gemini-2.5-pro", allow_missing_api_key=True),
        tools=[retrieve_zoning_knowledge],
        instructions=[
            "Use the zoning knowledge tool to find authoritative code passages.",
            "Return only grounded summaries and evidence identifiers.",
        ],
    )


def build_property_specialist_agent() -> Agent:
    return create_agent(
        id="parcel-data-agent",
        name="Property Context Specialist",
        role="Retrieves property-specific parcel context from Gridics.",
        model=build_agent_model(model_id_override="gemini-2.5-flash-lite", allow_missing_api_key=True),
        tools=[get_property_context],
        instructions=[
            "Use coordinates when provided to retrieve property context.",
            "Do not infer parcel facts that were not returned by Gridics.",
        ],
    )


def build_customer_zoning_team() -> Team:
    return Team(
        id="customer_zoning_team",
        name="Lead Zoning Orchestrator",
        description="Coordinates grounded zoning responses across knowledge and property context specialists.",
        model=build_agent_model(model_id_override="gemini-2.5-flash-lite", allow_missing_api_key=True),
        members=[build_code_researcher_agent(), build_property_specialist_agent()],
        db=AGNO_SESSION_KWARGS["db"],
        mode=TeamMode.coordinate,
        add_member_tools_to_context=False,
        add_history_to_context=AGNO_SESSION_KWARGS["add_history_to_context"],
        num_history_runs=AGNO_SESSION_KWARGS["num_history_runs"],
        store_history_messages=AGNO_SESSION_KWARGS["store_history_messages"],
        session_state={"active_property_context": None},
        add_session_state_to_context=True,
        markdown=True,
        instructions=[
            "Route zoning questions to the appropriate specialist.",
            "Keep the conversation within zoning and land use scope.",
            "For parcel questions, use property coordinates when they are available.",
            "Require grounded evidence and references for every substantive answer.",
        ],
        post_hooks=[log_agno_run_metrics],
    )


def build_zoning_chat_orchestrator(
    *,
    agent: Agent | None = None,
    property_service: GridicsPropertyContextService | None = None,
    knowledge_service: ZoningKnowledgeLookupService | None = None,
    grounding_service: GroundingService | None = None,
) -> ZoningChatOrchestrator:
    assistant_agent = build_grounded_answer_agent()
    return ZoningChatOrchestrator(
        composer=AgnoAnswerComposer(assistant_agent),
        property_service=property_service or GridicsPropertyContextService(),
        knowledge_service=knowledge_service or ZoningKnowledgeLookupService(),
        grounding_service=grounding_service or GroundingService(),
    )
