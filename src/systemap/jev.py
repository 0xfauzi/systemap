"""Send typed questions to TypeSafe's Jev and read typed answers.

The module uses `urllib` without external dependencies for the System One HTTP
API: POST /v1/systemone and GET /v1/models. Calls use `TYPESAFE_API_KEY`.
`TYPESAFE_BASE_URL` can select a different server.

Disk caching uses `[jev] cache`, with `.systemap/jev-cache.json` as the default.
Each key hashes model name, release date, state, and questions.
Unchanged questions use cached answers. A new model release changes the keys.
The release date comes from GET /v1/models at the start of each run.
That call uses no model tokens.

Rate limits, overload, server errors, and connection errors cause retries with
backoff. A terminal error raises `JevError` with the status and API message.
Received answers stay cached. The next run can continue without duplicate calls.
No error is replaced by a guessed answer.

Tests inject `send`: a function from method, path, and body to parsed JSON.
It supplies recorded responses from API calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API = "https://api.typesafe.ai/v1"
KEY_ENV = "TYPESAFE_API_KEY"
BASE_ENV = "TYPESAFE_BASE_URL"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504, 529})
ATTEMPTS = 4
TIMEOUT = 60.0
CONCURRENCY = 8

Send = Callable[[str, str, "dict[str, Any] | None"], "dict[str, Any]"]
Answers = dict[str, dict[str, Any]]


class JevError(Exception):
    """A Jev call cannot complete. The message gives the cause."""


class _Retryable(Exception):
    def __init__(self, status: int, text: str) -> None:
        super().__init__(f"{status} {text}")
        self.status = status
        self.text = text


def _message(status: int, text: str) -> str:
    try:
        detail = json.loads(text).get("detail", text)
        if isinstance(detail, dict):
            detail = detail.get("message", detail)
    except (ValueError, AttributeError):
        detail = text
    return f"Jev answered {status}: {str(detail)[:300]}"


def http_send(key: str, base: str = API) -> Send:
    """Send one HTTPS request per call, with JSON input and output."""

    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            base.rstrip("/") + path,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                parsed: dict[str, Any] = json.loads(resp.read())
                return parsed
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in RETRY_STATUSES:
                raise _Retryable(exc.code, text) from exc
            raise JevError(_message(exc.code, text)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise _Retryable(0, str(exc)) from exc

    return send


def with_retries(send: Send, attempts: int = ATTEMPTS, pause: float = 0.5) -> Send:
    """Try rate limits, overload, server errors, and connection errors again with backoff."""

    def retrying(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        for attempt in range(attempts):
            try:
                return send(method, path, body)
            except _Retryable as exc:
                if attempt == attempts - 1:
                    raise JevError(_message(exc.status, exc.text)) from exc
                time.sleep(pause * 2**attempt * (1 + random.random()))
        raise AssertionError("unreachable")

    return retrying


@dataclass(frozen=True)
class Ask:
    """One request with a caller-selected key, state, and questions."""

    key: str
    state: Any
    questions: dict[str, dict[str, Any]]

    def chars(self) -> int:
        return len(json.dumps(self.state)) + len(json.dumps(self.questions))


def cache_key(model: str, release: str, ask: Ask) -> str:
    blob = json.dumps(
        [model, release, ask.state, ask.questions], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode()).hexdigest()


class Cache:
    """Keep disk answers by `cache_key` and replace the full file through a temporary file.

    `systemap.agent` also keeps responses here. Each caller selects its data format.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.entries: dict[str, Any] = {}
        if path is not None and path.exists():
            try:
                self.entries = json.loads(path.read_text(encoding="utf-8")).get("entries", {})
            except (ValueError, AttributeError):
                self.entries = {}

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "entries": self.entries}), encoding="utf-8")
        tmp.replace(self.path)


@dataclass
class Usage:
    """Record sent calls, cached answers, and input/output tokens."""

    sent: int = 0
    cached: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    models: set[str] = field(default_factory=set)

    def line(self) -> str:
        served = f"{self.sent} sent, {self.cached} from the cache"
        tokens = f"{self.input_tokens:,} input and {self.output_tokens:,} output tokens"
        model = ", ".join(sorted(self.models)) or "no model called"
        return f"jev: {served}; {tokens}; {model}"


class Jev:
    """Get answers from one model, using cached answers when available."""

    def __init__(self, send: Send, model: str = "jev-latest", cache: Cache | None = None) -> None:
        self.send = send
        self.model = model
        self.cache = cache or Cache(None)
        self.usage = Usage()
        self._release: str | None = None

    def release(self) -> str:
        """Read the model release date one time per run for all cache keys."""
        if self._release is None:
            listed = self.send("GET", "/models", None).get("models", [])
            dates = [m.get("release_date", "") for m in listed if m.get("name") == self.model]
            if not dates:
                names = ", ".join(sorted(m.get("name", "") for m in listed))
                raise JevError(f"model {self.model} is not available. The API lists: {names}")
            self._release = dates[0]
        return self._release

    def pending(self, asks: list[Ask]) -> list[Ask]:
        """Get questions without cached answers."""
        release = self.release()
        return [a for a in asks if cache_key(self.model, release, a) not in self.cache.entries]

    def _one(self, ask: Ask) -> Answers:
        body = {"model": self.model, "state": ask.state, "questions": ask.questions}
        resp = self.send("POST", "/systemone", body)
        usage = resp.get("usage") or {}
        self.usage.input_tokens += usage.get("input_tokens") or 0
        self.usage.output_tokens += usage.get("output_tokens") or 0
        self.usage.models.add(str(resp.get("model", self.model)))
        answers: Answers = resp["answers"]
        return answers

    def ask(self, asks: list[Ask], concurrency: int = CONCURRENCY) -> dict[str, Answers]:
        """Get answers by request key.

        A terminal call error raises JevError.
        Received answers stay in the cache.
        """
        release = self.release()
        keys = {a.key: cache_key(self.model, release, a) for a in asks}
        todo = [a for a in asks if keys[a.key] not in self.cache.entries]
        self.usage.cached += len(asks) - len(todo)
        try:
            with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
                for a, answers in zip(todo, pool.map(self._one, todo), strict=True):
                    self.cache.entries[keys[a.key]] = answers
                    self.usage.sent += 1
        finally:
            self.cache.save()
        return {a.key: self.cache.entries[keys[a.key]] for a in asks}


def from_env(model: str, cache_path: Path | None, send: Send | None = None) -> Jev:
    """Make a client with injected transport, or HTTPS with an environment key."""
    if send is None:
        key = os.environ.get(KEY_ENV, "").strip()
        if not key:
            raise JevError(f"set {KEY_ENV} to call Jev. No data was sent")
        send = http_send(key, os.environ.get(BASE_ENV, "").strip() or API)
    return Jev(with_retries(send), model, Cache(cache_path))


def has_key() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip())
