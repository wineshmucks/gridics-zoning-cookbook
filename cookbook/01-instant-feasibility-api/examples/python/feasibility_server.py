#!/usr/bin/env python3
"""Compatibility server for the instant feasibility example.

Preferred server: `server/app/main.py` (FastAPI).
This file remains as a lightweight local wrapper.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from agent_os.common.feasibility_engine import evaluate_feasibility
from agent_os.common.gridics_client import GridicsClient


class FeasibilityHandler(BaseHTTPRequestHandler):
    server_version = "GridicsFeasibilityExample/0.2"

    def _json_response(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json_response(200, {"status": "ok"})
            return
        self._json_response(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/feasibility":
            self._json_response(404, {"error": "not_found"})
            return

        api_key = os.getenv("GRIDICS_API_KEY", "").strip() or os.getenv(
            "GRIDICS_CONSUMER_KEY", ""
        ).strip()
        if not api_key:
            self._json_response(
                500, {"error": "Set GRIDICS_API_KEY (or GRIDICS_CONSUMER_KEY)"}
            )
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            request_payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._json_response(400, {"error": "invalid JSON body"})
            return

        client = GridicsClient(
            api_key=api_key,
            base_url=os.getenv("GRIDICS_BASE_URL", "https://api.gridics.com/v1"),
            timeout_seconds=int(os.getenv("GRIDICS_TIMEOUT_SECONDS", "20")),
        )

        status, response = evaluate_feasibility(request_payload, client)
        self._json_response(status, response)


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), FeasibilityHandler)
    print(f"Listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
