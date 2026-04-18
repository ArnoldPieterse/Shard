"""Local HTTP API for Shard.

Bound to 127.0.0.1 by default so the API is not exposed to the network.
Endpoints (all JSON):

  GET  /workers
  POST /workers                       {"prefix": "child"} -> {"name": "..."}
  GET  /workers/<name>
  GET  /workers/<name>/history
  POST /workers/<name>/prompt         {"text": "..."}
  POST /workers/<name>/reply          {"text": "..."}  (inject assistant msg)
  POST /workers/<name>/fork           -> {"name": "..."}
  POST /workers/<name>/interrupt
  GET  /healthz

A simple shared-secret token can be required by setting ``SHARD_API_TOKEN``;
when set, callers must send ``Authorization: Bearer <token>``.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from .manager import WorkerManager

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class _Handler(BaseHTTPRequestHandler):
    manager: WorkerManager  # injected via factory
    token: str = ""

    # ---- helpers -------------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
        return

    def _send(self, status: int, body: dict | list | None = None) -> None:
        data = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 1_000_000:  # 1 MB cap
            raise ValueError("payload too large")
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError("expected JSON object")
        return obj

    def _authorized(self) -> bool:
        if not self.token:
            return True
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {self.token}"

    # ---- dispatch ------------------------------------------------------------
    def _route(self, method: str) -> None:
        if not self._authorized():
            self._send(401, {"error": "unauthorized"})
            return
        path = urlsplit(self.path).path.rstrip("/") or "/"
        parts = [p for p in path.split("/") if p]
        try:
            if method == "GET" and path == "/":
                self._send(200, {
                    "name": "shard",
                    "endpoints": [
                        "GET /healthz",
                        "GET /workers",
                        "POST /workers  {prefix?}",
                        "GET /workers/<name>",
                        "GET /workers/<name>/history",
                        "POST /workers/<name>/prompt  {text}",
                        "POST /workers/<name>/reply  {text}",
                        "POST /workers/<name>/fork",
                        "POST /workers/<name>/interrupt",
                        "POST /workers/<name>/pause",
                        "POST /workers/<name>/resume",
                        "DELETE /workers/<name>",
                    ],
                })
                return
            if method == "GET" and path == "/healthz":
                self._send(200, {"ok": True})
                return
            if method == "GET" and parts == ["workers"]:
                self._send(200, {"workers": self.manager.snapshot()})
                return
            if method == "POST" and parts == ["workers"]:
                body = self._read_json()
                prefix = str(body.get("prefix") or "agent")
                name = self.manager.create(prefix=prefix)
                self._send(201, {"name": name})
                return
            if len(parts) >= 2 and parts[0] == "workers":
                name = parts[1]
                worker = self.manager.get(name)
                if worker is None:
                    self._send(404, {"error": "no such worker"})
                    return
                # GETs and pause/resume are always allowed; mutating actions
                # against a paused worker are rejected.
                gated = method == "POST" and parts[2:] in (["prompt"], ["reply"], ["fork"], ["interrupt"])
                if gated and not worker.api_enabled():
                    self._send(423, {"error": "worker api disabled (paused)"})
                    return
                if method == "GET" and len(parts) == 2:
                    self._send(200, {
                        "name": worker.name,
                        "busy": worker.is_busy(),
                        "queue": worker.queue_size(),
                        "history_len": len(worker.history),
                        "api_enabled": worker.api_enabled(),
                    })
                    return
                if method == "GET" and parts[2:] == ["history"]:
                    self._send(200, {"history": worker.snapshot_history()})
                    return
                if method == "POST" and parts[2:] == ["prompt"]:
                    body = self._read_json()
                    text = body.get("text")
                    if not isinstance(text, str) or not text.strip():
                        self._send(400, {"error": "missing 'text'"})
                        return
                    self.manager.enqueue(name, text)
                    self._send(202, {"queued": True, "queue": worker.queue_size()})
                    return
                if method == "POST" and parts[2:] == ["reply"]:
                    body = self._read_json()
                    text = body.get("text")
                    if not isinstance(text, str) or not text.strip():
                        self._send(400, {"error": "missing 'text'"})
                        return
                    worker.post_assistant(text)
                    self._send(201, {"posted": True, "history_len": len(worker.history)})
                    return
                if method == "POST" and parts[2:] == ["fork"]:
                    child = self.manager.fork(name)
                    self._send(201, {"name": child})
                    return
                if method == "POST" and parts[2:] == ["interrupt"]:
                    self.manager.interrupt(name)
                    self._send(200, {"interrupted": True})
                    return
                if method == "POST" and parts[2:] == ["pause"]:
                    self.manager.set_api_enabled(name, False)
                    self._send(200, {"api_enabled": False})
                    return
                if method == "POST" and parts[2:] == ["resume"]:
                    self.manager.set_api_enabled(name, True)
                    self._send(200, {"api_enabled": True})
                    return
                if method == "DELETE" and len(parts) == 2:
                    if self.manager.remove(name):
                        self._send(200, {"deleted": True})
                    else:
                        self._send(404, {"error": "no such worker"})
                    return
            self._send(404, {"error": "not found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self) -> None:  # noqa: N802
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._route("POST")

    def do_DELETE(self) -> None:  # noqa: N802
        self._route("DELETE")


class ApiServer:
    """Background HTTP server bound to 127.0.0.1 by default."""

    def __init__(
        self,
        manager: WorkerManager,
        host: str | None = None,
        port: int | None = None,
        token: str | None = None,
    ) -> None:
        self.host = host or os.environ.get("SHARD_API_HOST", DEFAULT_HOST)
        self.port = int(port if port is not None else os.environ.get("SHARD_API_PORT", DEFAULT_PORT))
        self.token = token if token is not None else os.environ.get("SHARD_API_TOKEN", "")
        handler_cls = type(
            "BoundHandler",
            (_Handler,),
            {"manager": manager, "token": self.token},
        )
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler_cls)
        # Get the actual bound port (in case 0 was passed).
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="shard-api",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        try:
            self._httpd.shutdown()
        except Exception:
            pass
        try:
            self._httpd.server_close()
        except Exception:
            pass
