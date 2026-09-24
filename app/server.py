from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .plan import create_plan

MAX_REQUEST_BYTES = 64 * 1024


class PlanHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            endpoint = os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
            try:
                with urlopen(f"{endpoint}/api/version", timeout=2) as response:
                    ollama = json.loads(response.read())
                self._send(200, {"status": "ok", "ollama": ollama})
            except OSError as error:
                self._send(503, {"status": "degraded", "ollama": str(error)})
            return
        self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/plans":
            self._send(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_REQUEST_BYTES:
                raise ValueError("Request body must be between 1 and 65536 bytes")
            payload = json.loads(self.rfile.read(length))
            request = payload["request"]
            repository = Path(payload["repository"]).expanduser().resolve()
            if not isinstance(request, str) or not request.strip():
                raise ValueError("request must be a non-empty string")
            model = payload.get("model", "qwen2.5-coder:1.5b")
            endpoint = os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
            plan = create_plan(request, repository, model, endpoint)
            self._send(200, plan)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._send(400, {"error": str(error)})
        except OSError as error:
            self._send(422, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    host = os.environ.get("PLAN_HOST", "127.0.0.1")
    port = int(os.environ.get("PLAN_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PlanHandler)
    print(f"Plan API listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
