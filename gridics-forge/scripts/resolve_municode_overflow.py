from __future__ import annotations

from dataclasses import asdict
import json
import logging

import typer

from zoning_agno.config import get_settings
from zoning_agno.db import create_engine_from_settings, create_session_factory, initialize_database
from zoning_agno.services.municode_overflow import resolve_overflow_nodes

app = typer.Typer(add_completion=False)


@app.command()
def main(
    source_document_id: int = typer.Argument(..., help="Source document id loaded from workbook ingestion."),
    supplemental_source: list[str] | None = typer.Option(
        None,
        "--supplemental-source",
        help="Optional local PDF path or URL used to patch truncated source nodes. Repeatable.",
    ),
    force: bool = typer.Option(False, "--force", help="Re-run resolution for rows previously patched by overflow recovery."),
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    initialize_database(engine)
    session_factory = create_session_factory(settings)
    supplemental_sources = supplemental_source or settings.supplemental_source_urls
    with session_factory() as session:
        stats = resolve_overflow_nodes(
            session,
            source_document_id,
            supplemental_sources=supplemental_sources,
            force=force,
        )
    typer.echo(json.dumps(asdict(stats), indent=2))


if __name__ == "__main__":
    app()
