"""Add zoning code ingestion and pgvector knowledge tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260309_000006"
down_revision = "20260309_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai;")

    op.create_table(
        "zoning_code_ingestion_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_client_id", sa.String(length=36), sa.ForeignKey("tenant_clients.id"), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=False),
        sa.Column("pages_crawled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("documents_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sections_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "zoning_code_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_client_id", sa.String(length=36), sa.ForeignKey("tenant_clients.id"), nullable=False),
        sa.Column("ingestion_run_id", sa.String(length=36), sa.ForeignKey("zoning_code_ingestion_runs.id")),
        sa.Column("source_url", sa.String(length=2000), nullable=False),
        sa.Column("source_path", sa.String(length=1000)),
        sa.Column("source_title", sa.String(length=500)),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("fetch_status_code", sa.Integer()),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_client_id", "source_url", name="uq_zoning_code_documents_source"),
    )

    op.create_table(
        "zoning_code_sections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_client_id", sa.String(length=36), sa.ForeignKey("tenant_clients.id"), nullable=False),
        sa.Column("ingestion_run_id", sa.String(length=36), sa.ForeignKey("zoning_code_ingestion_runs.id")),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("zoning_code_documents.id"), nullable=False),
        sa.Column("section_key", sa.String(length=500), nullable=False),
        sa.Column("section_title", sa.String(length=500), nullable=False),
        sa.Column("section_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("section_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("section_path", sa.String(length=1000)),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source_anchor", sa.String(length=255)),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_client_id", "section_key", name="uq_zoning_code_sections_key"),
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai.customer_zoning_chunks (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            meta_data JSONB DEFAULT '{}'::jsonb,
            filters JSONB DEFAULT '{}'::jsonb,
            content TEXT,
            embedding vector(1536),
            usage JSONB,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ,
            content_hash VARCHAR,
            content_id VARCHAR
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_zoning_chunks_id ON ai.customer_zoning_chunks (id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_zoning_chunks_name ON ai.customer_zoning_chunks (name)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_zoning_chunks_content_hash ON ai.customer_zoning_chunks (content_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_zoning_chunks_content_id ON ai.customer_zoning_chunks (content_id)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_customer_zoning_chunks_embedding_hnsw
        ON ai.customer_zoning_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai.customer_zoning_chunks")
    op.drop_table("zoning_code_sections")
    op.drop_table("zoning_code_documents")
    op.drop_table("zoning_code_ingestion_runs")
