"""Admin and configuration schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeeScheduleCreate(BaseModel):
    jurisdiction_id: str
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(pattern="^(draft|active|retired)$")
    effective_start_at: datetime | None = None
    effective_end_at: datetime | None = None
    created_by_user_id: str | None = None


class FeeScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    jurisdiction_id: str
    name: str
    status: str
    effective_start_at: datetime | None
    effective_end_at: datetime | None
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class FeeScheduleItemCreate(BaseModel):
    fee_schedule_id: str
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="general", min_length=1, max_length=50)
    fee_type: str = Field(min_length=1, max_length=50)
    description: str | None = None
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    applies_to_letter_type: str | None = Field(default=None, max_length=50)
    applies_to_processing_type: str | None = Field(default=None, max_length=50)
    applies_to_delivery_method: str | None = Field(default=None, max_length=50)
    tax_mode: str | None = Field(default=None, max_length=50)
    charge_unit: str | None = Field(default=None, max_length=50)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    metadata_json: dict | None = None


class FeeScheduleItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    fee_schedule_id: str
    code: str
    name: str
    category: str
    fee_type: str
    description: str | None
    amount_cents: int
    currency: str
    applies_to_letter_type: str | None
    applies_to_processing_type: str | None
    applies_to_delivery_method: str | None
    tax_mode: str | None
    charge_unit: str | None
    display_order: int
    is_active: bool
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime


class FeeStructureClientContextRead(BaseModel):
    id: str
    client_id: str
    clerk_organization_id: str | None
    city_name: str
    department_name: str
    jurisdiction_id: str


class FeeStructureItemUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=50)
    fee_type: str = Field(min_length=1, max_length=50)
    description: str | None = None
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    applies_to_letter_type: str | None = Field(default=None, max_length=50)
    applies_to_processing_type: str | None = Field(default=None, max_length=50)
    applies_to_delivery_method: str | None = Field(default=None, max_length=50)
    tax_mode: str | None = Field(default=None, max_length=50)
    charge_unit: str | None = Field(default=None, max_length=50)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    metadata_json: dict | None = None


class FeeStructureUpsert(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    items: list[FeeStructureItemUpsert] = Field(min_length=1)


class FeeStructureResponse(BaseModel):
    client: FeeStructureClientContextRead
    schedule: FeeScheduleRead
    items: list[FeeScheduleItemRead]


class LetterTemplateCreate(BaseModel):
    jurisdiction_id: str
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    letter_type: str = Field(pattern="^(standard|comprehensive)$")
    status: str = Field(pattern="^(draft|active|archived)$")
    template_body: str = Field(min_length=1)
    merge_variables_json: list | dict | None = None
    version: int = Field(default=1, ge=1)
    created_by_user_id: str | None = None


class LetterTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    jurisdiction_id: str
    code: str
    name: str
    letter_type: str
    status: str
    template_body: str
    merge_variables_json: list | dict | None
    version: int
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class EmailTemplateClientContextRead(BaseModel):
    id: str
    client_id: str
    clerk_organization_id: str | None
    city_name: str
    department_name: str


class EmailTemplateOverrideUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str = Field(default="request_updates", min_length=1, max_length=100)
    subject_template: str = Field(min_length=1)
    body_template: str = Field(min_length=1)
    status: str = Field(pattern="^(draft|active|inactive)$")


class EmailTemplateEffectiveRead(BaseModel):
    id: str
    code: str
    trigger_state: str
    name: str
    description: str | None
    category: str
    subject_template: str
    body_template: str
    status: str
    version: int
    owner_organization_id: str | None
    default_template_id: str
    override_template_id: str | None
    is_override: bool
    updated_at: datetime


class EmailTemplatesResponse(BaseModel):
    client: EmailTemplateClientContextRead
    templates: list[EmailTemplateEffectiveRead]


class HomePageClientContextRead(BaseModel):
    id: str
    client_id: str
    clerk_organization_id: str | None
    city_name: str
    department_name: str
    jurisdiction_id: str


class HomePageHeroStat(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=100)
    icon: str = Field(min_length=1, max_length=10)


class HomePageHero(BaseModel):
    badge: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(min_length=1, max_length=2000)
    primary_button_text: str = Field(min_length=1, max_length=100)
    secondary_button_text: str = Field(min_length=1, max_length=100)
    learn_more_text: str = Field(min_length=1, max_length=100)
    stats: list[HomePageHeroStat] = Field(min_length=1, max_length=3)


class HomePageServiceItem(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)
    processing_time: str = Field(min_length=1, max_length=100)
    fee: str = Field(min_length=1, max_length=100)


class HomePageAbout(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=2000)


class HomePageFaqItem(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=255)
    answer: str = Field(min_length=1, max_length=2000)


class HomePageContact(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=2000)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)


class HomePageContentUpsert(BaseModel):
    hero: HomePageHero
    services: list[HomePageServiceItem] = Field(min_length=1, max_length=12)
    about: HomePageAbout
    faq: list[HomePageFaqItem] = Field(min_length=1, max_length=12)
    contact: HomePageContact


class HomePageContentResponse(BaseModel):
    client: HomePageClientContextRead
    content: HomePageContentUpsert


class TenantClientCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    clerk_organization_id: str = Field(min_length=1, max_length=255)
    city_name: str = Field(min_length=1, max_length=255)
    department_name: str = Field(min_length=1, max_length=255, default="Planning & Zoning Department")
    jurisdiction_id: str | None = None
    market: str | None = Field(default=None, max_length=255)
    standard_letter_fee_cents: int = Field(default=0, ge=0)
    comprehensive_letter_fee_cents: int = Field(default=0, ge=0)
    expedited_fee_cents: int = Field(default=0, ge=0)
    support_phone: str | None = Field(default=None, max_length=50)
    support_email: str | None = Field(default=None, max_length=255)
    contact_address: str | None = Field(default=None, max_length=255)
    settings_json: dict | None = None


class TenantClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    clerk_organization_id: str | None
    jurisdiction_id: str | None
    city_name: str
    department_name: str
    standard_letter_fee_cents: int
    comprehensive_letter_fee_cents: int
    expedited_fee_cents: int
    support_phone: str | None
    support_email: str | None
    contact_address: str | None
    is_active: bool
    settings_json: dict | None
    logo_path: str | None = None
    logo_source: str | None = None
    created_at: datetime
    updated_at: datetime


class TenantClientUpdate(BaseModel):
    client_id: str | None = Field(default=None, min_length=1, max_length=255)
    city_name: str | None = Field(default=None, min_length=1, max_length=255)
    department_name: str | None = Field(default=None, min_length=1, max_length=255)
    clerk_organization_id: str | None = Field(default=None, min_length=1, max_length=255)
    clerk_slug: str | None = Field(default=None, min_length=1, max_length=255)
    path_alias: str | None = Field(default=None, max_length=255)
    market: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class TenantExperienceSettingsRead(BaseModel):
    zoning_code_url: str | None
    assistant_disclaimer_text: str
    assistant_provider_keys: dict[str, str | None] = Field(default_factory=dict)
    assistant_agent_prompts: dict[str, str] = Field(default_factory=dict)
    raw_settings_json: dict | None = None
    debug_received_assistant_provider_keys: dict[str, str | None] | None = None
    debug_received_assistant_agent_prompts: dict[str, str | None] | None = None
    debug_merged_settings_json: dict | None = None


class TenantExperienceSettingsUpdate(BaseModel):
    zoning_code_url: str | None = Field(default=None, max_length=2000)
    assistant_disclaimer_text: str | None = Field(default=None, max_length=8000)
    assistant_provider_keys: dict[str, str | None] = Field(default_factory=dict)
    assistant_agent_prompts: dict[str, str | None] = Field(default_factory=dict)


class PlatformAssistantSettingsRead(BaseModel):
    assistant_disclaimer_text: str
    assistant_provider_keys: dict[str, str | None] = Field(default_factory=dict)
    assistant_agent_prompts: dict[str, str] = Field(default_factory=dict)
    raw_settings_json: dict | None = None


class PlatformAssistantSettingsUpdate(BaseModel):
    assistant_disclaimer_text: str | None = Field(default=None, max_length=8000)
    assistant_provider_keys: dict[str, str | None] = Field(default_factory=dict)
    assistant_agent_prompts: dict[str, str | None] = Field(default_factory=dict)


class DatabaseTableSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table_name: str
    row_count: int
    size_bytes: int | None = None
    size_label: str | None = None


class DanglingTableSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table_name: str
    dangling_rows: int
    sample_ids: list[str] = Field(default_factory=list)


class DatabaseInfoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    database_name: str | None = None
    total_size_bytes: int | None = None
    total_size_label: str | None = None
    tables: list[DatabaseTableSummaryRead]
    agno_tables: list[DatabaseTableSummaryRead] = Field(default_factory=list)
    dangling_tables: list[DanglingTableSummaryRead]


class DatabaseCleanupTableResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table_name: str
    deleted_rows: int


class DatabaseCleanupResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deleted_rows_total: int
    deleted_by_table: list[DatabaseCleanupTableResultRead]
    database_info: DatabaseInfoRead


class ZoningKnowledgeLatestRunRead(BaseModel):
    id: str
    mode: str
    status: str
    source_url: str
    pages_crawled: int
    documents_extracted: int
    sections_extracted: int
    chunks_upserted: int
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class ZoningKnowledgeStatusRead(BaseModel):
    client_id: str
    zoning_code_url: str | None
    embedder_provider: str
    embedder_model_id: str
    embedder_dimensions: int
    progress_percent: float
    progress_message: str
    is_complete: bool
    documents: int
    sections: int
    chunks: int
    latest_run: ZoningKnowledgeLatestRunRead | None


class ZoningKnowledgeIngestRequest(BaseModel):
    mode: str = Field(pattern="^(ingest|reindex)$")


class ZoningKnowledgeQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class ZoningKnowledgeQueryResultRead(BaseModel):
    content: str
    name: str | None
    meta_data: dict | None
    page_url: str | None = None
    section_url: str | None = None
    source_title: str | None = None
    source_anchor: str | None = None
    source_url: str | None = None


class ZoningKnowledgeQueryResponse(BaseModel):
    query: str
    results: list[ZoningKnowledgeQueryResultRead]
