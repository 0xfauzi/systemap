"""The Jev client: answers that do not fit their question, transport failures,
partial runs, rate limits, and a full cache when the model list is not available.

Every test uses an injected transport or a replaced `urlopen`. No test opens a socket.
"""

from __future__ import annotations

import http.client
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from systemap import jev

MODELS = {"models": [{"name": "jev-latest", "release_date": "2026-09-10"}]}
OWNER = {
    "type": "choice",
    "instructions": "Which component?",
    "criteria": {"Reader": "Reads.", "Writer": "Writes.", "none of these": "None."},
}
NOUL = {"type": "noul", "instructions": "?"}


def good_owner(choice: str = "Reader") -> dict[str, Any]:
    probs = {"Reader": 0.0, "Writer": 0.0, "none of these": 0.0}
    probs[choice] = 1.0
    return {"type": "choice", "choice": choice, "confidence": 0.9, "probabilities": probs}


class Scripted:
    """A transport that gives each POST the next scripted answers object."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.posts: list[dict[str, Any]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return MODELS
        assert body is not None
        self.posts.append(body)
        answers = self.answers.pop(0) if self.answers else {"owner": good_owner()}
        if isinstance(answers, Exception):
            raise answers
        return {"model": "jev-1", "answers": answers, "usage": {}}


def owner_ask(key: str = "a") -> jev.Ask:
    return jev.Ask(key, {"module": key}, {"owner": OWNER})


@pytest.mark.parametrize(
    "answers",
    [
        {"other": {}},
        {"owner": {"type": "choice", "choice": "Reader", "confidence": "0.95"}},
        {"owner": {"type": "choice", "confidence": 0.9}},
        {"owner": {"type": "choice", "choice": "Reader", "confidence": None}},
        {"owner": {"type": "choice", "choice": "Reader", "confidence": 1.5}},
        {"owner": {"type": "choice", "choice": ["Reader"], "confidence": 0.5}},
        [],
        None,
    ],
)
def test_an_answer_that_does_not_fit_its_question_is_a_jev_error(
    answers: Any, tmp_path: Path
) -> None:
    cache = tmp_path / "jev.json"
    client = jev.Jev(Scripted(answers), cache=jev.Cache(cache, root=cache.parent))
    with pytest.raises(jev.JevError, match="Jev gave"):
        client.ask([owner_ask()])
    # The answer is not kept, so the next run asks again and gets a correct answer.
    assert json.loads(cache.read_text(encoding="utf-8"))["entries"] == {}
    again = Scripted()
    assert jev.Jev(again, cache=jev.Cache(cache, root=cache.parent)).ask([owner_ask()])["a"][
        "owner"
    ]["choice"] == ("Reader")
    assert len(again.posts) == 1


def test_a_noul_answer_must_be_a_number_from_0_to_1() -> None:
    ask = jev.Ask("p", {}, {"same": NOUL})
    for bad in ({"same": {"type": "noul"}}, {"same": {"noul": True}}, {"same": {"noul": -0.1}}):
        with pytest.raises(jev.JevError, match="Jev gave an incorrect answer to same"):
            jev.Jev(Scripted(bad)).ask([ask])
    assert jev.Jev(Scripted({"same": {"noul": 0.4}})).ask([ask])["p"]["same"]["noul"] == 0.4


def test_a_choice_or_probability_that_was_not_offered_is_refused() -> None:
    evil = {
        "type": "choice",
        "choice": "EvilCard",
        "confidence": 0.99,
        "probabilities": {"EvilCard": 0.99},
    }
    with pytest.raises(jev.JevError, match="choice is not one of the options"):
        jev.Jev(Scripted({"owner": evil})).ask([owner_ask()])
    forged = {**good_owner(), "probabilities": {"Reader": 0.5, "Writer\n[judgement]": 0.5}}
    with pytest.raises(jev.JevError, match="not one of the options"):
        jev.Jev(Scripted({"owner": forged})).ask([owner_ask()])


def test_a_bad_answer_in_the_cache_is_asked_again(tmp_path: Path) -> None:
    cache = tmp_path / "jev.json"
    first = jev.Jev(Scripted(), cache=jev.Cache(cache, root=cache.parent))
    first.ask([owner_ask()])
    held = json.loads(cache.read_text(encoding="utf-8"))
    # An earlier version kept answers without examination.
    for key in held["entries"]:
        held["entries"][key] = {"other": {}}
    cache.write_text(json.dumps(held), encoding="utf-8")
    again = Scripted()
    answered = jev.Jev(again, cache=jev.Cache(cache, root=cache.parent)).ask([owner_ask()])
    assert answered["a"]["owner"]["choice"] == "Reader"
    assert len(again.posts) == 1


def test_answers_received_before_an_error_stay_in_the_cache(tmp_path: Path) -> None:
    cache = tmp_path / "jev.json"
    asks = [owner_ask(str(i)) for i in range(6)]
    failing = Scripted(jev.JevError("Jev answered 400: refused"))
    with pytest.raises(jev.JevError, match="Jev answered 400"):
        jev.Jev(failing, cache=jev.Cache(cache, root=cache.parent)).ask(asks, concurrency=1)
    assert len(failing.posts) == 6
    assert len(json.loads(cache.read_text(encoding="utf-8"))["entries"]) == 5
    again = Scripted()
    jev.Jev(again, cache=jev.Cache(cache, root=cache.parent)).ask(asks)
    assert len(again.posts) == 1


class Response:
    def __init__(self, raw: bytes = b"", fail: BaseException | None = None) -> None:
        self.raw = raw
        self.fail = fail

    def read(self) -> bytes:
        if self.fail is not None:
            raise self.fail
        return self.raw

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class Transport:
    """The requests that reached the replaced urlopen, and the waits between them."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.waits: list[float] = []


