# Zoning Agent Architecture

`backend/app/agents` now separates the zoning chat flow into small, testable parts:

- `guardrails.py`: conservative zoning-domain classifier.
- `zoning_agent.py`: Agno agent builders plus the deterministic `ZoningChatOrchestrator`.
- `response_policy.py`: prompt loading and safe refusal helpers.
- `prompts/`: system, answer, and refusal policies used by the assistant.

Flow:

1. Run the zoning scope guardrail.
2. Retrieve jurisdiction knowledge.
3. If a property is selected, retrieve normalized parcel context from Gridics.
4. Build a compact evidence bundle.
5. Use Agno structured output to draft the answer.
6. Validate citation coverage and regenerate once if needed.
7. Return a grounded response or a safe insufficient-evidence fallback.

Extension points:

- Replace `GridicsPropertyContextService.adapter` to wire in a different property API.
- Extend `ZoningKnowledgeLookupService` for hybrid or vector+structured retrieval.
- Tighten `GroundingService.validate` if you want stricter claim-to-citation checks.
- Update the prompt text files without changing orchestration code.

