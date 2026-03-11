"""Customer-scoped zoning knowledge agent."""

from __future__ import annotations

from app.agents.factory import build_agent_model, create_agent
from app.agents.tools import query_customer_zoning_code


customer_zoning_agent = create_agent(
    id="customer-zoning-agent",
    name="Customer Zoning Knowledge Agent",
    model=build_agent_model(),
    markdown=True,
    add_dependencies_to_context=True,
    tools=[query_customer_zoning_code],
    instructions=[
        "Answer zoning questions for exactly one customer at a time.",
        "If runtime dependencies include client_id, treat the run as already bound to that customer.",
        "Only ask the user for client_id when the run is not already bound to a customer.",
        "Use query_customer_zoning_code to retrieve customer-scoped zoning knowledge before answering.",
        "Answer only from the returned customer-scoped results.",
        "If the returned results are insufficient, say so plainly.",
        "Cite source_url and section_title when they are available in the tool results.",
    ],
)
