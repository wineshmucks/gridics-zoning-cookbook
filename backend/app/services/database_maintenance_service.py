"""Database inspection and dangling-record maintenance helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, delete, exists, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AssistantMessageFeedback,
    AssistantRunTelemetry,
    AssistantTurnEvent,
    Base,
    Delivery,
    EmailEvent,
    EmailTemplate,
    FeeSchedule,
    FeeScheduleItem,
    Jurisdiction,
    JurisdictionHomePageContent,
    LetterDraft,
    LetterTemplate,
    LetterVersion,
    Payment,
    PaymentEvent,
    Property,
    PropertySnapshot,
    Quote,
    Request,
    RequestAssignment,
    RequestNote,
    RequestStatusEvent,
    TenantClient,
    TenantDomain,
    ZoningCodeDocument,
    ZoningCodeIngestionRun,
    ZoningCodeSection,
)


@dataclass(frozen=True)
class DatabaseTableSummary:
    table_name: str
    row_count: int
    size_bytes: int | None
    size_label: str | None


@dataclass(frozen=True)
class DanglingTableSummary:
    table_name: str
    dangling_rows: int
    sample_ids: list[str]


@dataclass(frozen=True)
class DatabaseCleanupTableResult:
    table_name: str
    deleted_rows: int


@dataclass(frozen=True)
class DatabaseInfo:
    database_name: str | None
    total_size_bytes: int | None
    total_size_label: str | None
    tables: list[DatabaseTableSummary]
    dangling_tables: list[DanglingTableSummary]


@dataclass(frozen=True)
class DatabaseCleanupResult:
    deleted_rows_total: int
    deleted_by_table: list[DatabaseCleanupTableResult]
    database_info: DatabaseInfo


def _humanize_size(value: int | None) -> str | None:
    if value is None:
        return None

    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0

    return None


def _table_name(table) -> str:
    return table.name


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind and bind.dialect.name == "postgresql")


def _table_row_count(db: Session, table) -> int:
    return int(db.scalar(select(func.count()).select_from(table)) or 0)


def _table_size_bytes(db: Session, table) -> int | None:
    if not _is_postgres(db):
        return None

    size = db.scalar(select(func.pg_total_relation_size(func.to_regclass(table.fullname))))
    return int(size) if size is not None else None


def _database_total_size_bytes(db: Session) -> int | None:
    if not _is_postgres(db):
        return None

    size = db.scalar(select(func.pg_database_size(func.current_database())))
    return int(size) if size is not None else None


def _dangling_jurisdiction_condition(table):
    return and_(
        table.c.jurisdiction_id.is_not(None),
        ~exists(select(1).select_from(Jurisdiction).where(Jurisdiction.id == table.c.jurisdiction_id)),
    )


def _collect_ids(db: Session, table, condition) -> set[str]:
    if condition is None:
        return set()
    return set(db.scalars(select(table.c.id).where(condition)).all())


def _delete_by_ids(db: Session, table, ids: set[str]) -> int:
    if not ids:
        return 0
    db.execute(delete(table).where(table.c.id.in_(ids)))
    return len(ids)


def _dangling_summary(db: Session, table, sample_limit: int = 5) -> DanglingTableSummary | None:
    if "jurisdiction_id" not in table.c:
        return None

    condition = _dangling_jurisdiction_condition(table)
    rows = db.scalars(select(table.c.id).where(condition).order_by(table.c.id.asc())).all()
    if not rows:
        return None

    return DanglingTableSummary(
        table_name=_table_name(table),
        dangling_rows=len(rows),
        sample_ids=list(rows[:sample_limit]),
    )


def get_database_info(db: Session) -> DatabaseInfo:
    tables: list[DatabaseTableSummary] = []
    for table in sorted(Base.metadata.tables.values(), key=lambda item: item.name):
        size_bytes = _table_size_bytes(db, table)
        tables.append(
            DatabaseTableSummary(
                table_name=_table_name(table),
                row_count=_table_row_count(db, table),
                size_bytes=size_bytes,
                size_label=_humanize_size(size_bytes),
            )
        )
    tables.sort(key=lambda item: ((item.size_bytes or 0) * -1, item.table_name))

    dangling_tables = [
        summary
        for table in (
            TenantClient.__table__,
            Property.__table__,
            Request.__table__,
            FeeSchedule.__table__,
            LetterTemplate.__table__,
            EmailTemplate.__table__,
            JurisdictionHomePageContent.__table__,
        )
        if (summary := _dangling_summary(db, table)) is not None
    ]

    bind = db.get_bind()
    database_name = bind.url.database if bind and getattr(bind, "url", None) else None

    return DatabaseInfo(
        database_name=database_name,
        total_size_bytes=_database_total_size_bytes(db),
        total_size_label=_humanize_size(_database_total_size_bytes(db)),
        tables=tables,
        dangling_tables=dangling_tables,
    )


def cleanup_dangling_records(db: Session) -> DatabaseCleanupResult:
    tenant_ids = _collect_ids(
        db,
        TenantClient.__table__,
        _dangling_jurisdiction_condition(TenantClient.__table__),
    )
    property_ids = _collect_ids(
        db,
        Property.__table__,
        _dangling_jurisdiction_condition(Property.__table__),
    )
    request_ids = _collect_ids(
        db,
        Request.__table__,
        _dangling_jurisdiction_condition(Request.__table__),
    )
    fee_schedule_ids = _collect_ids(
        db,
        FeeSchedule.__table__,
        _dangling_jurisdiction_condition(FeeSchedule.__table__),
    )
    letter_template_ids = _collect_ids(
        db,
        LetterTemplate.__table__,
        _dangling_jurisdiction_condition(LetterTemplate.__table__),
    )
    email_template_ids = _collect_ids(
        db,
        EmailTemplate.__table__,
        _dangling_jurisdiction_condition(EmailTemplate.__table__),
    )
    email_template_tenant_ids = _collect_ids(
        db,
        EmailTemplate.__table__,
        EmailTemplate.__table__.c.tenant_client_id.in_(tenant_ids),
    )
    homepage_ids = _collect_ids(
        db,
        JurisdictionHomePageContent.__table__,
        _dangling_jurisdiction_condition(JurisdictionHomePageContent.__table__),
    )

    property_snapshot_ids = _collect_ids(
        db,
        PropertySnapshot.__table__,
        PropertySnapshot.__table__.c.property_id.in_(property_ids),
    )
    request_ids_from_property = _collect_ids(
        db,
        Request.__table__,
        Request.__table__.c.property_id.in_(property_ids) | Request.__table__.c.property_snapshot_id.in_(property_snapshot_ids),
    )
    request_ids_all = request_ids | request_ids_from_property

    zoning_run_ids = _collect_ids(
        db,
        ZoningCodeIngestionRun.__table__,
        ZoningCodeIngestionRun.__table__.c.tenant_client_id.in_(tenant_ids),
    )
    zoning_document_ids = _collect_ids(
        db,
        ZoningCodeDocument.__table__,
        ZoningCodeDocument.__table__.c.tenant_client_id.in_(tenant_ids)
        | ZoningCodeDocument.__table__.c.ingestion_run_id.in_(zoning_run_ids),
    )
    zoning_section_ids = _collect_ids(
        db,
        ZoningCodeSection.__table__,
        ZoningCodeSection.__table__.c.tenant_client_id.in_(tenant_ids)
        | ZoningCodeSection.__table__.c.ingestion_run_id.in_(zoning_run_ids)
        | ZoningCodeSection.__table__.c.document_id.in_(zoning_document_ids),
    )
    tenant_domain_ids = _collect_ids(
        db,
        TenantDomain.__table__,
        TenantDomain.__table__.c.tenant_client_id.in_(tenant_ids),
    )
    assistant_feedback_ids = _collect_ids(
        db,
        AssistantMessageFeedback.__table__,
        AssistantMessageFeedback.__table__.c.tenant_client_id.in_(tenant_ids),
    )
    assistant_turn_event_ids = _collect_ids(
        db,
        AssistantTurnEvent.__table__,
        AssistantTurnEvent.__table__.c.tenant_client_id.in_(tenant_ids),
    )
    assistant_run_ids = _collect_ids(
        db,
        AssistantRunTelemetry.__table__,
        AssistantRunTelemetry.__table__.c.tenant_client_id.in_(tenant_ids),
    )

    fee_item_ids = _collect_ids(
        db,
        FeeScheduleItem.__table__,
        FeeScheduleItem.__table__.c.fee_schedule_id.in_(fee_schedule_ids),
    )
    quote_ids = _collect_ids(
        db,
        Quote.__table__,
        Quote.__table__.c.request_id.in_(request_ids_all)
        | Quote.__table__.c.fee_schedule_id.in_(fee_schedule_ids),
    )
    payment_ids = _collect_ids(
        db,
        Payment.__table__,
        Payment.__table__.c.request_id.in_(request_ids_all) | Payment.__table__.c.quote_id.in_(quote_ids),
    )
    payment_event_ids = _collect_ids(
        db,
        PaymentEvent.__table__,
        PaymentEvent.__table__.c.payment_id.in_(payment_ids),
    )
    request_note_ids = _collect_ids(
        db,
        RequestNote.__table__,
        RequestNote.__table__.c.request_id.in_(request_ids_all),
    )
    request_assignment_ids = _collect_ids(
        db,
        RequestAssignment.__table__,
        RequestAssignment.__table__.c.request_id.in_(request_ids_all),
    )
    request_status_event_ids = _collect_ids(
        db,
        RequestStatusEvent.__table__,
        RequestStatusEvent.__table__.c.request_id.in_(request_ids_all),
    )
    letter_draft_ids = _collect_ids(
        db,
        LetterDraft.__table__,
        LetterDraft.__table__.c.request_id.in_(request_ids_all)
        | LetterDraft.__table__.c.template_id.in_(letter_template_ids),
    )
    letter_version_ids = _collect_ids(
        db,
        LetterVersion.__table__,
        LetterVersion.__table__.c.request_id.in_(request_ids_all)
        | LetterVersion.__table__.c.draft_id.in_(letter_draft_ids),
    )
    delivery_ids = _collect_ids(
        db,
        Delivery.__table__,
        Delivery.__table__.c.request_id.in_(request_ids_all)
        | Delivery.__table__.c.letter_version_id.in_(letter_version_ids),
    )
    email_event_ids = _collect_ids(
        db,
        EmailEvent.__table__,
        EmailEvent.__table__.c.request_id.in_(request_ids_all)
        | EmailEvent.__table__.c.template_id.in_(email_template_ids | email_template_tenant_ids),
    )
    email_template_ids = email_template_ids | email_template_tenant_ids

    deleted_by_table: list[DatabaseCleanupTableResult] = []

    for table_name, ids in (
        ("agentic_assistant_message_feedback", assistant_feedback_ids),
        ("agentic_assistant_turn_events", assistant_turn_event_ids),
        ("agentic_assistant_run_telemetry", assistant_run_ids),
        ("agentic_zoning_code_sections", zoning_section_ids),
        ("agentic_zoning_code_documents", zoning_document_ids),
        ("shared_tenant_domains", tenant_domain_ids),
        ("letters_payment_events", payment_event_ids),
        ("letters_deliveries", delivery_ids),
        ("letters_letter_versions", letter_version_ids),
        ("letters_payments", payment_ids),
        ("letters_letter_drafts", letter_draft_ids),
        ("letters_request_notes", request_note_ids),
        ("letters_request_assignments", request_assignment_ids),
        ("letters_request_status_events", request_status_event_ids),
        ("shared_email_events", email_event_ids),
        ("letters_quotes", quote_ids),
        ("letters_fee_schedule_items", fee_item_ids),
        ("letters_requests", request_ids_all),
        ("shared_property_snapshots", property_snapshot_ids),
        ("letters_fee_schedules", fee_schedule_ids),
        ("letters_letter_templates", letter_template_ids),
        ("shared_email_templates", email_template_ids),
        ("agentic_zoning_code_ingestion_runs", zoning_run_ids),
        ("shared_properties", property_ids),
        ("shared_tenant_clients", tenant_ids),
        ("shared_jurisdiction_home_page_content", homepage_ids),
    ):
        table = Base.metadata.tables[table_name]
        deleted = _delete_by_ids(db, table, ids)
        if deleted:
            deleted_by_table.append(DatabaseCleanupTableResult(table_name=table_name, deleted_rows=deleted))

    db.commit()
    return DatabaseCleanupResult(
        deleted_rows_total=sum(item.deleted_rows for item in deleted_by_table),
        deleted_by_table=deleted_by_table,
        database_info=get_database_info(db),
    )
