from zoning_agno.models.schemas import Citation, District, DistrictFamily, UseRule


def test_citation_confidence_range() -> None:
    citation = Citation(quote="Example", confidence=0.5)
    assert citation.confidence == 0.5


def test_district_defaults() -> None:
    district = District(code="RS-6")
    assert district.family == DistrictFamily.ZONE


def test_use_rule_minimal() -> None:
    rule = UseRule(district_code="RS-6", use_name="Single Family")
    assert rule.use_name == "Single Family"
