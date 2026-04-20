"""Rebuild customer zoning chunk vectors for 1536-dimension embeddings.

Gemini text embeddings currently return 1536 dimensions, but the vector table
was previously rebuilt for 2048 dimensions. Recreate the table so ingestion can
write the new vectors without dimension errors.
"""

from alembic import op


revision = "20260419_000014"
down_revision = "20260419_000013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai;")
    op.execute("DROP TABLE IF EXISTS ai.agentic_customer_zoning_chunks")
    op.execute(
        """
        CREATE TABLE ai.agentic_customer_zoning_chunks (
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
    op.execute("CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_id ON ai.agentic_customer_zoning_chunks (id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_name ON ai.agentic_customer_zoning_chunks (name)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_content_hash ON ai.agentic_customer_zoning_chunks (content_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_content_id ON ai.agentic_customer_zoning_chunks (content_id)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_embedding_hnsw
        ON ai.agentic_customer_zoning_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai.agentic_customer_zoning_chunks")
    op.execute(
        """
        CREATE TABLE ai.agentic_customer_zoning_chunks (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            meta_data JSONB DEFAULT '{}'::jsonb,
            filters JSONB DEFAULT '{}'::jsonb,
            content TEXT,
            embedding vector(2048),
            usage JSONB,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ,
            content_hash VARCHAR,
            content_id VARCHAR
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_id ON ai.agentic_customer_zoning_chunks (id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_name ON ai.agentic_customer_zoning_chunks (name)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_content_hash ON ai.agentic_customer_zoning_chunks (content_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agentic_customer_zoning_chunks_content_id ON ai.agentic_customer_zoning_chunks (content_id)"
    )
