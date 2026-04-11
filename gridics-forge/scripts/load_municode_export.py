from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from zoning_agno.config import get_settings
from zoning_agno.db import create_engine_from_settings, create_session_factory, initialize_database
from zoning_agno.ingest import ingest_workbook
from zoning_agno.schemas import SourceKind

app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)


@app.command()
def main(
    workbook_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    jurisdiction: str = typer.Option(..., help="Jurisdiction slug or human-readable name."),
    source_url: str | None = typer.Option(None, help="Optional canonical source URL."),
    sheet_name: str | None = typer.Option(None, help="Optional worksheet override."),
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    initialize_database(engine)
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        stats = ingest_workbook(
            session=session,
            workbook_path=workbook_path,
            jurisdiction=jurisdiction,
            source_url=source_url,
            source_type=SourceKind.MUNICODE,
            sheet_name=sheet_name,
        )

    payload = {
        "source_document_id": stats.source_document_id,
        "jurisdiction": stats.jurisdiction,
        "sheet_name": stats.sheet_name,
        "row_count": stats.row_count,
        "populated_node_ids": stats.populated_node_ids,
        "populated_titles": stats.populated_titles,
        "populated_content_rows": stats.populated_content_rows,
        "detected_columns": stats.detected_columns,
    }
    typer.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    app()
