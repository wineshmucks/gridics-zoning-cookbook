from pathlib import Path

from zoning_agno.models.schemas import PipelineInput


def test_pipeline_input_accepts_source_document_id() -> None:
    payload = PipelineInput(
        jurisdiction="Abilene, TX",
        source_url="database://source_document",
        workbook_template_path=str(Path("data/templates/zoning_template.xlsx")),
        source_document_id=1,
    )
    assert payload.source_document_id == 1