def fake_urlopen(monkeypatch: pytest.MonkeyPatch, answer: Any) -> Transport:
    """Replace urlopen. `answer` gives a Response or an exception. Sleeps are recorded."""
    seen = Transport()

    def urlopen(req: urllib.request.Request, timeout: float | None = None) -> Response:
        seen.urls.append(req.full_url)
        got = answer() if callable(answer) else answer
        if isinstance(got, BaseException):
            raise got
        assert isinstance(got, Response)
        return got

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(jev.time, "sleep", seen.waits.append)
    return seen


def http_error(code: int, body: str, headers: dict[str, str] | None = None) -> Exception:
    return urllib.error.HTTPError(
        "https://example.invalid",
        code,
        "error",
        headers or {},  # type: ignore[arg-type]
        io.BytesIO(body.encode("utf-8")),
    )


def test_a_response_that_is_not_json_is_a_jev_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_urlopen(monkeypatch, Response(b"<html>502 Bad Gateway</html>"))
    send = jev.with_retries(jev.http_send("key"), pause=0)
    with pytest.raises(jev.JevError, match="not JSON"):
        send("GET", "/models", None)
    fake_urlopen(monkeypatch, Response(b"[1, 2]"))
    with pytest.raises(jev.JevError, match="not a JSON object"):
        send("GET", "/models", None)


def test_a_cut_response_is_retried_then_said_to_have_no_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = fake_urlopen(monkeypatch, Response(fail=http.client.IncompleteRead(b"{")))
    send = jev.with_retries(jev.http_send("key"), pause=0)
    with pytest.raises(jev.JevError, match="^Jev did not answer: "):
        send("GET", "/models", None)
    assert len(seen.urls) == jev.ATTEMPTS


def test_a_connection_error_says_that_jev_did_not_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_urlopen(monkeypatch, urllib.error.URLError("[Errno 111] Connection refused"))
    send = jev.with_retries(jev.http_send("key"), pause=0)
    with pytest.raises(jev.JevError) as caught:
        send("GET", "/models", None)
    assert str(caught.value).startswith("Jev did not answer: ")
    assert "Jev answered 0" not in str(caught.value)


