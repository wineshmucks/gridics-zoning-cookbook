from __future__ import annotations

from dataclasses import asdict
import json
import logging

import typer

from zoning_agno.config import get_settings
from zoning_agno.db import create_engine_from_settings, create_session_factory, initialize_database
from zoning_agno.services.normalization_service import normalize_source_document

app = typer.Typer(add_completion=False)


@app.command()
def main(source_document_id: int = typer.Argument(..., help="Source document id loaded from workbook ingestion.")) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    initialize_database(engine)
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        stats = normalize_source_document(session, source_document_id)
    typer.echo(json.dumps(asdict(stats), indent=2))


if __name__ == "__main__":
    app()
