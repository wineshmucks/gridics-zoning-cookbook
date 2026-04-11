from __future__ import annotations

from pathlib import Path
import logging
import json
import shutil
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import typer

from zoning_agno.config import Settings
from zoning_agno.models.schemas import PipelineInput, PipelineOutput, SourceKind
from zoning_agno.tools.source_tools import scrape_source_to_local
from zoning_agno.workflows.zoning_pipeline import build_zoning_workflow

app = typer.Typer(add_completion=False)


class _SuppressGeminiNonTextWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "there are non-text parts in the response" not in message


def _source_signature(source_url: str, source_kind: SourceKind, node_id: str | None) -> dict[str, str | None]:
    return {
        "source_url": source_url,
        "source_kind": source_kind.value,
        "node_id": node_id,
    }


def _clear_stale_cache(cache_path: Path) -> None:
    for name in [
        "manifest.json",
        "workflow_steps",
    ]:
        target = cache_path / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()
    for pattern in ["*.html", "*.discovery.json", "*.source.json", "*.chunks.json", "*.meta.json"]:
        for artifact in cache_path.glob(pattern):
            if artifact.is_file():
                artifact.unlink()
            elif artifact.is_dir():
                shutil.rmtree(artifact, ignore_errors=True)


def _clear_from_step(cache_path: Path, step_name: str) -> None:
    step_order = ["load-source", "intake", "extract", "qa", "export"]
    if step_name not in step_order:
        return
    start_index = step_order.index(step_name)
    for idx, current_step in enumerate(step_order[start_index:], start=start_index + 1):
        step_dir = cache_path / "workflow_steps" / f"{idx:02d}-{current_step}"
        if step_dir.exists():
            shutil.rmtree(step_dir, ignore_errors=True)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "run"


def _default_cache_dir(jurisdiction: str, source_url: str) -> Path:
    source_stem = Path(urlparse(source_url).path).stem
    if not source_stem:
        source_stem = "source"
    return Path("cache") / _slugify(jurisdiction) / _slugify(source_stem)


@app.command()
def run(
    source_url: str = typer.Option(...),
    jurisdiction: str = typer.Option(...),
    out: Path = typer.Option(..., help="Output workbook path"),
    source_kind: str = typer.Option("municode"),
    node_id: str | None = typer.Option(None, help="Optional Municode nodeId for a direct content page"),
    cache_dir: Path | None = typer.Option(None, help="Optional directory to cache the scraped source HTML"),
    start_from_step: str | None = typer.Option(
        None,
        help="Optional step name to resume from: load-source, intake, extract, qa, or export",
    ),
    invalidate_from_step: str | None = typer.Option(
        None,
        help="Optional step name to invalidate from (delete that step and everything after it)",
    ),
) -> None:
    logging.getLogger("google.genai.types").addFilter(_SuppressGeminiNonTextWarning())

    settings = Settings()
    workflow = build_zoning_workflow(settings)

    out.parent.mkdir(parents=True, exist_ok=True)
    template_path = Path(settings.workbook_template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Workbook template not found: {template_path}")

    normalized_source_url = source_url
    if node_id:
        parsed = urlparse(source_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["nodeId"] = node_id
        normalized_source_url = urlunparse(parsed._replace(query=urlencode(query)))

    source_kind_enum = SourceKind(source_kind)
    source_path = Path(normalized_source_url)
    use_local_source = source_kind_enum == SourceKind.EXCEL or source_path.suffix.lower() in {".xlsx", ".xlsm"}

    pipeline_input = PipelineInput(
        jurisdiction=jurisdiction,
        source_url=normalized_source_url,
        source_kind=source_kind_enum,
        workbook_template_path=str(template_path),
    )

    session_state = {
        "pipeline_input": pipeline_input.model_dump(),
        "source_document": {},
        "out_path": str(out),
    }

    if cache_dir is None:
        cache_path = _default_cache_dir(jurisdiction, normalized_source_url)
    else:
        cache_path = cache_dir
    cache_path.mkdir(parents=True, exist_ok=True)
    session_state["artifact_root"] = str(cache_path)
    if start_from_step:
        session_state["resume_from_step"] = start_from_step
    if use_local_source:
        session_state["local_source_path"] = normalized_source_url
    else:
        local_html_path = scrape_source_to_local(
            source_url=normalized_source_url,
            jurisdiction=jurisdiction,
            source_kind=source_kind_enum,
            cache_dir=cache_path,
        )
        session_state["local_html_path"] = str(local_html_path)
        session_state["local_cache_dir"] = str(cache_path)

    manifest_path = cache_path / "manifest.json"
    source_signature = _source_signature(normalized_source_url, source_kind_enum, node_id)
    if manifest_path.exists():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            previous_signature = previous_manifest.get("source_signature")
            if previous_signature != source_signature:
                _clear_stale_cache(cache_path)
        except Exception:
            _clear_stale_cache(cache_path)
    if invalidate_from_step:
        _clear_from_step(cache_path, invalidate_from_step)
    manifest = {
        "jurisdiction": jurisdiction,
        "source_url": normalized_source_url,
        "source_kind": source_kind_enum.value,
        "source_signature": source_signature,
        "out_path": str(out),
        "cache_root": str(cache_path),
        "artifact_root": str(cache_path / "workflow_steps"),
        "resume_from_step": start_from_step,
        "invalidate_from_step": invalidate_from_step,
        "artifacts": {
            "load-source": {"input": "workflow_steps/01-load-source/01-input.json", "output": "workflow_steps/01-load-source/01-output.json"},
            "intake": {"input": "workflow_steps/02-intake/02-input.json", "output": "workflow_steps/02-intake/02-output.json"},
            "extract": {"input": "workflow_steps/03-extract/03-input.json", "output": "workflow_steps/03-extract/03-output.json"},
            "qa": {"input": "workflow_steps/04-qa/04-input.json", "output": "workflow_steps/04-qa/04-output.json"},
            "export": {"input": "workflow_steps/05-export/05-input.json", "output": "workflow_steps/05-export/05-output.json"},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = workflow.run(input=pipeline_input.model_dump(), session_state=session_state)
    output = PipelineOutput.model_validate(result.content)
    manifest["result_status"] = output.status
    manifest["workbook_output_path"] = output.workbook_output_path
    manifest["review_queue_path"] = output.review_queue_path
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    typer.echo(f"Cache: {cache_path}")
    typer.echo(f"Status: {output.status}")
    typer.echo(f"Workbook: {output.workbook_output_path}")


if __name__ == "__main__":
    app()
