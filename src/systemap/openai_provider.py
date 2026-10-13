"""Use OpenAI Decisions as a decision provider.

`OpenAIProvider` implements `systemap.decision.DecisionProvider` on the OpenAI
Decisions API (public beta): POST https://api.openai.com/v1/decisions.
Calls use `OPENAI_API_KEY`. The provider operates only when the user selects it
(`--provider openai` or `[decisions] provider = "openai"`). The key alone does not
select it.

A request has one `input` text and a list of questions. The input is the JSON text of
the question state. A choice question becomes a `choice` question with the options as
`choices`. A predicate question becomes a `predicate` question. Questions with an
identical state go in one request. Two questions with the same name go in different
requests, because the API identifies an answer by its name.

The API can give a refusal for one question. The other questions of the request still
get answers. A refusal becomes `decision.Refusal`. The raw answer of each question is
kept as metadata.

Each answer must agree with its question before the cache keeps it. An answer that
does not agree raises `OpenAIError`. The cache does not keep a refusal, so the next run
asks again. The cache is `jev.Cache`, and the key is `jev.cache_key` with the provider
name and the model as the model part. Thus a Jev answer is never read as an OpenAI
answer.

Rate limits, overload, server errors, and connection errors cause retries with backoff.
A terminal error raises `OpenAIError` with the status and the API message.
No error is replaced by a guessed answer or by a different provider.

Tests inject `send`: a function from method, path, and body to parsed JSON.
"""

from __future__ import annotations

import http.client
import json
import math
import os
import random
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from systemap import jev
from systemap.decision import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionError,
    PredicateAnswer,
    Question,
    Refusal,
)

NAME = "openai"
API = "https://api.openai.com/v1"
PATH = "/decisions"
KEY_ENV = "OPENAI_API_KEY"
MODEL = "gpt-6-luna"
# The release part of the cache key. The API gives no release date. A change of the
# request form must change this value.
FORMAT = "decisions-1"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
ATTEMPTS = 4
TIMEOUT = 60.0
CONCURRENCY = 8
RETRY_AFTER_CAP = 60.0


class OpenAIError(DecisionError):
    """An OpenAI Decisions call cannot complete. The message gives the cause."""


class _Retryable(Exception):
    def __init__(self, status: int, text: str, wait: float | None = None) -> None:
        super().__init__(f"{status} {text}")
        self.status = status
        self.text = text
        self.wait = wait


# ---- the request ----------------------------------------------------------------


def evidence(state: Any) -> str:
    """Give the input text of a question state: its JSON text."""
    return json.dumps(state)


def question_body(question: Question) -> dict[str, Any]:
    """Give the API form of one question."""
    if isinstance(question, ChoiceQuestion):
        choices = [{"value": k, "description": v} for k, v in question.options.items()]
        return {
            "type": "choice",
            "name": question.name,
            "instructions": question.instructions,
            "choices": choices,
        }
    return {"type": "predicate", "name": question.name, "instructions": question.instructions}


def request_body(model: str, questions: Sequence[Question]) -> dict[str, Any]:
    """Give the body of one request. All the questions must have the same state."""
    return {
        "model": model,
        "input": evidence(questions[0].state),
        "questions": [question_body(q) for q in questions],
    }


def batches(questions: Sequence[Question]) -> list[list[Question]]:
    """Put the questions with an identical state into one request, one name per request."""
    groups: dict[str, list[list[Question]]] = {}
    for q in questions:
        requests = groups.setdefault(evidence(q.state), [])
        free = next((r for r in requests if all(x.name != q.name for x in r)), None)
        if free is None:
            requests.append([q])
        else:
            free.append(q)
    return [r for requests in groups.values() for r in requests]


def cache_key(model: str, question: Question) -> str:
    """Give the cache key of one question. The provider name and the model are in the key."""
    ask = jev.Ask(question.key, question.state, {question.name: question_body(question)})
    return jev.cache_key(f"{NAME}/{model}", FORMAT, ask)


def chars(questions: Sequence[Question]) -> int:
    """Count the JSON characters of the request bodies."""
    return sum(len(json.dumps(request_body(MODEL, b))) for b in batches(questions))


# ---- the answer must agree with its question -------------------------------------


