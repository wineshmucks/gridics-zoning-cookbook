CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS source_documents (
    id BIGSERIAL PRIMARY KEY,
    jurisdiction TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_file_name TEXT,
    source_url TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS muni_nodes (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    node_id TEXT,
    url TEXT,
    title TEXT,
    subtitle TEXT,
    content TEXT,
    raw_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_muni_nodes_source_document_row_number UNIQUE (source_document_id, row_number)
);

CREATE TABLE IF NOT EXISTS legal_sections (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    node_id TEXT,
    section_path TEXT NOT NULL,
    title TEXT,
    subtitle TEXT,
    body_text TEXT NOT NULL,
    section_type TEXT NOT NULL,
    parent_section_id BIGINT REFERENCES legal_sections(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS legal_chunks (
    id BIGSERIAL PRIMARY KEY,
    legal_section_id BIGINT NOT NULL REFERENCES legal_sections(id) ON DELETE CASCADE,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    node_id TEXT,
    chunk_index INTEGER NOT NULL,
    chunk_type TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    token_estimate INTEGER,
    title TEXT,
    subtitle TEXT,
    section_path TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_legal_chunks_section_chunk_index UNIQUE (legal_section_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS legal_crossrefs (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    from_section_id BIGINT NOT NULL REFERENCES legal_sections(id) ON DELETE CASCADE,
    to_section_ref TEXT NOT NULL,
    to_section_id BIGINT REFERENCES legal_sections(id) ON DELETE SET NULL,
    ref_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_definitions (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    definition_text TEXT NOT NULL,
    section_id BIGINT REFERENCES legal_sections(id) ON DELETE SET NULL,
    node_id TEXT
);

CREATE TABLE IF NOT EXISTS legal_chunk_embeddings (
    id BIGSERIAL PRIMARY KEY,
    legal_chunk_id BIGINT NOT NULL UNIQUE REFERENCES legal_chunks(id) ON DELETE CASCADE,
    embedding VECTOR,
    embedding_model TEXT NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS zoning_districts (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    district_code TEXT NOT NULL,
    district_name TEXT,
    family TEXT,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS zoning_use_rules (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    district_code TEXT NOT NULL,
    use_key TEXT,
    use_label TEXT,
    allowance TEXT,
    conditions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    exceptions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS zoning_general_standards (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    district_code TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value_text TEXT,
    value_numeric DOUBLE PRECISION,
    unit TEXT,
    operator TEXT,
    conditions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    exceptions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS zoning_parking_rules (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    district_code TEXT,
    use_key TEXT,
    rule_text TEXT NOT NULL,
    formula_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS review_flags (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id BIGINT,
    severity TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    message TEXT NOT NULL,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_muni_nodes_node_id ON muni_nodes (node_id);
CREATE INDEX IF NOT EXISTS ix_muni_nodes_source_document_id ON muni_nodes (source_document_id);
CREATE INDEX IF NOT EXISTS ix_legal_sections_source_document_id ON legal_sections (source_document_id);
CREATE INDEX IF NOT EXISTS ix_legal_sections_section_path ON legal_sections (section_path);
CREATE INDEX IF NOT EXISTS ix_legal_chunks_source_document_id ON legal_chunks (source_document_id);
CREATE INDEX IF NOT EXISTS ix_legal_chunks_section_path ON legal_chunks (section_path);
CREATE INDEX IF NOT EXISTS ix_legal_definitions_term ON legal_definitions (term);
CREATE INDEX IF NOT EXISTS ix_zoning_districts_district_code ON zoning_districts (district_code);
CREATE INDEX IF NOT EXISTS ix_zoning_general_standards_field_name ON zoning_general_standards (field_name);
CREATE INDEX IF NOT EXISTS ix_zoning_general_standards_district_code ON zoning_general_standards (district_code);
CREATE INDEX IF NOT EXISTS ix_zoning_use_rules_district_code ON zoning_use_rules (district_code);
