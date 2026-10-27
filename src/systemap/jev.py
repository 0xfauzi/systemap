"""Send typed questions to TypeSafe's Jev and read typed answers.

The module uses `urllib` without external dependencies for the System One HTTP
API: POST /v1/systemone and GET /v1/models. Calls use `TYPESAFE_API_KEY`.
`TYPESAFE_BASE_URL` can select a different server.

Disk caching uses `[jev] cache`, with `.systemap/jev-cache.json` as the default.
Each key hashes model name, release date, state, and questions.
Unchanged questions use cached answers. A new model release changes the keys.
The release date comes from GET /v1/models at the start of each run.
That call uses no model tokens. If that call fails and the cache has an answer
for each question under the last known release, the run uses the cache and says so.

Each answer must agree with its question before the cache keeps it: a choice from
the offered options, and numbers from 0 to 1. An answer that does not agree raises
`JevError`. The cache does not keep it, so the next run asks again.

Rate limits, overload, server errors, and connection errors cause retries with
backoff. A `Retry-After` time sets a longer wait, up to `RETRY_AFTER_CAP` seconds.
A terminal error raises `JevError` with the status and API message.
Received answers stay cached, also when a different question fails.
The next run can continue without duplicate calls.
No error is replaced by a guessed answer.

Tests inject `send`: a function from method, path, and body to parsed JSON.
It supplies recorded responses from API calls.
`systemap.jev_provider` uses this client as a decision provider.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import random
import shlex
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import file_write, git_command, terminal_text
from systemap.decision import DecisionError

API = "https://api.typesafe.ai/v1"
KEY_ENV = "TYPESAFE_API_KEY"
BASE_ENV = "TYPESAFE_BASE_URL"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504, 529})
ATTEMPTS = 4
TIMEOUT = 60.0
CONCURRENCY = 8
# The longest wait that a `Retry-After` header can cause between two attempts.
RETRY_AFTER_CAP = 60.0

Send = Callable[[str, str, "dict[str, Any] | None"], "dict[str, Any]"]
Answers = dict[str, dict[str, Any]]


class JevError(DecisionError):
    """A Jev call cannot complete. The message gives the cause."""


class _Retryable(Exception):
    def __init__(self, status: int, text: str, wait: float | None = None) -> None:
        super().__init__(f"{status} {text}")
        self.status = status
        self.text = text
        self.wait = wait


def printable(text: str, cap: int = 300) -> str:
    """Remove control characters, such as line breaks, from text that a model gave."""
    return "".join(ch if ch.isprintable() else " " for ch in text)[:cap]


def _message(status: int, text: str) -> str:
    if status == 0:
        return f"Jev did not answer: {printable(text)}"
    try:
        detail = json.loads(text).get("detail", text)
        if isinstance(detail, dict):
            detail = detail.get("message", detail)
    except (ValueError, AttributeError):
        detail = text
    return f"Jev answered {status}: {printable(str(detail))}"


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    """Read a `Retry-After` time in seconds. A date or an incorrect value gives None."""
    raw = exc.headers.get("Retry-After") if exc.headers is not None else None
    try:
        seconds = float(raw) if raw is not None else math.nan
    except ValueError:
        return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


def _parsed(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        start = printable(raw[:80].decode("utf-8", "replace"), 80)
        raise JevError(f"Jev gave a response that is not JSON: {start}") from exc
    if not isinstance(parsed, dict):
        raise JevError("Jev gave a response that is not a JSON object")
    return parsed


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
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in RETRY_STATUSES:
                raise _Retryable(exc.code, text, _retry_after(exc)) from exc
            raise JevError(_message(exc.code, text)) from exc
        except (OSError, http.client.HTTPException) as exc:
            # OSError includes URLError, timeouts, and connection resets.
            raise _Retryable(0, str(exc) or type(exc).__name__) from exc
        return _parsed(raw)

    return send


def _pause(exc: _Retryable, pause: float, attempt: int) -> float:
    backoff: float = pause * (2.0**attempt) * (1 + random.random())
    if exc.wait is None:
        return backoff
    return max(backoff, min(exc.wait, RETRY_AFTER_CAP))


def with_retries(send: Send, attempts: int = ATTEMPTS, pause: float = 0.5) -> Send:
    """Try rate limits, overload, server errors, and connection errors again with backoff."""

    def retrying(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        for attempt in range(attempts):
            try:
                return send(method, path, body)
            except _Retryable as exc:
                if attempt == attempts - 1:
                    raise JevError(_message(exc.status, exc.text)) from exc
                time.sleep(_pause(exc, pause, attempt))
        raise AssertionError("unreachable")

    return retrying


@dataclass(frozen=True)
class Ask:
    """One request with a caller-selected key, state, and questions.

    `needs` gives the options whose probabilities each choice answer must give. It is
    not sent and is not part of the cache key.
    """

    key: str
    state: Any
    questions: dict[str, dict[str, Any]]
    needs: tuple[str, ...] = ()

    def chars(self) -> int:
        return len(json.dumps(self.state)) + len(json.dumps(self.questions))


def cache_key(model: str, release: str, ask: Ask) -> str:
    blob = json.dumps(
        [model, release, ask.state, ask.questions], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode()).hexdigest()


# ---- the answer must agree with its question ----------------------------------------


def _fraction(answer: dict[str, Any], key: str) -> str | None:
    value = answer.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return f"{key} is not a number from 0 to 1"
    if not (math.isfinite(value) and 0 <= value <= 1):
        return f"{key} is not a number from 0 to 1"
    return None


def _choice_problem(criteria: dict[str, Any], answer: dict[str, Any]) -> str | None:
    choice = answer.get("choice")
    if not isinstance(choice, str) or choice not in criteria:
        return "choice is not one of the options"
    probabilities = answer.get("probabilities", {})
    if not isinstance(probabilities, dict):
        return "probabilities is not an object"
    if any(name not in criteria for name in probabilities):
        return "a probability names an option that is not one of the options"
    if any(_fraction(probabilities, name) for name in probabilities):
        return "a probability is not a number from 0 to 1"
    return _fraction(answer, "confidence")


def answer_problem(question: dict[str, Any], answer: Any) -> str | None:
    """Give the reason that an answer does not agree with its question, or None."""
    if not isinstance(answer, dict):
        return "the answer is not an object"
    if question.get("type") == "noul":
        return _fraction(answer, "noul")
    if question.get("type") == "choice":
        return _choice_problem(question.get("criteria") or {}, answer)
    return None


def _missing(
    question: dict[str, Any], answer: dict[str, Any], needs: tuple[str, ...]
) -> str | None:
    """Give the first needed option without a probability in a choice answer, or None."""
    if question.get("type") != "choice":
        return None
    given = answer.get("probabilities") or {}
    absent = [name for name in needs if name not in given]
    return f"no probability for {absent[0]}" if absent else None


def checked(ask: Ask, answers: Any) -> Answers:
    """Give the answers to the questions of one request, or raise JevError."""
    if not isinstance(answers, dict):
        raise JevError(f"Jev gave no answers for {printable(ask.key)}")
    out: Answers = {}
    for name, question in ask.questions.items():
        problem = answer_problem(question, answers.get(name)) or _missing(
            question, answers[name], ask.needs
        )
        if problem is not None:
            raise JevError(
                f"Jev gave an incorrect answer to {name} for {printable(ask.key)}: {problem}"
            )
        out[name] = answers[name]
    return out


def _agrees(ask: Ask, answers: Any) -> bool:
    try:
        checked(ask, answers)
    except JevError:
        return False
    return True


def _read_cache(root: Path, path: Path | None) -> tuple[dict[str, Any], dict[str, str]]:
    """Give the entries and the releases of a cache file.

    A file that is not JSON, or that has fields of an incorrect type, is not usable.
    Its answers cannot be read. Thus the result is an empty cache, and the next request
    goes to the provider again. A link out of the root, a FIFO, and a device give
    `file_write.RefusedFile` with the cause. They do not give an empty cache."""
    text = None if path is None else file_write.read_text(root, path)
    if text is None:
        return {}, {}
    try:
        held = json.loads(text)
    except ValueError:
        return {}, {}
    entries = held.get("entries", {}) if isinstance(held, dict) else None
    releases = held.get("releases", {}) if isinstance(held, dict) else None
    if not isinstance(entries, dict) or not isinstance(releases, dict):
        return {}, {}
    return entries, {k: v for k, v in releases.items() if isinstance(v, str)}


# The environment variable that permits a cache file that Git tracks.
TRUST_TRACKED = "SYSTEMAP_TRUST_TRACKED_CACHE"


class UnknownTracking(Exception):
    """Git cannot tell if it tracks a file in a work tree. The text gives the Git cause."""


def tracked(path: Path) -> bool:
    """Tell if Git tracks the file at `path`.

    The check runs in the folder of the real file, after the links are followed. Thus
    it finds a file that a submodule or a nested repository tracks, and a link to a
    tracked file. The name comparison ignores the case of letters, and the result is
    True only for a listed file that is the same file as `path`. Thus a different case
    of the name is also found on a file system that ignores the case of letters.

    If Git cannot do the check and no folder of the real file contains `.git`, the
    result is False. If a folder contains `.git`, the result is UnknownTracking with
    the Git cause. For example, Git refuses a work tree of a different owner."""
    real = path.resolve()
    try:
        proc = git_command.run(
            real.parent, "ls-files", "-z", "--", f":(literal,icase){real.name}", timeout=60
        )
    except git_command.GitError as exc:
        return _not_tracked(real, str(exc))
    if proc.returncode != 0:
        return _not_tracked(real, git_command.cause(proc.stderr, proc.returncode))
    names = [n for n in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
    return any(_same(real.parent / n, real) for n in names)


def _not_tracked(real: Path, cause: str) -> bool:
    """Give False outside a work tree. In a work tree, give UnknownTracking with `cause`."""
    if any((folder / ".git").exists() for folder in real.parents):
        raise UnknownTracking(cause)
    return False


def _same(one: Path, other: Path) -> bool:
    """Tell if the two paths are the same file. A missing file gives False."""
    try:
        return os.path.samefile(one, other)
    except OSError:
        return False


def tracked_note(root: Path, path: Path) -> str:
    """Give the warning for a cache file that Git tracks and that the cache does not use.

    The command in the warning operates in the repository of the real file. This can be
    a submodule. For a link, the real file is the target of the link."""
    rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    real = path.resolve()
    top = root.resolve()
    folder = real.parent.relative_to(top) if real.parent.is_relative_to(top) else real.parent
    command = shlex.join(["git", "-C", folder.as_posix(), "rm", "--cached", real.name])
    return (
        f"systemap did not read or write the cache file {rel}, because Git tracks it. "
        "A cloned repository can supply the answers in such a file. "
        f"If you trust the answers in this file, set {TRUST_TRACKED}=1. "
        f"If you do not trust them, remove the file from Git: {command}"
    )


def unknown_note(root: Path, path: Path, cause: str) -> str:
    """Give the warning for a cache file that the cache does not use, because Git cannot
    tell if it tracks the file."""
    rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    return (
        f"systemap did not read or write the cache file {rel}, because Git cannot tell "
        f"if it tracks the file: {cause}. "
        "A cloned repository can supply the answers in such a file. "
        f"If you trust the answers in this file, set {TRUST_TRACKED}=1."
    )


def _refused(root: Path, path: Path) -> bool:
    """Tell if the cache must not use a file that Git tracks. If so, give the warning.

    If Git cannot do the check in a work tree, the cache also does not use the file."""
    note = "" if os.environ.get(TRUST_TRACKED) == "1" else _warning(root, path)
    if note:
        print(terminal_text.printable(note), file=sys.stderr)
    return bool(note)


def _warning(root: Path, path: Path) -> str:
    """Give the warning for a cache file that the cache must not use, or an empty string."""
    try:
        return tracked_note(root, path) if tracked(path) else ""
    except UnknownTracking as exc:
        return unknown_note(root, path, str(exc))


class Cache:
    """Keep disk answers by `cache_key` and replace the full file through a temporary file.

    `systemap.agent` also keeps responses here. Each caller selects its data format.
    `releases` keeps the last release date that the API gave for each model.

    Two commands can save the same cache at the same time. A save holds a lock on the
    cache. Then it reads the entries of the other writers and adds its own entries.
    It writes the result through a temporary file of its own. The first read of an
    existing file also holds the lock.

    A cache file has a root: the repository root for a configured cache. The file and
    each folder of it must be in the root (`file_write`). A path without a root gives
    ValueError, so that a caller cannot forget the root.

    A cache file that Git tracks can come from a cloned repository. Its answers are then
    not from a provider or an agent on this computer. Thus the cache does not read or
    write such a file, and `refused` is True. A warning on stderr gives the file. If the
    environment sets SYSTEMAP_TRUST_TRACKED_CACHE=1, the cache uses the file."""

    def __init__(self, path: Path | None = None, *, root: Path | None = None) -> None:
        if path is not None and root is None:
            raise ValueError(f"The cache file {path} needs the root folder that contains it.")
        self.path = path
        self.root = root or Path()
        self.entries: dict[str, Any] = {}
        self.releases: dict[str, str] = {}
        if path is not None:
            file_write.confined(self.root, path)
        self.refused = path is not None and path.exists() and _refused(self.root, path)
        if path is not None and path.exists() and not self.refused:
            # On Windows, a read cannot occur while a different process replaces the file.
            with file_write.locked(self.root, path):
                self.entries, self.releases = _read_cache(self.root, path)

    def save(self) -> None:
        if self.path is None or self.refused:
            return
        with file_write.locked(self.root, self.path):
            entries, releases = _read_cache(self.root, self.path)
            entries.update(self.entries)
            releases.update(self.releases)
            self.entries, self.releases = entries, releases
            held = {"version": 1, "entries": entries, "releases": releases}
            file_write.write_atomic(self.root, self.path, json.dumps(held))


@dataclass
class Usage:
    """Record sent calls, cached answers, and input/output tokens.

    `provider` is the first word of the usage line. The line has the same form for
    each decision provider.
    """

    sent: int = 0
    cached: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    models: set[str] = field(default_factory=set)
    note: str = ""
    provider: str = "jev"

    def line(self) -> str:
        served = f"{self.sent} sent, {self.cached} from the cache"
        tokens = f"{self.input_tokens:,} input and {self.output_tokens:,} output tokens"
        model = ", ".join(sorted(self.models)) or "no model called"
        tail = f". {self.note}" if self.note else ""
        return f"{self.provider}: {served}; {tokens}; {model}{tail}"


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


class Jev:
    """Get answers from one model, using cached answers when available."""

    def __init__(self, send: Send, model: str = "jev-latest", cache: Cache | None = None) -> None:
        self.send = send
        self.model = model
        self.cache = cache or Cache(None)
        self.usage = Usage()
        self._release: str | None = None
        self._lock = threading.Lock()

    def release(self) -> str:
        """Read the model release date one time per run for all cache keys."""
        if self._release is None:
            listed = self.send("GET", "/models", None).get("models", [])
            if not isinstance(listed, list):
                raise JevError("Jev gave a model list that is not a list")
            models = [m for m in listed if isinstance(m, dict)]
            dates = [str(m.get("release_date", "")) for m in models if m.get("name") == self.model]
            if not dates:
                names = ", ".join(sorted(printable(str(m.get("name", ""))) for m in models))
                raise JevError(f"model {self.model} is not available. The API lists: {names}")
            self._release = dates[0]
            self.cache.releases[self.model] = self._release
        return self._release

    def _held(self, release: str, ask: Ask) -> bool:
        key = cache_key(self.model, release, ask)
        return key in self.cache.entries and _agrees(ask, self.cache.entries[key])

    def pending(self, asks: list[Ask]) -> list[Ask]:
        """Get questions without cached answers."""
        release = self.release()
        return [a for a in asks if not self._held(release, a)]

    def _release_for(self, asks: list[Ask]) -> str:
        """Get the release, or the last known release if the cache has every answer."""
        try:
            return self.release()
        except JevError as exc:
            known = self.cache.releases.get(self.model)
            if known is None or not all(self._held(known, a) for a in asks):
                raise
            self.usage.note = (
                f"The model list was not available ({exc}). "
                f"The answers come from the cache for release {printable(known, 40)}"
            )
            return known

    def _one(self, ask: Ask) -> Answers:
        body = {"model": self.model, "state": ask.state, "questions": ask.questions}
        resp = self.send("POST", "/systemone", body)
        answers = checked(ask, resp.get("answers"))
        given = resp.get("usage")
        usage: dict[str, Any] = given if isinstance(given, dict) else {}
        with self._lock:
            self.usage.input_tokens += _count(usage.get("input_tokens"))
            self.usage.output_tokens += _count(usage.get("output_tokens"))
            self.usage.models.add(printable(str(resp.get("model", self.model)), 80))
        return answers

    def ask(self, asks: list[Ask], concurrency: int = CONCURRENCY) -> dict[str, Answers]:
        """Get answers by request key.

        A terminal call error raises JevError after all other requests complete.
        Received answers stay in the cache.
        """
        if not asks:
            return {}
        release = self._release_for(asks)
        keys = {a.key: cache_key(self.model, release, a) for a in asks}
        todo = [a for a in asks if not self._held(release, a)]
        self.usage.cached += len(asks) - len(todo)
        failed: dict[str, JevError] = {}
        try:
            with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
                futures = {pool.submit(self._one, a): a for a in todo}
                for future in as_completed(futures):
                    self._keep(futures[future], future, keys, failed)
        finally:
            self.cache.save()
        first = next((failed[a.key] for a in todo if a.key in failed), None)
        if first is not None:
            raise first
        return {a.key: self.cache.entries[keys[a.key]] for a in asks}

    def _keep(
        self, ask: Ask, future: Any, keys: dict[str, str], failed: dict[str, JevError]
    ) -> None:
        """Keep one received answer in the cache, or record its error."""
        try:
            answers = future.result()
        except JevError as exc:
            failed[ask.key] = exc
            return
        self.cache.entries[keys[ask.key]] = answers
        self.usage.sent += 1


def from_env(
    model: str, cache_path: Path | None, send: Send | None = None, root: Path | None = None
) -> Jev:
    """Make a client with injected transport, or HTTPS with an environment key.

    `root` is the folder that contains the cache file: the repository root."""
    if send is None:
        key = os.environ.get(KEY_ENV, "").strip()
        if not key:
            raise JevError(f"set {KEY_ENV} to call Jev. No data was sent")
        send = http_send(key, os.environ.get(BASE_ENV, "").strip() or API)
    return Jev(with_retries(send), model, Cache(cache_path, root=root))


def has_key() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip())
