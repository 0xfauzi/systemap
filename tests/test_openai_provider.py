"""OpenAI Decisions as a second decision provider, selected only by the user.

Acceptance values:

- With `OPENAI_API_KEY` set and no selection, each command that asks questions (audit,
  triage, plan, `suggest --jev`, `delta --jev`) sends zero requests to OpenAI. The test
  uses a Python fixture and a TypeScript fixture for delta.
- With OpenAI selected, the request body agrees with the documented form
  (`fixtures/openai_decisions.json`): `model`, `input`, and `questions`, with a
  `predicate` or a `choice` question and its `choices`.
- A refusal gives no finding and no crash for each question type that OpenAI can use:
  the audit questions (owner, sentence, flow, governs) and the owner question of
  `delta --jev`. The other question types have no measured value for OpenAI. They send
  zero requests and give the reason.
- A failed request stops the command with exit 1 and the reason. No other provider
  answers.
- The cache key has the provider name and the model. A Jev answer is never read as an
  OpenAI answer.

The transport is injected (`send`), with the recorded response of the live request.
No test calls OpenAI or Jev.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, Sample, init_two_cards, write_tree
from test_decision_providers import tree_of
from test_delta_jev import git, renamed
from test_jev_on_request import renamed_ts

from systemap import audit, decision, delta_jev, extract, jev, jev_cli, jev_provider
from systemap import openai_provider as oa
from systemap.cli import main
from systemap.config import ConfigError
from systemap.config import load as load_config
from systemap.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionError,
    PredicateAnswer,
    PredicateQuestion,
    Refusal,
)

__all__ = ["git", "renamed", "renamed_ts"]

RECORDED = json.loads((Path(__file__).parent / "fixtures/openai_decisions.json").read_text())
STATE = {"module": "pkg.reader", "docstring": "Read the input files."}
READS = PredicateQuestion("m1", "reads", "Does `module` read input files?", STATE)
OWNER = ChoiceQuestion(
    "m1",
    "owner",
    "Which component has the function of `module`?",
    STATE,
    {"intake": "Reads the input files.", "report": "Writes the report."},
    ("intake",),
)


class Decisions:
    """Answer like OpenAI Decisions, and keep each request.

    A predicate gets the probability in `noul`. A choice gets its first option.
    """

    def __init__(self, refuse: bool = False, noul: float = 0.5) -> None:
        self.refuse = refuse
        self.noul = noul
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        self.requests.append((method, path, body))
        assert body is not None
        answers = [self._answer(q) for q in body["questions"]]
        return {"model": "gpt-6-luna", "answers": answers, "usage": {"input_tokens": 10}}

    def _answer(self, q: dict[str, Any]) -> dict[str, Any]:
        if self.refuse:
            return {"type": "refusal", "name": q["name"]}
        if q["type"] == "predicate":
            return {"type": "predicate", "name": q["name"], "probability": self.noul}
        values = [c["value"] for c in q["choices"]]
        spread = [{"value": v, "probability": 1.0 if v == values[0] else 0.0} for v in values]
        return {
            "type": "choice",
            "name": q["name"],
            "choice": values[0],
            "probabilities": spread,
            "confidence": 1.0,
        }


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> Decisions:
    """An OpenAI key in the environment. Each HTTPS request goes to a counting transport."""
    transport = Decisions()
    monkeypatch.setenv(oa.KEY_ENV, "a test key")
    monkeypatch.setattr(oa, "http_send", lambda key, base=oa.API: transport)
    return transport


@pytest.fixture
def two_cards(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def _run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


# ---- the request ------------------------------------------------------------------


def test_the_request_body_has_the_documented_form() -> None:
    """Golden: the two questions with one state make the recorded request body."""
    assert oa.batches([READS, OWNER]) == [[READS, OWNER]]
    body = oa.request_body("gpt-6-luna", [READS, OWNER])
    assert json.loads(body["input"]) == json.loads(RECORDED["request"]["input"])
    assert {**body, "input": RECORDED["request"]["input"]} == RECORDED["request"]


def test_a_different_state_or_the_same_name_goes_in_a_different_request() -> None:
    other = PredicateQuestion("m2", "reads", "Does `module` read input files?", {"module": "x"})
    again = PredicateQuestion("m3", "reads", "Does `module` read files?", STATE)
    assert oa.batches([READS, other, again, OWNER]) == [[READS, OWNER], [again], [other]]


def test_the_audit_requests_have_the_documented_form(two_cards: Path) -> None:
    transport = Decisions()
    args = argparse.Namespace(
        root_path=two_cards, kind=list(audit.KINDS), dry_run=False, brief=True, provider="openai"
    )
    assert jev_cli.cmd_audit(args, transport) == 0
    assert transport.requests
    for method, path, body in transport.requests:
        assert (method, path) == ("POST", "/decisions")
        assert body is not None and set(body) == {"model", "input", "questions"}
        assert body["model"] == "gpt-6-luna" and isinstance(body["input"], str)
        for q in body["questions"]:
            if q["type"] == "choice":
                assert set(q) == {"type", "name", "instructions", "choices"}
                assert all(set(c) == {"value", "description"} for c in q["choices"])
            else:
                assert set(q) == {"type", "name", "instructions"}
                assert q["type"] == "predicate"


# ---- the answers ------------------------------------------------------------------


def test_the_recorded_answers_become_answer_records() -> None:
    reads, owner = RECORDED["response"]["answers"]
    assert oa.answer_of(READS, reads) == PredicateAnswer(1.0, reads)
    assert oa.answer_of(OWNER, owner) == ChoiceAnswer(
        "intake", {"intake": 1.0, "report": 0.0}, 1.0, owner
    )
    provider = oa.OpenAIProvider(lambda m, p, b: RECORDED["response"])
    assert provider.decide([READS, OWNER]) == [
        PredicateAnswer(1.0, reads),
        ChoiceAnswer("intake", {"intake": 1.0, "report": 0.0}, 1.0, owner),
    ]
    line = "openai: 1 sent, 0 from the cache; 290 input and 0 output tokens; gpt-6-luna"
    assert provider.usage.line() == line


def test_a_refusal_for_one_question_keeps_the_other_answer() -> None:
    owner = RECORDED["response"]["answers"][1]
    response = {**RECORDED["response"], "answers": [RECORDED["refusal"], owner]}
    sends: list[dict[str, Any] | None] = []

    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        sends.append(body)
        return response

    provider = oa.OpenAIProvider(send)
    answers = provider.decide([READS, OWNER])
    assert answers[0] == Refusal("the API gave no reason", RECORDED["refusal"])
    assert isinstance(answers[1], ChoiceAnswer) and answers[1].choice == "intake"
    # The cache keeps the answer, not the refusal: the next run asks only the refused one.
    assert provider.pending([READS, OWNER]) == 1


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ({"type": "choice", "name": "owner", "choice": "other", "confidence": 1.0}, "choice is"),
        (
            {
                "type": "choice",
                "name": "owner",
                "choice": "report",
                "confidence": 1.0,
                "probabilities": [{"value": "report", "probability": 1.0}],
            },
            "no probability for intake",
        ),
        ({"type": "predicate", "name": "owner", "probability": 0.5}, "is not a choice"),
    ],
)
def test_an_answer_that_does_not_agree_raises_and_is_not_cached(
    answer: dict[str, Any], reason: str
) -> None:
    response = {"model": "gpt-6-luna", "answers": [answer]}
    provider = oa.OpenAIProvider(lambda m, p, b: response)
    with pytest.raises(oa.OpenAIError, match=reason):
        provider.decide([OWNER])
    assert provider.pending([OWNER]) == 1


def test_a_failed_request_raises_after_the_retries() -> None:
    calls: list[int] = []

    def busy(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        calls.append(1)
        raise oa._Retryable(503, '{"error": {"message": "overloaded"}}')

    provider = oa.OpenAIProvider(oa.with_retries(busy, attempts=2, pause=0.0))
    with pytest.raises(oa.OpenAIError, match="OpenAI answered 503: overloaded"):
        provider.decide([READS])
    assert len(calls) == 2


def test_a_failed_request_stops_the_command_and_no_other_provider_answers(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refused(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        raise oa.OpenAIError("OpenAI answered 401: incorrect key")

    def no_jev(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the command used Jev")

    monkeypatch.setattr(jev_provider, "from_env", no_jev)
    args = argparse.Namespace(
        root_path=two_cards, kind=[], dry_run=False, brief=True, provider="openai"
    )
    assert jev_cli.cmd_audit(args, refused) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "audit: OpenAI answered 401: incorrect key"


# ---- the cache ----------------------------------------------------------------------


def test_the_cache_key_has_the_provider_and_the_model(tmp_path: Path) -> None:
    key = oa.cache_key("gpt-6-luna", READS)
    assert key != oa.cache_key("gpt-6-other", READS)
    assert key != jev.cache_key("jev-latest", "2026-09-10", jev_provider.ask_of(READS))
    assert key != jev.cache_key("gpt-6-luna", "2026-09-10", jev_provider.ask_of(READS))
    # A cache that Jev wrote for the same question gives no OpenAI answer.
    cache = jev.Cache(tmp_path / "cache.json")
    jev_key = jev.cache_key("jev-latest", "2026-09-10", jev_provider.ask_of(READS))
    cache.entries[jev_key] = {"reads": {"type": "noul", "noul": 0.9}}
    cache.save()
    transport = Decisions(noul=0.25)
    provider = oa.OpenAIProvider(transport, cache=jev.Cache(tmp_path / "cache.json"))
    assert provider.pending([READS]) == 1
    assert provider.decide([READS]) == [
        PredicateAnswer(0.25, transport._answer({"type": "predicate", "name": "reads"}))
    ]
    again = oa.OpenAIProvider(transport, cache=jev.Cache(tmp_path / "cache.json"))
    assert again.decide([READS])[0] == PredicateAnswer(
        0.25, transport._answer({"type": "predicate", "name": "reads"})
    )
    assert len(transport.requests) == 1 and again.usage.cached == 1


# ---- the selection ------------------------------------------------------------------


def test_a_key_without_a_selection_sends_zero_requests_to_openai(
    two_cards: Path, renamed: Path, counted: Decisions, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: with OPENAI_API_KEY and no selection, each command sends 0 requests."""
    assert _run(two_cards, "audit") == 1
    assert _run(two_cards, "triage", "the reader fails") == 1
    assert _run(two_cards, "plan", "change the reader") == 1
    assert _run(two_cards, "suggest", "--jev") == 1
    _run(renamed, "delta", "--base", "HEAD~1", "--jev")
    out = capsys.readouterr().out
    assert out.count("set TYPESAFE_API_KEY") == 5
    assert counted.requests == []