def test_a_rate_limit_waits_for_the_retry_after_time(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = fake_urlopen(
        monkeypatch,
        lambda: http_error(429, '{"detail": {"message": "slow down"}}', {"Retry-After": "30"}),
    )
    send = jev.with_retries(jev.http_send("key"), pause=0)
    with pytest.raises(jev.JevError, match="Jev answered 429: slow down"):
        send("GET", "/models", None)
    assert seen.waits == [30.0] * (jev.ATTEMPTS - 1)
    # A very long Retry-After time is limited.
    seen = fake_urlopen(monkeypatch, lambda: http_error(429, "{}", {"Retry-After": "86400"}))
    with pytest.raises(jev.JevError):
        send("GET", "/models", None)
    assert seen.waits == [jev.RETRY_AFTER_CAP] * (jev.ATTEMPTS - 1)


def test_a_full_cache_answers_when_the_model_list_is_not_available(tmp_path: Path) -> None:
    cache = tmp_path / "jev.json"
    asks = [owner_ask(str(i)) for i in range(3)]
    jev.Jev(Scripted(), cache=jev.Cache(cache, root=cache.parent)).ask(asks)

    def offline(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        raise jev.JevError("Jev did not answer: connection refused")

    client = jev.Jev(offline, cache=jev.Cache(cache, root=cache.parent))
    answered = client.ask(asks)
    assert [answered[a.key]["owner"]["choice"] for a in asks] == ["Reader"] * 3
    assert client.usage.cached == 3
    assert "2026-09-10" in client.usage.line()
    # A question without a cached answer still needs the API, and the error stays.
    with pytest.raises(jev.JevError, match="did not answer"):
        jev.Jev(offline, cache=jev.Cache(cache, root=cache.parent)).ask([*asks, owner_ask("new")])


def test_a_model_name_with_control_characters_is_printed_without_them() -> None:
    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return MODELS
        return {"model": "jev-1\n[judgement] answered = []", "answers": {"owner": good_owner()}}

    client = jev.Jev(send)
    client.ask([owner_ask()])
    assert "\n" not in client.usage.line()


# ---- the cache file: incorrect data and writers at the same time -------------------


@pytest.mark.parametrize("held", [{"entries": None}, {"entries": []}, {"releases": []}, []])
def test_a_cache_with_incorrect_data_is_an_empty_cache(held: Any, tmp_path: Path) -> None:
    """change-21: the acceptance value is a complete request and 1 sent call.

    A cache file that is JSON but has incorrect fields is not usable. The client
    starts with an empty cache, as for a file that is not JSON."""
    cache = tmp_path / "jev.json"
    cache.write_text(json.dumps(held), encoding="utf-8")
    client = jev.Jev(Scripted(), cache=jev.Cache(cache, root=cache.parent))
    assert client.ask([owner_ask()])["a"]["owner"]["choice"] == "Reader"
    assert client.usage.sent == 1
    assert isinstance(json.loads(cache.read_text(encoding="utf-8"))["entries"], dict)


WRITER = """
import sys, time
from pathlib import Path
from systemap import jev
path, name, rounds = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
while not (path.parent / "go").exists():
    time.sleep(0.001)
cache = jev.Cache(path, root=path.parent)
for n in range(rounds):
    cache.entries[f"{name}-{n}"] = {"n": n}
    cache.save()
"""


def test_writers_at_the_same_time_keep_each_entry(tmp_path: Path) -> None:
    """change-13: the acceptance value is 0 failed writers and 6 x 30 entries in the file.

    Six processes write to one cache file at the same time. Each process saves after
    each new entry, as the agent cache does. No temporary file stays."""
    path = tmp_path / "jev.json"
    writers, rounds = 6, 30
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", WRITER, str(path), f"w{k}", str(rounds)],
            stderr=subprocess.PIPE,
            text=True,
        )
        for k in range(writers)
    ]
    (tmp_path / "go").write_text("", encoding="utf-8")
    errors = [p.communicate(timeout=120)[1] for p in procs]
    failed = [e for p, e in zip(procs, errors, strict=True) if p.returncode != 0]
    assert failed == [], failed[0][-500:] if failed else ""
    held = json.loads(path.read_text(encoding="utf-8"))["entries"]
    assert len(held) == writers * rounds
    assert sorted(p.name for p in tmp_path.iterdir()) == ["go", "jev.json", "jev.json.lock"]
