from __future__ import annotations

from pathlib import Path
import json
import logging
import re
import shutil

import typer

from zoning_agno.config import Settings
from zoning_agno.models.schemas import PipelineInput
from zoning_agno.workflows import build_zoning_standardization_workflow

app = typer.Typer(add_completion=False)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "run"


def _default_cache_dir(jurisdiction: str, source_document_id: int) -> Path:
    return Path("cache") / _slugify(jurisdiction) / f"source-document-{source_document_id}"


def _clear_previous_artifacts(cache_path: Path) -> None:
    for name in ["manifest.json", "workflow_steps"]:
        target = cache_path / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


@app.command()
def run(
    source_document_id: int = typer.Option(..., help="Existing source_document_id loaded into the database."),
    jurisdiction: str = typer.Option(..., help="Jurisdiction label."),
    out: Path = typer.Option(..., help="Output workbook path."),
    template_path: Path | None = typer.Option(None, help="Optional workbook template override."),
    source_url: str = typer.Option("database://source_document", help="Logical source URL label for the workflow run."),
    cache_dir: Path | None = typer.Option(None, help="Optional artifact directory."),
    invalidate_existing_artifacts: bool = typer.Option(
        False,
        help="Delete prior workflow artifacts in the cache dir before running.",
    ),
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    workflow = build_zoning_standardization_workflow(settings)

    out.parent.mkdir(parents=True, exist_ok=True)
    resolved_template_path = template_path or Path(settings.workbook_template_path)
    if not resolved_template_path.exists():
        raise FileNotFoundError(f"Workbook template not found: {resolved_template_path}")

    pipeline_input = PipelineInput(
        jurisdiction=jurisdiction,
        source_url=source_url,
        workbook_template_path=str(resolved_template_path),
        source_document_id=source_document_id,
    )

    cache_path = cache_dir or _default_cache_dir(jurisdiction, source_document_id)
    cache_path.mkdir(parents=True, exist_ok=True)
    if invalidate_existing_artifacts:
        _clear_previous_artifacts(cache_path)

    session_state = {
        "pipeline_input": pipeline_input.model_dump(),
        "source_document_id": source_document_id,
        "out_path": str(out),
        "artifact_root": str(cache_path),
    }

    manifest_path = cache_path / "manifest.json"
    manifest = {
        "workflow": "zoning-standardization-pivot-foundation",
        "source_document_id": source_document_id,
        "jurisdiction": jurisdiction,
        "source_url": source_url,
        "template_path": str(resolved_template_path),
        "out_path": str(out),
        "cache_root": str(cache_path),
        "artifact_root": str(cache_path / "workflow_steps"),
        "artifacts": {
            "load-source-metadata": "workflow_steps/01-load-source-metadata/output.json",
            "build-district-registry": "workflow_steps/02-build-district-registry/output.json",
            "extract-dimensional-facts": "workflow_steps/03-extract-dimensional-facts/output.json",
            "extract-use-facts": "workflow_steps/04-extract-use-facts/output.json",
            "build-general-pivot": "workflow_steps/05-build-general-pivot/output.json",
            "build-general-population": "workflow_steps/06-build-general-population/output.json",
            "build-use-population": "workflow_steps/07-build-use-population/output.json",
            "extract-parking-facts": "workflow_steps/08-extract-parking-facts/output.json",
            "build-parking-population": "workflow_steps/09-build-parking-population/output.json",
            "build-use-capacity-population": "workflow_steps/10-build-use-capacity-population/output.json",
            "build-bonus-population": "workflow_steps/11-build-bonus-population/output.json",
            "run-qa": "workflow_steps/12-run-qa/output.json",
            "export-workbook": "workflow_steps/13-export-workbook/output.json",
            "emit-review-queue": "workflow_steps/14-emit-review-queue/output.json",
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = workflow.run(input=pipeline_input.model_dump(), session_state=session_state)
    manifest["result"] = result.content
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    source_path = (
        result.content.get("source_document", {})
        .get("metadata", {})
        .get("source_file_path")
    )
    typer.echo(f"Cache: {cache_path}")
    if source_path:
        typer.echo(f"Source workbook: {source_path}")
    typer.echo(f"Template workbook: {resolved_template_path}")
    typer.echo(f"Workbook: {out}")


if __name__ == "__main__":
    app()
