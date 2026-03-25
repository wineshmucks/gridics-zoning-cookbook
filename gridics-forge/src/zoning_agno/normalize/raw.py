from __future__ import annotations

from pydantic import BaseModel, Field

from zoning_agno.schemas import MuniNode


class NormalizedNodeText(BaseModel):
    node_id: str | None = None
    title: str | None = None
    subtitle: str | None = None
    body_text: str = ""
    section_path_hint: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class MuniNodeNormalizer:
    """Prepare raw workbook rows for later legal-section normalization."""

    def normalize(self, node: MuniNode) -> NormalizedNodeText:
        section_path_hint = [part for part in [node.title, node.subtitle] if part]
        return NormalizedNodeText(
            node_id=node.node_id,
            title=node.title,
            subtitle=node.subtitle,
            body_text=node.content or "",
            section_path_hint=section_path_hint,
            metadata={
                "row_number": str(node.row_number),
                "url": node.url or "",
            },
        )
