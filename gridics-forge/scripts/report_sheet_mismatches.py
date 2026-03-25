from __future__ import annotations

import json
from pathlib import Path

import typer

from zoning_agno.services.mismatch_report import collect_sheet_mismatches, summary_to_json_ready


app = typer.Typer(add_completion=False, help="Summarize workbook mismatches by template row and district.")


@app.command()
def main(
    generated: Path = typer.Argument(..., exists=True, readable=True, help="Generated workbook path."),
    reference: Path = typer.Argument(..., exists=True, readable=True, help="Reference workbook path."),
    sheets: list[str] | None = typer.Option(None, "--sheet", help="Specific sheet(s) to report."),
    sample_limit: int = typer.Option(20, min=1, help="Mismatch samples to print per sheet."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a text summary."),
) -> None:
    summaries = collect_sheet_mismatches(generated, reference, sheet_names=sheets)

    if as_json:
        print(json.dumps([summary_to_json_ready(item) for item in summaries], indent=2, ensure_ascii=True))
        return

    print(f"Generated: {generated}")
    print(f"Reference: {reference}")
    print()
    for summary in summaries:
        print(f"{summary.sheet_name}: mismatches={summary.mismatch_count} by_kind={summary.by_kind}")
        top_rows = list(summary.by_row_key.items())[:10]
        if top_rows:
            print("  top_rows:")
            for row_key, count in top_rows:
                print(f"    {row_key}: {count}")
        if summary.mismatches:
            print("  samples:")
            for mismatch in summary.mismatches[:sample_limit]:
                print(
                    f"    {mismatch.row_key} [{mismatch.district_code}] {mismatch.kind}: "
                    f"generated={mismatch.generated_value!r} reference={mismatch.reference_value!r}"
                )
        print()


if __name__ == "__main__":
    app()
