"""Refresh local cached Gridics market availability data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from agent_os.common.gridics_client import GridicsClient
from agent_os.config import GRIDICS_BASE_URL, GRIDICS_TIMEOUT_SECONDS, get_gridics_api_key


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "markets.json"


def refresh_markets(output_path: Path) -> Path:
    client = GridicsClient(
        api_key=get_gridics_api_key(),
        base_url=GRIDICS_BASE_URL,
        timeout_seconds=GRIDICS_TIMEOUT_SECONDS,
    )
    response = client.get_markets()
    if not isinstance(response, dict):
        raise RuntimeError(f"Unexpected response type: {type(response).__name__}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh cached Gridics markets data.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    out = refresh_markets(Path(args.output))
    payload = json.loads(out.read_text(encoding="utf-8"))
    print(f"Wrote {out}")
    print(f"status={payload.get('status')} dataRows={payload.get('dataRows')}")


if __name__ == "__main__":
    main()
