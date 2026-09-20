"""A piece of work projected onto the map, and checked against what happened.

`systemap plan` asks Jev which cards a task will most likely change, at the
cut measured in `bench/jev/plan_eval.py`, and prints what each of those cards
sits in: the flows, the walks and the rules around it. `--check` compares the
projection with the cards the code actually changed.

No test here sends anything: each passes its own transport, as the other Jev
tests do.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import plan as plan_mod
from systemap.cli import main
from systemap.config import Config, load
from systemap.jev_cli import cmd_plan
from systemap.model import Meaning


def answering(spread: dict[str, float]) -> Any:
    """A transport that answers the plan question with one spread over the cards."""

    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "2026-01-01"}]}
        return {
            "model": "jev-latest",
            "usage": {"input_tokens": 10, "output_tokens": 2},
            "answers": {
                "where": {
                    "type": "choice",
                    "choice": max(spread, key=lambda k: spread[k]),
                    "confidence": max(spread.values()),
                    "probabilities": spread,
                }
            },
        }

    return send


# ---- what the projection is made of ------------------------------------------------


def test_only_the_cards_with_real_weight_are_named() -> None:
    spread = {"Reader": 0.7, "Writer": 0.06, "Ledger": 0.04, "none of these": 0.2}
    assert plan_mod.named(spread) == ["Reader", "Writer"], "the cut is 0.05, and none is not a card"
    assert plan_mod.named(spread, cut=0.5) == ["Reader"]


def test_a_card_is_given_with_what_it_sits_in(sample: Any) -> None:
    one = plan_mod.around(sample.model, sample.meaning, "Parser")
    assert "Reader -> Parser (parse)" in one.flows
    assert "Parser -> Writer (parts)" in one.flows
    assert one.journeys == ("input-to-record: An input becomes a record",)
    assert one.rules == (), "no invariant names Parser"
    writer = plan_mod.around(sample.model, sample.meaning, "Writer")
    assert [r.split(".")[0] for r in writer.rules] == ["1", "2"]


def test_the_projection_keeps_the_task_the_weights_and_the_day(sample: Any) -> None:
    spread = {"Parser": 0.6, "Writer": 0.2, "Reader": 0.01}
    made = plan_mod.project(sample.model, sample.meaning, "split the input differently", spread)
    assert made.cards == ("Parser", "Writer")
    assert made.weights == {"Parser": 0.6, "Writer": 0.2}
    assert made.id.endswith("-split-the-input-differently")
    assert [a.card for a in made.around] == ["Parser", "Writer"]
    assert json.loads(json.dumps(made.as_json()))["task"] == "split the input differently"


def test_a_task_with_nothing_to_name_it_by_still_gets_an_id() -> None:
    assert plan_mod.plan_id("?!").endswith("-plan")


# ---- the command -------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Config:
    """The two-card map in a git repository, so --check has a base to read."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    run = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run([*run, "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run([*run, "-C", str(tmp_path), "commit", "-qm", "first"], check=True)
    return load(tmp_path)


def args_for(cfg: Config, **kw: Any) -> argparse.Namespace:
    values: dict[str, Any] = {
        "root_path": cfg.root,
        "task": None,
        "check": None,
        "base": "main",
        **kw,
    }
    return argparse.Namespace(**values)


def test_the_plan_names_its_cards_and_is_written_down(
    repo: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    send = answering({"Reader": 0.8, "Writer": 0.1, "none of these": 0.1})
    code = cmd_plan(args_for(repo, task="read the input in chunks"), send=send)
    assert code == 0
    out = capsys.readouterr().out
    assert "2 cards this work will most likely change" in out
    assert "  Reader (0.8" in out and "  Writer (0.1" in out
    assert "flow: Reader -> Writer (request)" in out
    assert "walk: input-to-output: An input becomes an output" in out
    assert "rule: 1. The writer never reads the input itself." in out
    saved = plan_mod.saved(repo)
    assert len(saved) == 1
    written = plan_mod.load(repo, saved[0])
    assert written is not None and written["cards"] == ["Reader", "Writer"]


def test_a_task_no_card_answers_to_says_so_rather_than_guessing(
    repo: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    send = answering({"Reader": 0.02, "Writer": 0.01, "none of these": 0.97})
    assert cmd_plan(args_for(repo, task="rename the project"), send=send) == 0
    out = capsys.readouterr().out
    assert "no card stands out for this work" in out
    assert plan_mod.saved(repo) == [], "nothing is written down when nothing is named"


def test_an_empty_task_asks_for_one_and_sends_nothing(
    repo: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cmd_plan(args_for(repo, task="   ")) == 1
    assert "give the task in your own words" in capsys.readouterr().out


# ---- what happened against what was planned ----------------------------------------


def test_a_card_that_changed_outside_the_plan_is_the_finding(
    repo: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    send = answering({"Reader": 0.9, "Writer": 0.01, "none of these": 0.09})
    assert cmd_plan(args_for(repo, task="read the input in chunks"), send=send) == 0
    plan_id = plan_mod.saved(repo)[0]
    capsys.readouterr()
    # the work touched the writer, which the plan did not name
    (repo.root / "pkg/writer.py").write_text(
        "from pkg.reader import read\n\n\ndef write(request: str) -> str:\n    return read(request) * 2\n"
    )
    assert cmd_plan(args_for(repo, check=plan_id)) == 1
    out = capsys.readouterr().out
    assert "not in the plan: Writer changed and the plan did not name it" in out
    assert "the work reached a part the plan did not see" in out


def test_work_that_landed_where_it_was_projected_says_so(
    repo: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    send = answering({"Reader": 0.9, "Writer": 0.2, "none of these": 0.05})
    assert cmd_plan(args_for(repo, task="read the input in chunks"), send=send) == 0
    plan_id = plan_mod.saved(repo)[0]
    capsys.readouterr()
    (repo.root / "pkg/reader.py").write_text(
        "def read(source: str) -> str:\n    return source[:1]\n"
    )
    (repo.root / "pkg/writer.py").write_text(
        "from pkg.reader import read\n\n\ndef write(request: str) -> str:\n    return read(request) * 2\n"
    )
    assert cmd_plan(args_for(repo, check=plan_id)) == 0
    assert "the work landed where it was projected to" in capsys.readouterr().out


def test_a_plan_nobody_wrote_names_the_ones_that_exist(
    repo: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cmd_plan(args_for(repo, check="no-such-plan")) == 1
    out = capsys.readouterr().out
    assert "no plan named no-such-plan" in out and "none yet" in out


def test_the_cards_a_change_touched_are_read_from_the_facts() -> None:
    base = {"components": {"pkg.a": {"sha": "1"}, "pkg.b": {"sha": "2"}}}
    head = {"components": {"pkg.a": {"sha": "9"}, "pkg.c": {"sha": "3"}}}
    owner = {"pkg.a": "A", "pkg.b": "B", "pkg.c": "C"}
    assert plan_mod.touched(base, head, owner) == {"A", "B", "C"}
    missed, untouched = plan_mod.check(["A", "D"], {"A", "B"})
    assert missed == ["B"] and untouched == ["D"]


def test_a_journey_that_does_not_pass_through_the_card_is_not_listed(sample: Any) -> None:
    empty = Meaning(plain={}, relations=sample.meaning.relations)
    assert plan_mod.around(sample.model, empty, "Parser").journeys == ()