def _fraction(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return math.isfinite(value) and 0 <= value <= 1


def _spread(question: ChoiceQuestion, raw: dict[str, Any]) -> dict[str, float] | str:
    """Give the probability of each option, or the reason that the list is incorrect."""
    given = raw.get("probabilities", [])
    if not isinstance(given, list):
        return "probabilities is not a list"
    out: dict[str, float] = {}
    for item in given:
        if not isinstance(item, dict) or item.get("value") not in question.options:
            return "a probability names an option that is not one of the options"
        if not _fraction(item.get("probability")):
            return "a probability is not a number from 0 to 1"
        out[item["value"]] = float(item["probability"])
    absent = [name for name in question.needs if name not in out]
    return f"no probability for {absent[0]}" if absent else out


def _choice(question: ChoiceQuestion, raw: dict[str, Any]) -> Answer | str:
    if raw.get("choice") not in question.options:
        return "choice is not one of the options"
    if not _fraction(raw.get("confidence")):
        return "confidence is not a number from 0 to 1"
    spread = _spread(question, raw)
    if isinstance(spread, str):
        return spread
    return ChoiceAnswer(raw["choice"], spread, float(raw["confidence"]), raw)


def _predicate(raw: dict[str, Any]) -> Answer | str:
    if not _fraction(raw.get("probability")):
        return "probability is not a number from 0 to 1"
    return PredicateAnswer(float(raw["probability"]), raw)


def _refusal(raw: dict[str, Any]) -> Refusal:
    text = raw.get("reason") or raw.get("refusal") or "the API gave no reason"
    return Refusal(jev.printable(str(text)), raw)


def answer_of(question: Question, raw: Any) -> Answer:
    """Make the answer record from one API answer, or raise OpenAIError."""
    if not isinstance(raw, dict):
        raise OpenAIError(f"OpenAI gave no answer to {question.name} for {question.key}")
    kind = raw.get("type")
    if kind == "refusal":
        return _refusal(raw)
    if isinstance(question, ChoiceQuestion):
        made = _choice(question, raw) if kind == "choice" else "the answer is not a choice"
    else:
        made = _predicate(raw) if kind == "predicate" else "the answer is not a predicate"
    if isinstance(made, str):
        key = jev.printable(question.key)
        raise OpenAIError(f"OpenAI gave an incorrect answer to {question.name} for {key}: {made}")
    return made


# ---- the transport ------------------------------------------------------------


def _message(status: int, text: str) -> str:
    if status == 0:
        return f"OpenAI did not answer: {jev.printable(text)}"
    try:
        detail = json.loads(text).get("error", text)
        if isinstance(detail, dict):
            detail = detail.get("message", detail)
    except (ValueError, AttributeError):
        detail = text
    return f"OpenAI answered {status}: {jev.printable(str(detail))}"


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
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
        raise OpenAIError("OpenAI gave a response that is not JSON") from exc
    if not isinstance(parsed, dict):
        raise OpenAIError("OpenAI gave a response that is not a JSON object")
    return parsed


def http_send(key: str, base: str = API) -> jev.Send:
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
            raise OpenAIError(_message(exc.code, text)) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise _Retryable(0, str(exc) or type(exc).__name__) from exc
        return _parsed(raw)

    return send


def with_retries(send: jev.Send, attempts: int = ATTEMPTS, pause: float = 0.5) -> jev.Send:
    """Try rate limits, overload, server errors, and connection errors again with backoff."""

    def retrying(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        for attempt in range(attempts):
            try:
                return send(method, path, body)
            except _Retryable as exc:
                if attempt == attempts - 1:
                    raise OpenAIError(_message(exc.status, exc.text)) from exc
                wait = pause * (2.0**attempt) * (1 + random.random())
                time.sleep(wait if exc.wait is None else max(wait, min(exc.wait, RETRY_AFTER_CAP)))
        raise AssertionError("unreachable")

    return retrying


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


# ---- the provider ---------------------------------------------------------------


class OpenAIProvider:
    """Give the answers of one OpenAI Decisions model. Cached answers are used when available."""

    name = NAME

    def __init__(self, send: jev.Send, model: str = MODEL, cache: jev.Cache | None = None) -> None:
        self.send = send
        self.model = model
        self.cache = cache or jev.Cache(None)
        self.usage = jev.Usage(provider=NAME)
        self._lock = threading.Lock()

    def _held(self, question: Question) -> Answer | None:
        raw = self.cache.entries.get(cache_key(self.model, question))
        if raw is None:
            return None
        try:
            return answer_of(question, raw)
        except OpenAIError:
            return None

    def pending(self, questions: Sequence[Question]) -> int:
        """Count the questions without a cached answer. No request is sent."""
        return sum(self._held(q) is None for q in questions)

    def _one(self, batch: list[Question]) -> dict[tuple[str, str], Answer]:
        resp = self.send("POST", PATH, request_body(self.model, batch))
        given = resp.get("answers")
        if not isinstance(given, list):
            raise OpenAIError(f"OpenAI gave no answers for {jev.printable(batch[0].key)}")
        by_name = {a.get("name"): a for a in given if isinstance(a, dict)}
        answers = {(q.key, q.name): answer_of(q, by_name.get(q.name)) for q in batch}
        usage = resp.get("usage")
        counted: dict[str, Any] = usage if isinstance(usage, dict) else {}
        with self._lock:
            self.usage.sent += 1
            self.usage.input_tokens += _count(counted.get("input_tokens"))
            self.usage.output_tokens += _count(counted.get("output_tokens"))
            self.usage.models.add(jev.printable(str(resp.get("model", self.model)), 80))
            for q in batch:
                if not isinstance(answers[(q.key, q.name)], Refusal):
                    self.cache.entries[cache_key(self.model, q)] = by_name[q.name]
        return answers

    def decide(self, questions: Sequence[Question]) -> list[Answer]:
        """Give one answer for each question, in sequence.

        A terminal error raises OpenAIError after all other requests complete.
        Received answers stay in the cache.
        """
        found: dict[tuple[str, str], Answer] = {}
        todo: list[Question] = []
        for q in questions:
            held = self._held(q)
            if held is None:
                todo.append(q)
            else:
                found[(q.key, q.name)] = held
        self.usage.cached += len(questions) - len(todo)
        errors: list[OpenAIError] = []
        try:
            with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
                for future in [pool.submit(self._one, b) for b in batches(todo)]:
                    try:
                        found.update(future.result())
                    except OpenAIError as exc:
                        errors.append(exc)
        finally:
            self.cache.save()
        if errors:
            raise errors[0]
        return [found[(q.key, q.name)] for q in questions]


def has_key() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip())


def from_env(model: str, cache_path: Path | None, send: jev.Send | None = None) -> OpenAIProvider:
    """Make the provider with an injected transport, or HTTPS with the environment key."""
    if send is None:
        key = os.environ.get(KEY_ENV, "").strip()
        if not key:
            raise OpenAIError(f"set {KEY_ENV} to call OpenAI. No data was sent")
        send = http_send(key)
    return OpenAIProvider(with_retries(send), model, jev.Cache(cache_path))
