"""Audit, triage, plan and suggest with answers that the real model could give,
and with Jev not available. Each transport is an injected fake. No test opens a socket.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, Sample, init_two_cards, write_tree

from systemap import audit, explain, extract, jev, jev_cli, jev_provider, nest
from systemap.cli import main
from systemap.config import Answer, Config
from systemap.config import load as load_config
from systemap.decision import JEV, ChoiceAnswer, DecisionError
from systemap.judgement import answer_digest
from systemap.model import Component, Flow, Meaning, Model

MODELS = {"models": [{"name": "jev-latest", "release_date": "2026-09-10"}]}


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


class Fake:
    """A transport that answers each question with `answer(name, question)`."""

    def __init__(self, answer: Any = None, models: Any = None) -> None:
        self.answer = answer or self.first_option
        self.models = models
        self.posts: list[dict[str, Any]] = []

    @staticmethod
    def first_option(name: str, question: dict[str, Any]) -> dict[str, Any]:
        if question["type"] == "choice":
            names = list(question["criteria"])
            return {
                "type": "choice",
                "choice": names[0],
                "confidence": 0.95,
                "probabilities": {n: (0.95 if i == 0 else 0.0) for i, n in enumerate(names)},
            }
        return {"type": "noul", "noul": 0.5}

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            if isinstance(self.models, Exception):
                raise self.models
            return self.models or MODELS
        assert body is not None
        self.posts.append(body)
        answers = {k: self.answer(k, q) for k, q in body["questions"].items()}
        return {"model": "jev-fake", "answers": answers, "usage": {}}


@pytest.fixture
def two_cards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def use_fake(monkeypatch: pytest.MonkeyPatch, fake: Fake) -> None:
    """Let the CLI make its client from the environment, with the fake as transport."""
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: fake)
    monkeypatch.setattr(jev.time, "sleep", lambda seconds: None)


def audit_args(root: Path, *kinds: str, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(root_path=root, kind=list(kinds), dry_run=dry_run, brief=True)


# ---- finding 4: an answer that does not fit is a message, not a traceback ---------


def test_audit_triage_plan_and_suggest_say_why_a_bad_answer_stops_them(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = Fake(lambda name, q: {"type": q["type"]})
    use_fake(monkeypatch, bad)
    assert main(["--root", str(two_cards), "audit"]) == 1
    assert capsys.readouterr().out.startswith("audit: Jev gave an incorrect answer")
    assert main(["--root", str(two_cards), "triage", "the reader fails"]) == 1
    assert capsys.readouterr().out.startswith("triage: Jev gave an incorrect answer")
    assert main(["--root", str(two_cards), "plan", "change the reader"]) == 1
    assert capsys.readouterr().out.startswith("plan: Jev gave an incorrect answer")
    assert main(["--root", str(two_cards), "suggest", "--jev"]) == 1
    assert capsys.readouterr().out.startswith("suggest --decide: Jev gave an incorrect answer")
    assert not (two_cards / ".systemap/plans").exists()


# ---- finding 6: a missing probability is not a probability of 0 -------------------


def test_a_missing_probability_for_the_claimed_component_is_an_error(sample: Sample) -> None:
    read = ("owner", tree_of(sample).top, "pkg.reader", "Reader")
    answer = ChoiceAnswer("Reader", confidence=0.99)
    with pytest.raises(DecisionError, match="no probability for Reader"):
        audit.owner_line(read, answer, JEV)


def test_an_owner_answer_without_the_claimed_probability_is_not_kept(
    sample: Sample, tmp_path: Path
) -> None:
    plan = audit.make_plan(tree_of(sample), sample.facts, sample.cfg, ("decision mis-fold",))
    partial = Fake(
        lambda name, q: {
            "type": "choice",
            "choice": audit.NONE,
            "confidence": 0.9,
            "probabilities": {audit.NONE: 0.9},
        }
    )
    cache = tmp_path / "jev.json"
    with pytest.raises(jev.JevError, match="no probability for"):
        jev_provider.JevProvider(jev.Jev(partial, cache=jev.Cache(cache))).decide(plan.questions)
    assert jev.Cache(cache).entries == {}


def test_triage_and_plan_use_the_choice_when_jev_gives_no_probabilities(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    only_choice = Fake(lambda name, q: {"type": "choice", "choice": "Writer", "confidence": 0.9})
    use_fake(monkeypatch, only_choice)
    assert main(["--root", str(two_cards), "triage", "the writer fails"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "triage: confidence 0.90"
    assert out[1].startswith("  0.90  Writer: pkg.writer")
    assert main(["--root", str(two_cards), "plan", "change the writer"]) == 0
    assert "  Writer (0.90)" in capsys.readouterr().out


# ---- finding 7: the dry run counts the questions when the model list fails ---------


def test_a_dry_run_gives_the_counts_and_the_reason_when_the_model_list_fails(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    refused = Fake(models=jev.JevError("Jev answered 401: invalid key"))
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=refused) == 1
    out = capsys.readouterr().out
    assert out.startswith("audit --dry-run: 5 questions (unknown: Jev answered 401: invalid key)")
    assert "by type: " in out
    assert refused.posts == []


# ---- finding 9: whole-module, namespace and default imports give flow evidence -----


def flow_model(src_module: str, dst_module: str) -> tuple[Model, Meaning]:
    model = Model(
        canvas=(400, 200),
        containers=(),
        regions=(),
        components=(
            Component(id="Reader", does="Reads.", implemented_by=(dst_module,), x=40, y=40),
            Component(id="Writer", does="Writes.", implemented_by=(src_module,), x=240, y=40),
        ),
        flows=(Flow("Writer", "Reader", "request", "data"),),
        flow_kinds=(),
    )
    return model, Meaning(plain={}, relations={("Writer", "Reader"): "The writer gives a request."})


def flow_asks(cfg: Config, model: Model, meaning: Meaning) -> audit.Plan:
    tree = nest.Tree(
        (nest.Map(id="", path=cfg.model_path, rel="", model=model, meaning=meaning, theme={}),)
    )
    return audit.make_plan(tree, extract.build(cfg), cfg, ("decision flow",))


@pytest.mark.parametrize(
    ("writer", "used"),
    [
        (
            "import pkg.reader\n\ndef write() -> None:\n    pkg.reader.read('x')\n",
            "pkg.reader.read",
        ),
        (
            "import pkg.reader as rd\n\ndef write() -> None:\n    rd.read('x')\n",
            "rd.read('x')",
        ),
        (
            "from pkg import reader\n\ndef write() -> None:\n    reader.read('x')\n",
            "reader.read('x')",
        ),
        ("from pkg.reader import *\n\ndef write() -> None:\n    read('x')\n", "read('x')"),
    ],
)
def test_a_python_flow_through_a_whole_module_import_is_asked(
    tmp_path: Path, writer: str, used: str
) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": writer,
        },
    )
    cfg = Config(root=tmp_path, name="flows", package_roots=(("pkg", "pkg"),), language="python")
    plan = flow_asks(cfg, *flow_model("pkg.writer", "pkg.reader"))
    assert [a.key for a in plan.questions] == ["|flow|Writer->Reader:request"]
    assert any(used in line for line in plan.questions[0].state["code"])
    assert plan.unasked == []


def test_a_typescript_flow_through_a_namespace_or_default_import_is_asked(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "typescript-app"
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
    (tmp_path / "src/service.ts").write_text(
        'import * as client from "@/client";\n'
        'import fetchAll from "@/view";\n\n'
        "export function serve(id: string): client.User {\n"
        "  fetchAll();\n"
        "  return client.fetchUser(id);\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "src/view.tsx").write_text(
        "export default function fetchAll(): void {}\n", encoding="utf-8"
    )
    cfg = load_config(tmp_path)
    for target in ("acme.web.client", "acme.web.view"):
        plan = flow_asks(cfg, *flow_model("acme.web.service", target))
        assert [a.key for a in plan.questions] == ["|flow|Writer->Reader:request"], target
        code = plan.questions[0].state["code"]
        used = "client.fetchUser(id)" if target.endswith("client") else "fetchAll();"
        assert any(used in line for line in code), (target, code)


def test_the_dry_run_counts_the_flows_that_it_cannot_ask_about(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write() -> None:\n    return None\n",
        },
    )
    cfg = Config(root=tmp_path, name="flows", package_roots=(("pkg", "pkg"),), language="python")
    plan = flow_asks(cfg, *flow_model("pkg.writer", "pkg.reader"))
    assert plan.questions == []
    assert plan.unasked == ["Writer -> Reader (request)"]
    assert any(
        "1 flow" in line for line in audit.dry_run(plan, None, jev_provider.chars(plan.questions))
    )


# ---- finding 15: the identifier does not contain Jev's pick ------------------------


def test_the_audit_identifier_does_not_contain_the_pick(sample: Sample) -> None:
    read = ("owner", tree_of(sample).top, "pkg.parser", "Parser")
    probs = {"Parser": 0.01, "Reader": 0.9, "Writer": 0.0, "Ledger": 0.0, audit.NONE: 0.09}
    first = audit.owner_line(read, ChoiceAnswer("Reader", probs, 0.9), JEV)
    later = audit.owner_line(read, ChoiceAnswer(audit.NONE, probs, 0.5), JEV)
    assert first is not None and later is not None
    assert first.text == later.text == "decision mis-fold: Parser claims pkg.parser"
    assert first.detail[0].startswith("reads like Reader; P(Parser) 0.01")
    assert later.detail[0].startswith("reads like none of the cards")
    stray = ("owner", tree_of(sample).top, "pkg.stray", "")
    sure = audit.owner_line(stray, ChoiceAnswer("Writer", {"Writer": 0.95}, 0.95), JEV)
    assert sure is not None and sure.text == "decision owner: pkg.stray is claimed by no card"
    assert sure.detail == ("reads like Writer; confidence 0.95",)


OLD = "jev mis-fold: Parser claims pkg.parser, which reads like Reader"
NEW = "decision mis-fold: Parser claims pkg.parser"
OLD_OWNER = "Core: jev owner: pkg.stray is claimed by no card; closest: Writer, Parser, Reader"
NEW_OWNER = "Core: decision owner: pkg.stray is claimed by no card"


def test_answers_recorded_with_the_old_line_still_match() -> None:
    assert audit.migrated(OLD) == NEW
    assert audit.migrated(OLD_OWNER) == NEW_OWNER
    assert audit.migrated(
        "jev owner: pkg.x is claimed by no card; it reads like none of the cards"
    ) == ("decision owner: pkg.x is claimed by no card")
    assert audit.migrated(NEW) == NEW
    found = [audit.Line(NEW), audit.Line(NEW_OWNER)]
    evidence = {NEW: "d1", NEW_OWNER: "d2"}
    one = Answer(items=(OLD,), reason="r", evidence="d1")
    # The digest of a group was recorded over the old lines.
    group_digest = answer_digest([OLD, OLD_OWNER], {OLD: "d1", OLD_OWNER: "d2"})
    group = Answer(items=(OLD, OLD_OWNER), reason="r", evidence=group_digest)
    for given in ([one], [group]):
        result = audit.apply_reviewed(found, given, evidence, audit.KINDS)
        assert result.pending == [] and result.stale == []
        assert NEW not in [x.text for x in result.open]
    result = audit.apply_reviewed(found, [group], evidence, audit.KINDS)
    assert result.open == [] and result.answered == 2
    # A line that is gone makes the old item stale, with the text from the configuration.
    gone = audit.apply_reviewed([], [one], {}, audit.KINDS)
    assert gone.stale == [OLD]


# ---- finding 16: the explanation says what Jev reads -------------------------------


def test_the_misfold_explanation_says_what_jev_reads() -> None:
    lesson = explain.lesson("decision mis-fold")
    assert lesson is not None
    assert "reads the code" not in lesson.why
    assert "docstring" in lesson.why


# ---- finding 17: each owner kind asks only its own modules -------------------------


def test_each_owner_kind_asks_only_about_its_own_modules(sample: Sample) -> None:
    write_tree(
        sample.cfg.root, {"pkg/stray.py": '"""A stray."""\n\ndef stray() -> None:\n    pass\n'}
    )
    facts = extract.build(sample.cfg)
    owner_only = audit.make_plan(tree_of(sample), facts, sample.cfg, ("decision owner",))
    assert [a.key for a in owner_only.questions] == ["|owner|pkg.stray"]
    misfold_only = audit.make_plan(tree_of(sample), facts, sample.cfg, ("decision mis-fold",))
    assert "|owner|pkg.stray" not in [a.key for a in misfold_only.questions]
    assert len(misfold_only.questions) == 4


# ---- finding 10: the hints give the measurement limits -----------------------------


def test_the_hints_say_what_jev_does_and_how_to_stop_them() -> None:
    assert "systemap audit" in jev_cli.JUDGEMENT_HINT
    assert "do not change the delta result" in jev_cli.DELTA_HINT
    for hint in (jev_cli.JUDGEMENT_HINT, jev_cli.DELTA_HINT):
        assert "%" not in hint, "a benchmark figure is not for the reader of a hint"
        assert "measurement" not in hint and "bench/" not in hint
        assert hint.endswith("Set [jev] enabled = false in systemap.toml to stop this hint.")


def test_suggest_jev_without_a_key_sends_nothing(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = load_config(two_cards)
    assert cfg.jev_cache_path is not None
    assert main(["--root", str(two_cards), "suggest", "--jev"]) == 1
    assert "set TYPESAFE_API_KEY" in capsys.readouterr().out
    assert not cfg.jev_cache_path.exists()
