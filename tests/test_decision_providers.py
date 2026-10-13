"""The provider-neutral questions and answers, and a provider that refuses.

Acceptance values:

- A refusal from an injected provider gives no finding and no crash for each question
  kind: the four audit questions (owner, sentence, flow, governs), triage, plan,
  `suggest --jev`, and the two `delta --jev` questions (move and owner).
- Triage and plan cannot give a result without an answer. They give the reason and
  exit 1. The other kinds give the count of refused questions.
- The Jev adapter changes a Jev `noul` answer into a predicate answer, and a Jev
  `choice` answer into a choice answer. The raw Jev answer is kept as metadata.
- A provider without measured thresholds causes an error, not a guessed threshold.

The provider is injected. No test calls Jev.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, Sample, init_two_cards, write_tree

from systemap import audit, decision, delta_jev, jev, jev_cli, nest
from systemap.cli import main
from systemap.config import load as load_config
from systemap.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionError,
    PredicateAnswer,
    PredicateQuestion,
    Refusal,
)
from systemap.jev_provider import JevProvider, answer_of, ask_of


class Refusing:
    """A provider that refuses each question. It uses the measured Jev thresholds."""

    name = "jev"

    def __init__(self) -> None:
        self.asked: list[decision.Question] = []
        self.usage = jev.Usage()

    def decide(self, questions: Sequence[decision.Question]) -> list[decision.Answer]:
        self.asked += questions
        return [Refusal("the policy does not permit this question") for _ in questions]


def tree_of(sample: Sample) -> nest.Tree:
    top = nest.Map(
        id="",
        path=sample.cfg.model_path,
        rel="map/model.py",
        model=sample.model,
        meaning=sample.meaning,
        theme=sample.theme,
    )
    return nest.Tree((top,))


@pytest.fixture
def two_cards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Refusing]:
    """The two-card project. The commands get the refusing provider."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    refusing = Refusing()
    monkeypatch.setattr(jev_cli, "_client", lambda cfg, send=None: refusing)
    return tmp_path, refusing


def test_a_refusal_gives_no_audit_finding_for_each_kind(sample: Sample) -> None:
    write_tree(
        sample.cfg.root, {"pkg/stray.py": '"""A stray."""\n\ndef stray() -> None:\n    pass\n'}
    )
    from systemap import extract

    facts = extract.build(sample.cfg)
    refusing = Refusing()
    assert audit.run(tree_of(sample), facts, sample.cfg, refusing, audit.KINDS) == []
    names = {q.name for q in refusing.asked}
    assert names == {"owner", "describes", "holds", "governs"}
    unclaimed = [q.key for q in refusing.asked if q.key == "|owner|pkg.stray"]
    assert unclaimed, "the owner question of a module without a component was asked"


def test_the_audit_report_gives_the_count_of_refused_questions(
    two_cards: tuple[Path, Refusing], capsys: pytest.CaptureFixture[str]
) -> None:
    root, refusing = two_cards
    args = argparse.Namespace(root_path=root, kind=list(audit.KINDS), dry_run=False, brief=True)
    assert jev_cli.cmd_audit(args) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "audit: nothing to confirm"
    assert any(
        line.startswith(
            f"  no answer: the decision provider gave a refusal for {len(refusing.asked)} questions: "
        )
        for line in out
    )


def test_triage_and_plan_give_the_reason_and_exit_1(
    two_cards: tuple[Path, Refusing], capsys: pytest.CaptureFixture[str]
) -> None:
    root, refusing = two_cards
    assert main(["--root", str(root), "triage", "the reader fails"]) == 1
    assert capsys.readouterr().out == (
        "triage: the decision provider gave a refusal: the policy does not permit this question\n"
    )
    assert main(["--root", str(root), "plan", "change the reader"]) == 1
    assert capsys.readouterr().out.startswith("plan: the decision provider gave a refusal")
    assert not (root / ".systemap/plans").exists()
    assert [q.key for q in refusing.asked] == ["triage", "plan"]


def test_suggest_gives_no_pair_for_a_refusal(two_cards: tuple[Path, Refusing]) -> None:
    root, refusing = two_cards
    cfg = load_config(root)
    from systemap import facts_file

    facts = facts_file.read_facts(cfg.facts_path)
    assert facts is not None
    out = jev_cli.suggest_groups(cfg, facts, refusing)
    assert refusing.asked and all(q.name == "same" for q in refusing.asked)
    assert out[0].startswith("suggest --decide: 2 groups from 1 questions about module pairs")
    assert out[1] == "  no answer: the decision provider gave a refusal for 1 pair questions"
    assert out[2:] == ["  group 1 (1 modules): pkg.reader", "  group 2 (1 modules): pkg.writer"]


def _module(file: str, sha: str, *names: str) -> dict[str, Any]:
    named = [{"name": n, "kind": "function"} for n in names]
    return {"file": file, "sha": sha, "docstring": "", "names": named, "imports": []}


def test_delta_gives_no_move_and_no_owner_for_a_refusal(sample: Sample) -> None:
    base = {"components": {"pkg.ledger": _module("pkg/ledger.py", "a", "record")}}
    head = {"components": {"pkg.book": _module("pkg/book.py", "b", "post")}}
    refusing = Refusing()
    counted = delta_jev.Counted(refusing)
    assert delta_jev.jev_moves(base, head, counted) == {}
    tree = tree_of(sample)
    owners = delta_jev.owner_suggestions(
        sample.cfg, tree, sample.facts, {"": ["pkg.reader"]}, counted
    )
    assert owners == []
    assert [q.name for q in refusing.asked] == ["became", "owner"]
    assert counted.errors() == (
        "delta --decide: the decision provider gave a refusal for 2 questions",
    )


def test_the_jev_adapter_maps_noul_and_choice() -> None:
    predicate = PredicateQuestion("k1", "holds", "Is it true?", {"x": 1})
    choice = ChoiceQuestion("k2", "where", "Which?", {"y": 2}, {"A": "a", "B": "b"}, ("A",))
    assert ask_of(predicate).questions == {"holds": {"type": "noul", "instructions": "Is it true?"}}
    jev_choice = ask_of(choice)
    assert jev_choice.questions == {
        "where": {"type": "choice", "instructions": "Which?", "criteria": {"A": "a", "B": "b"}}
    }
    assert jev_choice.needs == ("A",)
    raw_noul = {"type": "noul", "noul": 0.25}
    assert answer_of(predicate, raw_noul) == PredicateAnswer(0.25, raw_noul)
    raw_choice = {"type": "choice", "choice": "B", "confidence": 0.7}
    assert answer_of(choice, raw_choice) == ChoiceAnswer("B", {}, 0.7, raw_choice)

    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "2026-09-10"}]}
        assert body is not None
        name = next(iter(body["questions"]))
        given = raw_noul if name == "holds" else {**raw_choice, "probabilities": {"A": 0.3}}
        return {"model": "jev-latest", "answers": {name: given}, "usage": {}}

    answers = JevProvider(jev.Jev(send)).decide([predicate, choice])
    assert answers[0] == PredicateAnswer(0.25, raw_noul)
    assert isinstance(answers[1], ChoiceAnswer)
    assert answers[1].choice == "B" and answers[1].probabilities == {"A": 0.3}


def test_a_provider_without_measured_thresholds_is_an_error() -> None:
    assert decision.thresholds("jev") == decision.JEV
    with pytest.raises(DecisionError, match="has no measured thresholds"):
        decision.thresholds("another")
