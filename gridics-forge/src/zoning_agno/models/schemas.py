from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    MUNICODE = "municode"
    ECODE360 = "ecode360"
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"


class Citation(BaseModel):
    section_id: str | None = None
    section_title: str | None = None
    quote: str
    source_url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


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
    jurisdiction: str
    source_kind: SourceKind
    source_url: str
    document_title: str | None = None
    effective_date: str | None = None
    sections: list[SourceSection] = Field(default_factory=list)
    tables: list[SourceTable] = Field(default_factory=list)
    definitions: list[DefinedTerm] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class District(BaseModel):
    code: str
    name: str | None = None
    family: DistrictFamily = DistrictFamily.ZONE
    citations: list[Citation] = Field(default_factory=list)


class Condition(BaseModel):
    expression: str
    notes: str | None = None


class UseRule(BaseModel):
    district_code: str
    family: DistrictFamily = DistrictFamily.ZONE
    use_label_id: int | None = None
    use_name: str
    use_value: str | None = None
    conditions: list[Condition] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class GeneralStandard(BaseModel):
    district_code: str
    family: DistrictFamily = DistrictFamily.ZONE
    field_name: str
    db_field_name: str
    data_type: str
    value: str | int | float | bool | None = None
    unit: str | None = None
    conditions: list[Condition] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ParkingRule(BaseModel):
    district_code: str
    family: DistrictFamily = DistrictFamily.ZONE
    field_name: str
    db_field_name: str
    formula_text: str | None = None
    normalized_value: str | int | float | None = None
    citations: list[Citation] = Field(default_factory=list)


class BonusRule(BaseModel):
    district_code: str
    family: DistrictFamily = DistrictFamily.ZONE
    field_name: str
    db_field_name: str
    value: str | int | float | bool | None = None
    citations: list[Citation] = Field(default_factory=list)


class ReviewSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewFlag(BaseModel):
    severity: ReviewSeverity
    family: DistrictFamily | None = None
    district_code: str | None = None
    sheet_name: str
    field_key: str
    issue_type: str
    reason: str
    suggested_action: str
    citations: list[Citation] = Field(default_factory=list)


class WorkbookSheetTemplate(BaseModel):
    name: str
    static_columns: list[str] = Field(default_factory=list)
    dynamic_columns: list[str] = Field(default_factory=list)


class CanonicalWorkbookTemplate(BaseModel):
    sheets: list[WorkbookSheetTemplate] = Field(default_factory=list)


class ExtractionBatch(BaseModel):
    districts: list[District] = Field(default_factory=list)
    general_standards: list[GeneralStandard] = Field(default_factory=list)
    use_rules: list[UseRule] = Field(default_factory=list)
    parking_rules: list[ParkingRule] = Field(default_factory=list)
    bonus_rules: list[BonusRule] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineInput(BaseModel):
    jurisdiction: str
    source_url: str
    source_kind: SourceKind = SourceKind.MUNICODE
    workbook_template_path: str
    source_document_id: int | None = None


class PipelineOutput(BaseModel):
    input: PipelineInput
    source_document: SourceDocument
    extraction: ExtractionBatch
    workbook_output_path: str | None = None
    review_queue_path: str | None = None
    status: Literal["ok", "needs_review", "failed"] = "ok"
