from zoning_agno.normalize.crossrefs import extract_cross_references


def test_extract_cross_references_finds_common_patterns() -> None:
    text = "See Sec. 5.3.2, Section 2.4.1, Article IV, Chapter 4, and Division 3 for details."
    refs = extract_cross_references(text)
    assert "Sec. 5.3.2" in refs
    assert "Section 2.4.1" in refs
    assert "Article IV" in refs
    assert "Chapter 4" in refs
    assert "Division 3" in refs
