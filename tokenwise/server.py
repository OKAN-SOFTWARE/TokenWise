"""Dependency-free, localhost-only HTTP server for the TokenWise workbench."""
from __future__ import annotations

import json
import mimetypes
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

from .demo import overview
from .engine import Scenario, compare_runs, inspect_prompt, simulate
from .store import Ledger

MAX_BODY = 75_000
ASSETS = {"/": "index.html", "/index.html": "index.html",
          "/static/style.css": "style.css", "/static/app.js": "app.js",
          "/static/favicon.svg": "favicon.svg"}


class TokenWiseServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], db_path: Path):
        super().__init__(address, TokenWiseHandler)
        self.ledger = Ledger(db_path)


class TokenWiseHandler(BaseHTTPRequestHandler):
    server: TokenWiseServer
    server_version = "TokenWise/0.1"

    def log_message(self, format: str, *args):
        # Do not log prompt bodies, query-string contents, or tokens.
        print("[TokenWise]", format % args)

    def log_request(self, code="-", size="-"):
        # The standard handler logs the complete request line, including query strings.
        # Preserve request method, path and status without exposing URL parameters.
        safe_path = urlsplit(self.path).path or "/"
        self.log_message('"%s %s %s" %s %s',
                         self.command, safe_path, self.request_version, code, size)

    def _headers(self, code: int, type_: str, length: int):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()

    def _send_json(self, code: int, value: dict | list):
        payload = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def _local_request(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        # No browser-auth or remote exposure in this learning release.
        return host in {"localhost", "127.0.0.1", "[::1]"}

    def do_GET(self):
        if not self._local_request():
            return self._send_json(403, {"error": "Localhost access only"})
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self._send_json(200, {"ok": True, "mode": "offline-first", "aws_calls": False})
        if path == "/api/overview":
            return self._send_json(200, overview())
        if path == "/api/runs":
            return self._send_json(200, {"runs": self.server.ledger.recent()})
        if path in ASSETS:
            content = files("tokenwise").joinpath("static", ASSETS[path]).read_bytes()
            mime = mimetypes.guess_type(ASSETS[path])[0] or "application/octet-stream"
            if mime == "image/svg+xml":
                mime = "image/svg+xml"
            self._headers(200, mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else ""), len(content))
            self.wfile.write(content)
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._local_request():
            return self._send_json(403, {"error": "Localhost access only"})
        origin = self.headers.get("Origin", "")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
                return self._send_json(403, {"error": "Cross-origin POST blocked"})
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send_json(415, {"error": "Expected application/json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send_json(400, {"error": "Invalid Content-Length"})
        if not 0 < length <= MAX_BODY:
            return self._send_json(413, {"error": "Request body must be between 1 and 75000 bytes"})
        try:
            data = json.loads(self.rfile.read(length))
            path = urlsplit(self.path).path
            if path == "/api/simulate":
                scenario = Scenario.parse(data)
                result = simulate(scenario)
                identifier = self.server.ledger.add(asdict(scenario), result)
                return self._send_json(200, {"result": result, "run_id": identifier})
            if path == "/api/inspect":
                if not isinstance(data, dict):
                    raise ValueError("Expected object")
                return self._send_json(200, inspect_prompt(data.get("prompt")))
            if path == "/api/compare":
                if not isinstance(data, dict):
                    raise ValueError("Expected object")
                return self._send_json(200, compare_runs(data.get("rows"), data.get("quality_floor", 4)))
            return self._send_json(404, {"error": "Not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._send_json(400, {"error": str(exc)[:200]})
        except Exception:
            # Do not leak stack traces or local paths to client.
            return self._send_json(500, {"error": "Internal server error"})