def test_a_key_without_a_selection_sends_zero_requests_for_typescript(
    renamed_ts: Path, counted: Decisions, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(renamed_ts, "delta", "--base", "HEAD~1", "--jev")
    assert counted.requests == []
    _run(renamed_ts, "delta", "--base", "HEAD~1", "--jev", "--provider", "openai")
    assert counted.requests, "the control: an explicit selection sends requests"


def test_the_option_and_the_configuration_select_openai(
    two_cards: Path, counted: Decisions, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(two_cards, "audit", "--provider", "openai") == 0
    by_option = len(counted.requests)
    assert by_option > 0
    (two_cards / ".systemap/openai-cache.json").unlink()
    toml = two_cards / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[decisions]\nprovider = "openai"\n')
    assert _run(two_cards, "audit") == 0
    assert len(counted.requests) == 2 * by_option
    assert _run(two_cards, "audit", "--provider", "jev") == 1
    assert len(counted.requests) == 2 * by_option
    out = capsys.readouterr()
    assert "openai: " in out.out and "set TYPESAFE_API_KEY" in out.out


def test_an_incorrect_provider_name_is_a_configuration_error(two_cards: Path) -> None:
    toml = two_cards / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[decisions]\nprovider = "other"\n')
    with pytest.raises(ConfigError, match='decisions.provider must be "jev" or "openai"'):
        load_config(two_cards)


def test_the_old_decision_table_names_the_decisions_provider_key(two_cards: Path) -> None:
    """Acceptance: a `[decision]` table gives an error that names `[decisions] provider`."""
    toml = two_cards / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[decision]\nprovider = "openai"\n')
    with pytest.raises(
        ConfigError, match=r"does not read the \[decision\] table\. Use \[decisions\] provider"
    ):
        load_config(two_cards)


def test_one_decisions_table_has_the_provider_and_the_limit(two_cards: Path) -> None:
    """Acceptance: `[decisions]` gives the provider and `max_contradicted` together."""
    toml = two_cards / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[decisions]\nprovider = "openai"\nmax_contradicted = 2\n')
    loaded = load_config(two_cards)
    assert (loaded.decision_provider, loaded.max_contradicted) == ("openai", 2)


def test_a_question_type_without_a_measured_value_sends_nothing(
    two_cards: Path, renamed: Path, counted: Decisions, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(two_cards, "triage", "the reader fails", "--provider", "openai") == 1
    assert _run(two_cards, "plan", "change the reader", "--provider", "openai") == 1
    assert _run(two_cards, "suggest", "--jev", "--provider", "openai") == 1
    assert counted.requests == []
    out = capsys.readouterr().out.splitlines()
    assert out == [
        f"triage: {decision.unmeasured('openai', 'triage')}",
        f"plan: {decision.unmeasured('openai', 'plan')}",
        f"suggest --decide: {decision.unmeasured('openai', 'suggest --decide')}",
    ]
    # Audit leaves out the mis-fold question and asks the other types.
    assert _run(two_cards, "audit", "--provider", "openai", "--kind", "decision mis-fold") == 1
    assert counted.requests == []
    assert capsys.readouterr().out == (
        f"audit: {decision.unmeasured('openai', 'decision mis-fold')}\n"
    )
    # Delta leaves out the move question and asks the owner question.
    _run(renamed, "delta", "--base", "HEAD~1", "--jev", "--provider", "openai")
    assert counted.requests
    assert all(q["name"] == "owner" for _m, _p, b in counted.requests for q in b["questions"])
    out = capsys.readouterr().out
    assert decision.unmeasured("openai", "the move question of delta --decide") in out


# ---- refusals -------------------------------------------------------------------------


def test_a_refusal_gives_no_finding_for_each_question_type(sample: Sample) -> None:
    write_tree(
        sample.cfg.root, {"pkg/stray.py": '"""A stray."""\n\ndef stray() -> None:\n    pass\n'}
    )
    facts = extract.build(sample.cfg)
    transport = Decisions(refuse=True)
    provider = oa.OpenAIProvider(transport)
    kinds = [k for k in audit.KINDS if k != "decision mis-fold"]
    assert audit.run(tree_of(sample), facts, sample.cfg, provider, kinds) == []
    names = {q["name"] for _m, _p, b in transport.requests for q in b["questions"]}
    assert names == {"owner", "describes", "holds", "governs"}
    counted = delta_jev.Counted(oa.OpenAIProvider(Decisions(refuse=True)))
    owners = delta_jev.owner_suggestions(
        sample.cfg, tree_of(sample), sample.facts, {"": ["pkg.reader"]}, counted
    )
    assert owners == []
    assert counted.errors() == (
        "delta --decide: the decision provider gave a refusal for 1 questions",
    )


def test_the_openai_thresholds_have_no_value_for_the_failed_types() -> None:
    limits = decision.thresholds("openai")
    assert limits.misfold_below is None and limits.plan_cut is None and not limits.triage
    assert decision.value(limits, "sentence_below") == 0.3
    with pytest.raises(DecisionError, match="no measured value for decision mis-fold"):
        decision.value(limits, "misfold_below")
