from pathlib import Path

from openpyxl import Workbook

from zoning_agno.services.mismatch_report import collect_sheet_mismatches


def test_collect_sheet_mismatches_groups_by_row_key_and_kind(tmp_path: Path) -> None:
    generated = tmp_path / "generated.xlsx"
    reference = tmp_path / "reference.xlsx"

    for path, values in [
        (
            generated,
            [
                ["Uses Label Id", "Use Name", "Use Value", "AO", "CB"],
                ["100", "Accessory Dwelling Unit", "Use Allowance", "P", None],
                ["101", "General Office", "Use Allowance", "NP", "P"],
            ],
        ),
        (
            reference,
            [
                ["Uses Label Id", "Use Name", "Use Value", "AO", "CB"],
                ["100", "Accessory Dwelling Unit", "Use Allowance", "P", "PC"],
                ["101", "General Office", "Use Allowance", "P", None],
            ],
        ),
    ]:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Zones - Uses"
        for row in values:
            worksheet.append(row)
        workbook.save(path)

    summaries = collect_sheet_mismatches(generated, reference, sheet_names=["Zones - Uses"])

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.mismatch_count == 3
    assert summary.by_kind == {
        "missing_from_generated": 1,
        "value_mismatch": 1,
        "extra_in_generated": 1,
    }
    assert summary.by_row_key["100|Accessory Dwelling Unit|Use Allowance"] == 1
    assert summary.by_row_key["101|General Office|Use Allowance"] == 2
