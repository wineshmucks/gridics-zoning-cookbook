from zoning_agno.schemas import UseLabelInterpretationBundle
from zoning_agno.services.use_interpretation import _normalize_bundle


def test_normalize_bundle_accepts_items_alias() -> None:
    bundle = _normalize_bundle(
        {
            "items": [
                {
                    "source_label": "Church or Place of Worship",
                    "matched_use_names": ["Religious Buildings", "Assembly"],
                    "confidence": 0.9,
                }
            ]
        }
    )

    assert isinstance(bundle, UseLabelInterpretationBundle)
    assert bundle.interpretations[0].matched_use_names == ["Religious Buildings", "Assembly"]
