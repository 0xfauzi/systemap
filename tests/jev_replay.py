"""Jev's real answers, recorded once and replayed, so the tests send nothing.

A recording maps the hash of each request (method, path and body) to the
response the API gave. Replaying a request the recording does not hold
fails the test with the way to fix it: when a question or the state it reads
changes, the answers must be recorded again, against the real API:

    SYSTEMAP_RECORD_JEV=1 TYPESAFE_API_KEY=... uv run pytest tests/test_audit.py

`serve` puts the same recording behind a local HTTP server, so a test can
drive the CLI end to end through `urllib` with TYPESAFE_BASE_URL pointing at it.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from systemap import jev

FIXTURES = Path(__file__).parent / "fixtures"
# The real key, read before any test replaces it with a placeholder.
REAL_KEY = os.environ.get(jev.KEY_ENV, "")


def request_key(method: str, path: str, body: dict[str, Any] | None) -> str:
    blob = json.dumps([method, path, body], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


class Recording:
    """A file of recorded responses; in record mode, the real API fills it."""

    def __init__(self, name: str) -> None:
        self.path = FIXTURES / f"{name}.json"
        self.responses: dict[str, Any] = (
            json.loads(self.path.read_text()) if self.path.exists() else {}
        )
        self.recording = os.environ.get("SYSTEMAP_RECORD_JEV") == "1"
        self.sent: list[tuple[str, str]] = []

    def send(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        self.sent.append((method, path))
        key = request_key(method, path, body)
        if key not in self.responses:
            if not self.recording:
                raise AssertionError(
                    f"no recorded answer for {method} {path} in {self.path.name}; the question "
                    "or its state changed: record again with SYSTEMAP_RECORD_JEV=1 and a key"
                )
            real = jev.http_send(REAL_KEY)
            self.responses[key] = real(method, path, body)
            self.path.write_text(json.dumps(self.responses, indent=1, sort_keys=True) + "\n")
        answer: dict[str, Any] = self.responses[key]
        return answer


@contextmanager
def serve(recording: Recording) -> Iterator[str]:
    """The recording behind http://127.0.0.1:<port>/v1, for the CLI to call."""

    class Handler(BaseHTTPRequestHandler):
        def _answer(self, body: dict[str, Any] | None) -> None:
            path = self.path.removeprefix("/v1")
            try:
                out = json.dumps(recording.send(self.command, path, body)).encode()
                self.send_response(200)
            except AssertionError as exc:
                out = json.dumps({"detail": {"message": str(exc)}}).encode()
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def do_GET(self) -> None:  # noqa: N802 - the stdlib's name
            self._answer(None)

        def do_POST(self) -> None:  # noqa: N802 - the stdlib's name
            length = int(self.headers.get("Content-Length", 0))
            self._answer(json.loads(self.rfile.read(length)))

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        server.server_close()
