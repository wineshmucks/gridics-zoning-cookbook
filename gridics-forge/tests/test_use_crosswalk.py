from zoning_agno.services.use_crosswalk import (
    canonicalize_use_label,
    load_use_crosswalk,
    load_use_derivations,
    use_labels_share_canonical_concept,
)


def test_load_use_crosswalk_returns_catalog() -> None:
    catalog = load_use_crosswalk()
    assert "accessory_dwelling_unit" in catalog
    assert "Dwelling - Accessory" in catalog["accessory_dwelling_unit"]


def test_load_use_derivations_returns_catalog() -> None:
    derivations = load_use_derivations()
    assert "home_office_occupation" in derivations
    assert "Accessory Office Unit" in derivations["home_office_occupation"]


def test_canonicalize_use_label_maps_common_crosswalk_pairs() -> None:
    assert canonicalize_use_label("Accessory Dwelling Unit").canonical_key == "accessory_dwelling_unit"
    assert canonicalize_use_label("Dwelling - Accessory").canonical_key == "accessory_dwelling_unit"
    assert canonicalize_use_label("Trade/Business School").canonical_key == "adult_education"
    assert canonicalize_use_label("Office (general, professional, financial)").canonical_key == "general_office"


def test_use_labels_share_canonical_concept_for_crosswalked_labels() -> None:
    assert use_labels_share_canonical_concept("Accessory Dwelling Unit", "Dwelling - Accessory")
    assert use_labels_share_canonical_concept("Adult Education", "Trade/Business School")
    assert use_labels_share_canonical_concept("Large Multifamily", "Dwelling - Multiple-Family")
