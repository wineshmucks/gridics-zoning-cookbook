from __future__ import annotations

import json
from pathlib import Path

import typer

from zoning_agno.services.workbook_compare import TARGET_SHEETS, compare_workbooks


app = typer.Typer(add_completion=False, help="Compare a generated workbook against a reference workbook.")


@app.command()
def main(
    generated: Path = typer.Argument(..., exists=True, readable=True, help="Generated workbook path."),
    reference: Path = typer.Argument(..., exists=True, readable=True, help="Reference workbook path."),
    sheets: list[str] | None = typer.Option(None, "--sheet", help="Specific sheet(s) to compare."),
    sample_limit: int = typer.Option(10, min=1, help="Number of sample diffs per sheet."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a text summary."),
) -> None:
    comparisons = compare_workbooks(
        generated,
        reference,
        sheet_names=sheets or TARGET_SHEETS,
        sample_limit=sample_limit,
    )

    if as_json:
        payload = [
            {
                "sheet_name": comparison.sheet_name,
                "rows": comparison.rows,
                "columns": comparison.columns,
                "total_cells": comparison.total_cells,
                "exact_nonblank_matches": comparison.exact_nonblank_matches,
                "both_blank": comparison.both_blank,
                "generated_filled_cells": comparison.generated_filled_cells,
                "reference_filled_cells": comparison.reference_filled_cells,
                "missing_from_generated": comparison.missing_from_generated,
                "extra_in_generated": comparison.extra_in_generated,
                "value_mismatches": comparison.value_mismatches,
                "populated_cell_match_rate": round(comparison.populated_cell_match_rate, 4),
                "sample_diffs": [
                    {
                        "row": diff.row,
                        "column": diff.column,
                        "generated_value": diff.generated_value,
                        "reference_value": diff.reference_value,
                        "kind": diff.kind,
                    }
                    for diff in comparison.sample_diffs
                ],
            }
            for comparison in comparisons
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return

    print(f"Generated: {generated}")
    print(f"Reference: {reference}")
    print()
    for comparison in comparisons:
        print(
            f"{comparison.sheet_name}: "
            f"match_rate={comparison.populated_cell_match_rate:.1%} "
            f"exact={comparison.exact_nonblank_matches} "
            f"missing={comparison.missing_from_generated} "
            f"extra={comparison.extra_in_generated} "
            f"mismatch={comparison.value_mismatches}"
        )
        for diff in comparison.sample_diffs:
            print(
                f"  r{diff.row}c{diff.column} {diff.kind}: "
                f"generated={diff.generated_value!r} reference={diff.reference_value!r}"
            )
        print()


if __name__ == "__main__":
    app()
