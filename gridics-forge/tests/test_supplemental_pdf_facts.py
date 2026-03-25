from zoning_agno.schemas import Citation
from zoning_agno.services.supplemental_pdf_facts import (
    _TemplateUseCandidate,
    _match_template_use_candidates,
    _nonresidential_row_to_facts,
    _normalize_use_label,
    _residential_row_to_facts,
    _use_match_score,
)


def test_residential_row_to_facts_extracts_height_and_density() -> None:
    citation = Citation(title="table", quote="row", source_url="https://example.com", confidence=1.0)
    row = [
        "MF",
        "24",
        "6,000",
        "60",
        "100",
        "15",
        None,
        "20",
        "30",
        "40",
        None,
        "25",
        "20",
        "10",
        "40; 3 stories",
        "90%",
        None,
    ]
    facts = _residential_row_to_facts(
        district_code="MF",
        row=row,
        citation=citation,
        source_document_id="1",
    )
    by_field = {fact.field_name: fact for fact in facts}
    assert by_field["LotAreaMin"].value_numeric == 6000
    assert by_field["DensityNet"].value_numeric == 24
    assert by_field["PrincipalMaxHeightFt"].value_numeric == 40
    assert by_field["PrincipalMaxHeightLvl"].value_numeric == 3


def test_nonresidential_row_to_facts_extracts_far_as_levels_and_capacity() -> None:
    citation = Citation(title="table", quote="row", source_url="https://example.com", confidence=1.0)
    row = [
        "CB",
        "none",
        None,
        "none",
        None,
        None,
        "none",
        "none",
        "none",
        "0; abutting AO or Residential District, 25",
        "0; abutting AO or Residential District, 20",
        None,
        "none",
        "10:1",
        None,
        None,
    ]
    facts = _nonresidential_row_to_facts(
        district_code="CB",
        row=row,
        citation=citation,
        source_document_id="1",
    )
    by_field = {fact.field_name: fact for fact in facts}
    assert by_field["MaximumResidentialFAR"].value_numeric == 10
    assert by_field["PrincipalMaxHeightLvl"].value_numeric == 10
    assert by_field["MinRearSetback"].value_numeric == 0
    assert by_field["MinSideSetback"].value_numeric == 0


def test_use_match_score_recognizes_accessory_dwelling_alias() -> None:
    assert _use_match_score(_normalize_use_label("Dwelling - Accessory"), _normalize_use_label("Accessory Dwelling Unit")) >= 0.9


def test_match_template_use_candidates_adds_derivation_targets() -> None:
    candidates = [
        _TemplateUseCandidate(
            row_key="home_office_occupation",
            use_name="Home Office Occupation",
            use_key="home_office_occupation",
            normalized_label="home office occupation",
            canonical_key="home_office_occupation",
        ),
        _TemplateUseCandidate(
            row_key="accessory_office_unit",
            use_name="Accessory Office Unit",
            use_key="accessory_office_unit",
            normalized_label="accessory office unit",
            canonical_key="accessory_office_unit",
        ),
        _TemplateUseCandidate(
            row_key="accessory_commercial_unit",
            use_name="Accessory Commercial Unit",
            use_key="accessory_commercial_unit",
            normalized_label="accessory commercial unit",
            canonical_key="accessory_commercial_unit",
        ),
    ]

    matches = _match_template_use_candidates("Home Occupation", candidates)

    assert {item.use_name for item in matches} == {
        "Home Office Occupation",
        "Accessory Office Unit",
        "Accessory Commercial Unit",
    }
