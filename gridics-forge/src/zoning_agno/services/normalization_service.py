from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from zoning_agno.db.models import (
    LegalChunkORM,
    LegalCrossrefORM,
    LegalDefinitionORM,
    LegalSectionORM,
    MuniNodeORM,
)
from zoning_agno.normalize import chunk_sections, extract_cross_references, extract_definitions, normalize_sections
from zoning_agno.schemas import MuniNode


@dataclass(slots=True)
class NormalizationStats:
    source_document_id: int
    section_count: int
    chunk_count: int
    definition_count: int
    crossref_count: int


def _load_muni_nodes(session: Session, source_document_id: int) -> list[MuniNode]:
    rows = session.scalars(
        select(MuniNodeORM).where(MuniNodeORM.source_document_id == source_document_id).order_by(MuniNodeORM.row_number)
    ).all()
    return [
        MuniNode(
            id=row.id,
            source_document_id=row.source_document_id,
            row_number=row.row_number,
            node_id=row.node_id,
            url=row.url,
            title=row.title,
            subtitle=row.subtitle,
            content=row.content,
            raw_payload_json=row.raw_payload_json,
        )
        for row in rows
    ]


def _clear_existing_normalized_rows(session: Session, source_document_id: int) -> None:
    """Remove previously normalized artifacts so reruns are idempotent for a source document."""
    session.execute(delete(LegalCrossrefORM).where(LegalCrossrefORM.source_document_id == source_document_id))
    session.execute(delete(LegalDefinitionORM).where(LegalDefinitionORM.source_document_id == source_document_id))
    session.execute(delete(LegalChunkORM).where(LegalChunkORM.source_document_id == source_document_id))
    session.execute(delete(LegalSectionORM).where(LegalSectionORM.source_document_id == source_document_id))
    session.flush()


def normalize_source_document(session: Session, source_document_id: int) -> NormalizationStats:
    """Normalize raw Municode nodes into legal sections, chunks, cross-references, and definitions."""
    nodes = _load_muni_nodes(session, source_document_id)
    _clear_existing_normalized_rows(session, source_document_id)
    sections = normalize_sections(nodes, source_document_id=source_document_id)
    temp_parent_ids = {section.id: section.parent_section_id for section in sections}

    persisted_sections: list[tuple[int, LegalSectionORM]] = []
    for section in sections:
        temp_id = int(section.id or 0)
        record = LegalSectionORM(
            source_document_id=source_document_id,
            node_id=section.node_id,
            section_path=section.section_path,
            title=section.title,
            subtitle=section.subtitle,
            body_text=section.body_text,
            section_type=section.section_type,
            parent_section_id=None,
        )
        session.add(record)
        persisted_sections.append((temp_id, record))
    session.flush()

    persisted_id_by_temp_id = {temp_id: record.id for temp_id, record in persisted_sections}
    section_id_by_node_id = {
        section.node_id: record.id for section, (temp_id, record) in zip(sections, persisted_sections, strict=False)
    }
    for section, (temp_id, record) in zip(sections, persisted_sections, strict=False):
        section.id = record.id
        temp_parent_id = temp_parent_ids.get(temp_id)
        if temp_parent_id is None:
            continue
        record.parent_section_id = persisted_id_by_temp_id.get(temp_parent_id)
        session.add(record)

    chunks = chunk_sections(sections)
    for chunk in chunks:
        session.add(
            LegalChunkORM(
                legal_section_id=chunk.legal_section_id,
                source_document_id=source_document_id,
                node_id=chunk.node_id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                chunk_text=chunk.chunk_text,
                token_estimate=chunk.token_estimate,
                title=chunk.title,
                subtitle=chunk.subtitle,
                section_path=chunk.section_path,
                metadata_json=chunk.metadata_json,
            )
        )

    definitions = extract_definitions(sections)
    for definition in definitions:
        session.add(
            LegalDefinitionORM(
                source_document_id=source_document_id,
                term=str(definition["term"]),
                definition_text=str(definition["definition_text"]),
                section_id=definition["section_id"],
                node_id=definition["node_id"],
            )
        )

    crossref_count = 0
    for section in sections:
        from_section_id = section_id_by_node_id.get(section.node_id)
        for ref in extract_cross_references(section.body_text):
            session.add(
                LegalCrossrefORM(
                    source_document_id=source_document_id,
                    from_section_id=from_section_id or section.id,
                    to_section_ref=ref,
                    to_section_id=None,
                    ref_text=ref,
                )
            )
            crossref_count += 1

    session.commit()
    return NormalizationStats(
        source_document_id=source_document_id,
        section_count=len(sections),
        chunk_count=len(chunks),
        definition_count=len(definitions),
        crossref_count=crossref_count,
    )
