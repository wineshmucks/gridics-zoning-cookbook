"""Experimental zoning agent flow for trialing a simpler Agno team design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agno.team.mode import TeamMode
from agno.team.team import Team

from app.agents.factory import build_agent_model, create_agent
from app.agents.storage import build_agno_session_kwargs, log_agno_run_metrics
from app.services.property_context_service import GridicsPropertyContextService
from app.services.zoning_knowledge_tool_service import ZoningKnowledgeLookupService
from app.tools.gridics_property_tool import get_property_context
from app.tools.zoning_knowledge_tool import retrieve_zoning_knowledge

AGNO_SESSION_KWARGS = build_agno_session_kwargs(enable_history=True)


def _render_property_context_block(property_context: dict[str, Any] | None) -> str:
    if not isinstance(property_context, dict):
        return "No specific property context provided."

    lines: list[str] = []

    # 1. Extract Top-Level Fields from the PropertyContextResult schema
    zoning = property_context.get("zoning_district")
    if zoning:
        lines.append(f"- Zoning District: {zoning}")
        
    flu = property_context.get("future_land_use")
    if flu:
        lines.append(f"- Future Land Use: {flu}")

    overlays = property_context.get("overlays")
    if isinstance(overlays, list) and overlays:
        lines.append(f"- Overlays: {', '.join(overlays)}")
        
    allowed_uses = property_context.get("allowed_uses")
    if isinstance(allowed_uses, list) and allowed_uses:
        lines.append(f"- Allowed Uses: {', '.join(allowed_uses)}")

    height_ft = property_context.get("max_height_ft")
    if height_ft is not None:
        lines.append(f"- Max Height (ft): {height_ft}")
        
    height_st = property_context.get("max_height_stories")
    if height_st is not None:
        lines.append(f"- Max Stories: {height_st}")

    # 2. Extract the dynamic facts_for_prompt
    facts = property_context.get("facts_for_prompt") or []
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            label = str(fact.get("label") or "").strip()
            value = str(fact.get("value") or "").strip()
            if label and value:
                lines.append(f"- {label}: {value}")

    # 3. Extract Status and Missing Fields
    status = str(property_context.get("status") or "").strip()
    if status:
        lines.append(f"- Property data status: {status}")

    missing_fields = property_context.get("missing_fields") or []
    if isinstance(missing_fields, list) and missing_fields:
        rendered_missing = ", ".join(str(item).strip() for item in missing_fields if str(item).strip())
        if rendered_missing:
            lines.append(f"- Missing property fields: {rendered_missing}")

    return "\n".join(lines) if lines else "No specific property context provided."


def build_experimental_zoning_team() -> Team:
    knowledge_agent = create_agent(
        id="experimental-zoning-knowledge-agent",
        name="Zoning Knowledge Specialist",
        role="Search the zoning knowledge base for rules, exceptions, and definitions.",
        model=build_agent_model(model_id_override="gemini-2.5-flash-lite", allow_missing_api_key=True),
        db=AGNO_SESSION_KWARGS["db"],
        tools=[retrieve_zoning_knowledge],
        instructions=[
            "Use the zoning knowledge tool to retrieve authoritative zoning code material.",
            "Return grounded summaries only, and include citations when the tool provides them.",
        ],
        post_hooks=[log_agno_run_metrics],
    )

    # Note: I removed the duplicate return block that was here!
    return Team(
        id="experimental_customer_zoning_team",
        name="Experimental Gridics Zoning Expert Team",
        model=build_agent_model(model_id_override="gemini-2.5-flash-lite", allow_missing_api_key=True),
        members=[knowledge_agent],
        db=AGNO_SESSION_KWARGS["db"],
        mode=TeamMode.coordinate,
        add_member_tools_to_context=False,
        add_history_to_context=AGNO_SESSION_KWARGS["add_history_to_context"],
        num_history_runs=AGNO_SESSION_KWARGS["num_history_runs"],
        store_history_messages=AGNO_SESSION_KWARGS["store_history_messages"],
        markdown=True,
        instructions=[
            "You are an experimental zoning assistant team for zoning and land use questions.",
            "Stay strictly within zoning, land use, setbacks, overlays, allowed uses, parking, and development standards.",
            "Do not answer non-zoning questions.",
            "",
            "---",
            "### RUNTIME CONTEXT",
            "- Jurisdiction: {jurisdiction_name} (ID: {jurisdiction_id})",
            "- Active Property Data:",
            "{property_context}",
            "---",
            "",
            "### RULES FOR ANSWERING",
            "1. Use the Active Property Data as the absolute source of truth for parcel-specific facts.",
            "2. Ground all substantive claims in the provided property data or the outputs of the zoning knowledge tool.",
            "3. Include citations matching the tool outputs.",
            "4. If evidence is thin, state clearly that the information is unavailable instead of guessing.",
        ],
        # post_hooks=[log_agno_run_metrics],
    )


@dataclass(slots=True)
class ExperimentalZoningSession:
    team: Team

    def ask(
        self,
        *,
        question: str,
        jurisdiction_id: str,
        jurisdiction_name: str,
        lat: float | None = None,
        lng: float | None = None,
        address: str | None = None,
        session_id: str | None = None,
    ) -> str:
        property_context: dict[str, Any] | None = None
        if lat is not None and lng is not None:
            property_context = get_property_context(
                lat=lat,
                lng=lng,
                jurisdiction_id=jurisdiction_id,
                jurisdiction_name=jurisdiction_name,
                address=address,
            )

        property_context_block = _render_property_context_block(property_context)
        
        # DEBUG: This will print to your backend log so you can see if the API actually found the property!
        print("\n--- DEBUG: PROPERTY CONTEXT SENT TO AI ---")
        print(property_context_block)
        print("------------------------------------------\n")

        # FIX: Put the context back into the user prompt payload.
        # This ensures the Knowledge Agent can read it when the Team Leader delegates the task.
        payload = (
            f"Jurisdiction: {jurisdiction_name} (ID: {jurisdiction_id})\n"
            f"Active Property Data:\n{property_context_block}\n\n"
            f"User question: {question}"
        )

        response = self.team.run(
            payload,
            session_id=session_id,
        )
        return str(getattr(response, "content", response))


_EXPERIMENTAL_SESSION = ExperimentalZoningSession(team=build_experimental_zoning_team())


def run_experimental_zoning_chat(
    *,
    question: str,
    jurisdiction_id: str,
    jurisdiction_name: str,
    lat: float | None = None,
    lng: float | None = None,
    address: str | None = None,
    session_id: str | None = None,
) -> str:
    print(f"Running experimental zoning chat with question: {question}")
    print(f"Jurisdiction: {jurisdiction_name} ({jurisdiction_id})")
    if lat is not None and lng is not None:
        print(f"Property coordinates: ({lat}, {lng})")
    if address:
        print(f"Property address: {address}")
    return _EXPERIMENTAL_SESSION.ask(
        question=question,
        jurisdiction_id=jurisdiction_id,
        jurisdiction_name=jurisdiction_name,
        lat=lat,
        lng=lng,
        address=address,
        session_id=session_id,
    )
