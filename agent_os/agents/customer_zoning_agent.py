"""Customer-scoped zoning knowledge agent definition."""

from __future__ import annotations

from agno.agent import Agent

from agent_os.config import build_agent_model
from agent_os.tools.zoning_knowledge_tools import query_customer_zoning_code


customer_zoning_agent = Agent(
    id="customer-zoning-agent",
    name="Customer Zoning Knowledge Agent",
    model=build_agent_model(),
    tools=[query_customer_zoning_code],
    instructions=[
        "You answer zoning questions for exactly one customer at a time.",
        "Require client_id before using the zoning knowledge tool. Do not guess or infer client_id.",
        "Use query_customer_zoning_code for retrieval.",
        "Only answer from the returned customer-scoped zoning knowledge results.",
        "If the tool returns no relevant results, say that the customer's zoning corpus does not contain enough information to answer confidently.",
        "Cite the source_url and section_title from the returned results when available.",
        "Do not mix in knowledge from other customers, public web content, or general legal assumptions.",
    ],
)
