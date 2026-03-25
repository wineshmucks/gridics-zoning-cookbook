from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class SourceKind(str, Enum):
    MUNICODE = "municode"
    ECODE360 = "ecode360"
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"


AtomicFactType = Literal[
    "use_permission",
    "dimensional_standard",
    "parking_rule",
    "bonus_rule",
    "overlay_modifier",
    "definition",
    "district_metadata",
]


class Citation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    section_id: int | str | None = None
    node_id: str | None = None
    title: str | None = None
    section_title: str | None = Field(default=None, exclude=True)
    quote: str
    source_url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("quote")
    @classmethod
    def _trim_quote(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Citation quote cannot be empty.")
        return normalized

    @computed_field
    @property
    def normalized_title(self) -> str | None:
        return self.title or self.section_title


class SourceSection(BaseModel):
    section_id: str
    title: str
    text: str
    path: list[str] = Field(default_factory=list)
    cross_references: list[str] = Field(default_factory=list)


class SourceTable(BaseModel):
    table_id: str
    title: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
    source_section_id: str | None = None


class DefinedTerm(BaseModel):
    term: str
    definition: str
    citations: list[Citation] = Field(default_factory=list)


class SourceDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    jurisdiction: str
    source_type: SourceKind = Field(default=SourceKind.MUNICODE, alias="source_kind")
    source_file_name: str | None = None
    source_url: str
    imported_at: datetime | None = None
    document_title: str | None = None
    effective_date: str | None = None
    sections: list[SourceSection] = Field(default_factory=list)
    tables: list[SourceTable] = Field(default_factory=list)
    definitions: list[DefinedTerm] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def source_kind(self) -> SourceKind:
        return self.source_type


class MuniNode(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    row_number: int
    node_id: str | None = None
    url: str | None = None
    title: str | None = None
    subtitle: str | None = None
    content: str | None = None
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)


class LegalSection(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    node_id: str | None = None
    section_path: str
    title: str | None = None
    subtitle: str | None = None
    body_text: str
    section_type: str = "section"
    parent_section_id: int | None = None


class LegalChunk(BaseModel):
    id: int | None = None
    legal_section_id: int | None = None
    source_document_id: int | None = None
    node_id: str | None = None
    chunk_index: int = 0
    chunk_type: str = "section_text"
    chunk_text: str
    token_estimate: int | None = None
    title: str | None = None
    subtitle: str | None = None
    section_path: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class SourceChunk(BaseModel):
    chunk_id: str
    title: str
    kind: str
    text: str
    source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DistrictFamily(str, Enum):
    ZONE = "zone"
    OVERLAY = "overlay"
    TYPOLOGY = "typology"


class DistrictRecord(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    district_code: str
    district_name: str | None = None
    family: DistrictFamily = DistrictFamily.ZONE
    citations: list[Citation] = Field(default_factory=list, alias="citations_json")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DistrictRegistryRecord(BaseModel):
    """Canonical district entry used to build district-pivoted Gridics workbook columns."""

    district_code: str
    district_name: str | None = None
    district_family: str | None = None
    source_node_id: str | None = None
    source_title: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Condition(BaseModel):
    expression: str
    notes: str | None = None


class UseRuleRecord(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    district_code: str
    use_key: str | None = None
    use_label: str | None = None
    allowance: str | None = None
    conditions_json: list[Condition] = Field(default_factory=list)
    exceptions_json: list[str] = Field(default_factory=list)
    citations_json: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GeneralStandardRecord(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    district_code: str
    field_name: str
    value_text: str | None = None
    value_numeric: float | None = None
    unit: str | None = None
    operator: str | None = None
    conditions_json: list[Condition] = Field(default_factory=list)
    exceptions_json: list[str] = Field(default_factory=list)
    citations_json: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ParkingRuleRecord(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    district_code: str | None = None
    use_key: str | None = None
    rule_text: str
    formula_json: dict[str, Any] = Field(default_factory=dict)
    citations_json: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AtomicZoningFact(BaseModel):
    """Atomic zoning fact used as the stable layer between legal extraction and workbook pivots."""

    fact_id: str
    source_document_id: str | None = None
    node_id: str | None = None
    section_path: str | None = None
    fact_type: AtomicFactType
    district_code: str | None = None
    overlay_code: str | None = None
    use_key: str | None = None
    field_name: str | None = None
    value_text: str | None = None
    value_numeric: float | None = None
    value_json: dict[str, Any] | None = None
    operator: str | None = None
    unit: str | None = None
    condition_text: str | None = None
    exception_text: str | None = None
    applicability_text: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_human_review: bool = False


class PivotRow(BaseModel):
    """One logical Gridics matrix row with district codes as dynamic columns."""

    output_sheet: str
    row_key: str
    row_label: str
    row_metadata: dict[str, Any] = Field(default_factory=dict)
    district_values: dict[str, Any] = Field(default_factory=dict)
    citations_by_district: dict[str, list[Citation]] = Field(default_factory=dict)


class DistrictRegistryBundle(BaseModel):
    """Ordered district registry used to pivot legal facts into Gridics workbook columns."""

    districts: list[DistrictRegistryRecord] = Field(default_factory=list)


class AtomicFactBundle(BaseModel):
    """Normalized atomic facts that sit between legal extraction and district-pivoted workbook export."""

    facts: list[AtomicZoningFact] = Field(default_factory=list)


class PivotTableBundle(BaseModel):
    """District-pivoted workbook sheet representation; not a row-for-row source extraction."""

    sheet_name: str
    district_codes: list[str] = Field(default_factory=list)
    rows: list[PivotRow] = Field(default_factory=list)


class TemplateSheetHeader(BaseModel):
    """Canonical template header for a Gridics output sheet, preserving fixed and district columns exactly."""

    sheet_name: str
    fixed_headers: list[str] = Field(default_factory=list)
    district_headers: list[str] = Field(default_factory=list)


class TemplateRow(BaseModel):
    """Represents one canonical output row from the Gridics template. Columns A, B, and C are preserved exactly from the template."""

    sheet_name: str
    row_index: int
    key: str
    col_a: str | int | None = None
    col_b: str | int | None = None
    col_c: str | int | None = None
    raw_values: dict[str, Any] = Field(default_factory=dict)


class TemplateSheet(BaseModel):
    """One Gridics template sheet with preserved header structure and canonical row order."""

    sheet_name: str
    header: TemplateSheetHeader
    rows: list[TemplateRow] = Field(default_factory=list)


class CellPopulation(BaseModel):
    """One populated district cell mapped onto an existing Gridics template row."""

    sheet_name: str
    row_key: str
    district_code: str
    value: Any
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_fact_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = False


class SheetPopulationBundle(BaseModel):
    """Template-row cell population set for one sheet; structure comes from the workbook template, not the extractor."""

    sheet_name: str
    row_keys: list[str] = Field(default_factory=list)
    district_codes: list[str] = Field(default_factory=list)
    populated_cells: list[CellPopulation] = Field(default_factory=list)


class UseLabelInterpretation(BaseModel):
    """Typed interpretation of one unresolved source use label against the template use catalog."""

    source_label: str
    matched_use_names: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None


class UseLabelInterpretationBundle(BaseModel):
    """Bundle of narrow label-interpretation results for ambiguous source use concepts."""

    interpretations: list[UseLabelInterpretation] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    legal_chunk_id: int | None = None
    legal_section_id: int | None = None
    node_id: str | None = None
    title: str | None = None
    subtitle: str | None = None
    section_path: str | None = None
    chunk_type: str | None = None
    chunk_text: str
    score: float
    retrieval_mode: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalBundle(BaseModel):
    query: str
    hits: list[RetrievalHit] = Field(default_factory=list)
    expanded_context: list[RetrievalHit] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewFlag(BaseModel):
    id: int | None = None
    source_document_id: int | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    severity: ReviewSeverity
    issue_type: str
    message: str | None = None
    citations_json: list[Citation] = Field(default_factory=list)
    status: str = "open"
    created_at: datetime | None = None

    family: DistrictFamily | None = None
    district_code: str | None = None
    sheet_name: str = "workflow"
    field_key: str = "unknown"
    reason: str | None = None
    suggested_action: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def _fill_message(cls, value: str | None, info) -> str | None:
        if value:
            return value
        data = info.data
        return data.get("reason")


class WorkbookSheetTemplate(BaseModel):
    name: str
    static_columns: list[str] = Field(default_factory=list)
    dynamic_columns: list[str] = Field(default_factory=list)


class CanonicalWorkbookTemplate(BaseModel):
    sheets: list[WorkbookSheetTemplate] = Field(default_factory=list)


class ExtractionBatch(BaseModel):
    districts: list[DistrictRecord] = Field(default_factory=list)
    general_standards: list[GeneralStandardRecord] = Field(default_factory=list)
    use_rules: list[UseRuleRecord] = Field(default_factory=list)
    parking_rules: list[ParkingRuleRecord] = Field(default_factory=list)
    bonus_rules: list[dict[str, Any]] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineInput(BaseModel):
    jurisdiction: str
    source_url: str
    source_kind: SourceKind = SourceKind.MUNICODE
    workbook_template_path: str


class PipelineOutput(BaseModel):
    input: PipelineInput
    source_document: SourceDocument
    extraction: ExtractionBatch
    workbook_output_path: str | None = None
    review_queue_path: str | None = None
    retrieval_bundle: RetrievalBundle | None = None
    status: Literal["ok", "needs_review", "failed"] = "ok"


# Compatibility aliases for the existing codebase.
District = DistrictRecord
UseRule = UseRuleRecord
GeneralStandard = GeneralStandardRecord
ParkingRule = ParkingRuleRecord
