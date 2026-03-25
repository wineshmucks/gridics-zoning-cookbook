from __future__ import annotations

import json
import logging

import typer

from zoning_agno.config import get_settings
from zoning_agno.db import create_engine_from_settings, create_session_factory, initialize_database
from zoning_agno.retrieval import VectorStore, build_embedder

app = typer.Typer(add_completion=False)


@app.command()
def main(
    source_document_id: int | None = typer.Option(None, help="Optional source document id filter."),
    limit: int | None = typer.Option(None, help="Optional maximum number of chunks to embed this run."),
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    initialize_database(engine)
    session_factory = create_session_factory(settings)
    embedder = build_embedder(settings)

    with session_factory() as session:
        store = VectorStore(session, embedder)
        embedded = store.embed_pending_chunks(
            source_document_id=source_document_id,
            limit=limit,
            batch_size=settings.embedding_batch_size,
        )
        pending_after = store.pending_chunk_count(source_document_id=source_document_id)

    typer.echo(
        json.dumps(
            {
                "source_document_id": source_document_id,
                "embedded_count": embedded,
                "pending_count": pending_after,
                "embedding_provider": settings.embedding_provider,
                "embedding_model": embedder.model_name,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
