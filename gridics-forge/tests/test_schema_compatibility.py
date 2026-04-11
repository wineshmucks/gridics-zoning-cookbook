from zoning_agno.schemas import Citation, DistrictRecord, PipelineInput, RetrievalBundle, RetrievalHit, SourceKind


def test_citation_accepts_node_id_and_title() -> None:
    citation = Citation(
        node_id="123",
        title="Section 1.1",
        quote="Minimum lot area is 5,000 square feet.",
        source_url="https://example.com",
        confidence=0.8,
    )
    assert citation.node_id == "123"
    assert citation.normalized_title == "Section 1.1"


def test_district_record_alias_round_trip() -> None:
    district = DistrictRecord(
        district_code="RS-6",
        district_name="Single Family Residential",
        citations_json=[{"node_id": "100", "title": "Districts", "quote": "RS-6 district", "confidence": 0.7}],
    )
    assert district.citations[0].node_id == "100"


def test_retrieval_bundle_shape() -> None:
    bundle = RetrievalBundle(
        query="RS-6 minimum lot area",
        hits=[RetrievalHit(chunk_text="Minimum lot area is 5000 sf", score=0.91, retrieval_mode="hybrid")],
    )
    assert bundle.hits[0].retrieval_mode == "hybrid"


def test_pipeline_input_defaults_to_municode() -> None:
    payload = PipelineInput(
        jurisdiction="Abilene, TX",
        source_url="https://example.com",
        workbook_template_path="template.xlsx",
    )
    assert payload.source_kind == SourceKind.MUNICODE
