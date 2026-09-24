from __future__ import annotations

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .plan import create_plan

MAX_REQUEST_BYTES = 64 * 1024


class PlanHandler(BaseHTTPRequestHandler):
    def _plans_directory(self) -> Path:
        return Path(os.environ.get("PLANS_DIR", "plans"))

    def _allowed_repository(self, requested: Path) -> Path:
        configured = os.environ.get("PROJECT_ROOTS") or os.environ.get("STREAMBANK_PATH")
        if not configured:
            return requested
        roots = [
            Path(value).expanduser().resolve()
            for value in configured.split(os.pathsep)
            if value.strip()
        ]
        if any(requested == root or root in requested.parents for root in roots):
            return requested
        raise ValueError("repository is outside the configured project roots")

    def _configured_roots(self) -> list[Path]:
        configured = os.environ.get("PROJECT_ROOTS") or os.environ.get("STREAMBANK_PATH", "")
        return [
            Path(value).expanduser().resolve()
            for value in configured.split(os.pathsep)
            if value.strip()
        ]

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
        if self.path == "/projects":
            projects = [
                {
                    "name": root.name,
                    "path": str(root),
                    "exists": root.is_dir(),
                }
                for root in self._configured_roots()
            ]
            self._send(200, {"projects": projects})
            return
        if self.path == "/plans":
            plans = []
            for path in sorted(
                self._plans_directory().glob("*.json"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            ):
                try:
                    plan = json.loads(path.read_text(encoding="utf-8"))
                    plans.append(
                        {
                            "runId": plan["runId"],
                            "createdAt": plan["createdAt"],
                            "request": plan.get("request", ""),
                            "mode": plan.get("mode", "plan-only"),
                        }
                    )
                except (OSError, KeyError, TypeError, json.JSONDecodeError):
                    continue
            self._send(200, {"plans": plans})
            return
        if self.path.startswith("/plans/"):
            run_id = self.path.removeprefix("/plans/")
            if "/" in run_id or not run_id:
                self._send(400, {"error": "Invalid runId"})
                return
            plan_path = self._plans_directory() / f"{run_id}.json"
            try:
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                self._send(200, plan)
            except FileNotFoundError:
                self._send(404, {"error": "Plan not found"})
            except (OSError, TypeError, json.JSONDecodeError) as error:
                self._send(500, {"error": str(error)})
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
            repository = self._allowed_repository(
                Path(payload["repository"]).expanduser().resolve()
            )
            if not isinstance(request, str) or not request.strip():
                raise ValueError("request must be a non-empty string")
            model = payload.get("model", "qwen2.5-coder:1.5b")
            endpoint = os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
            plan = create_plan(request, repository, model, endpoint)
            plan["runId"] = str(uuid.uuid4())
            plan["createdAt"] = datetime.now(timezone.utc).isoformat()
            plans_dir = self._plans_directory()
            plans_dir.mkdir(parents=True, exist_ok=True)
            (plans_dir / f"{plan['runId']}.json").write_text(
                json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
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
