from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from zoning_agno.db.base import Base


class _JSONVariant(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        from sqlalchemy import JSON

        return dialect.type_descriptor(JSON())


try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:
    PgVector = None


JsonType = _JSONVariant


class EmbeddingVectorType(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def __init__(self, dimensions: int | None = None) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PgVector is not None:
            return dialect.type_descriptor(PgVector(self.dimensions) if self.dimensions else PgVector())
        from sqlalchemy import JSON

        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, tuple):
            value = list(value)
        return value

    def process_result_value(self, value: Any, dialect):
        return value


class SourceDocumentORM(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_file_name: Mapped[str | None] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    muni_nodes: Mapped[list["MuniNodeORM"]] = relationship(back_populates="source_document")


class MuniNodeORM(Base):
    __tablename__ = "muni_nodes"
    __table_args__ = (
        UniqueConstraint("source_document_id", "row_number", name="uq_muni_nodes_source_document_row_number"),
        Index("ix_muni_nodes_source_document_id_node_id", "source_document_id", "node_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)

    source_document: Mapped[SourceDocumentORM] = relationship(back_populates="muni_nodes")


class LegalSectionORM(Base):
    __tablename__ = "legal_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    section_path: Mapped[str] = mapped_column(Text, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_type: Mapped[str] = mapped_column(String(100), nullable=False, default="section")
    parent_section_id: Mapped[int | None] = mapped_column(ForeignKey("legal_sections.id", ondelete="SET NULL"))


class LegalChunkORM(Base):
    __tablename__ = "legal_chunks"
    __table_args__ = (
        UniqueConstraint("legal_section_id", "chunk_index", name="uq_legal_chunks_section_chunk_index"),
        Index("ix_legal_chunks_source_document_id_section_path", "source_document_id", "section_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legal_section_id: Mapped[int] = mapped_column(ForeignKey("legal_sections.id", ondelete="CASCADE"), index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(100), nullable=False, default="section_text")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text)
    section_path: Mapped[str | None] = mapped_column(Text, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)


class LegalCrossrefORM(Base):
    __tablename__ = "legal_crossrefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    from_section_id: Mapped[int] = mapped_column(ForeignKey("legal_sections.id", ondelete="CASCADE"), index=True)
    to_section_ref: Mapped[str] = mapped_column(Text, nullable=False)
    to_section_id: Mapped[int | None] = mapped_column(ForeignKey("legal_sections.id", ondelete="SET NULL"))
    ref_text: Mapped[str] = mapped_column(Text, nullable=False)


class LegalDefinitionORM(Base):
    __tablename__ = "legal_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    definition_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("legal_sections.id", ondelete="SET NULL"), index=True)
    node_id: Mapped[str | None] = mapped_column(String(255), index=True)


class LegalChunkEmbeddingORM(Base):
    __tablename__ = "legal_chunk_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legal_chunk_id: Mapped[int] = mapped_column(ForeignKey("legal_chunks.id", ondelete="CASCADE"), unique=True, index=True)
    embedding: Mapped[Any] = mapped_column(EmbeddingVectorType(), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ZoningDistrictORM(Base):
    __tablename__ = "zoning_districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    district_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    district_name: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(String(50), index=True)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float)


class ZoningUseRuleORM(Base):
    __tablename__ = "zoning_use_rules"
    __table_args__ = (Index("ix_zoning_use_rules_source_document_district_use", "source_document_id", "district_code", "use_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    district_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    use_key: Mapped[str | None] = mapped_column(String(255), index=True)
    use_label: Mapped[str | None] = mapped_column(Text)
    allowance: Mapped[str | None] = mapped_column(String(64))
    conditions_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    exceptions_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float)


class ZoningGeneralStandardORM(Base):
    __tablename__ = "zoning_general_standards"
    __table_args__ = (
        Index(
            "ix_zoning_general_standards_source_document_district_field",
            "source_document_id",
            "district_code",
            "field_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    district_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(64))
    operator: Mapped[str | None] = mapped_column(String(32))
    conditions_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    exceptions_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float)


class ZoningParkingRuleORM(Base):
    __tablename__ = "zoning_parking_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    district_code: Mapped[str | None] = mapped_column(String(128), index=True)
    use_key: Mapped[str | None] = mapped_column(String(255), index=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    formula_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float)


class ReviewFlagORM(Base):
    __tablename__ = "review_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
