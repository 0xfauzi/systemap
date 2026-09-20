"""A walk written for a way in that nothing walks from yet.

`systemap journeys` asks the agent named under `[agent]` to read the code
from one way into the system and answer with the cards a run passes through.
systemap checks that answer against the map before it is written in: a step
tracing a flow the map does not draw is not a journey, it is a line to fix.

No test here runs a real agent. Each passes its own `run_command`, the way
the Jev tests pass a recorded transport.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import agent, extract, journeys, nest
from systemap.cli import main
from systemap.config import Config, load
from systemap.jev_cli import cmd_journeys
from systemap.model import Journey, Meaning, Model

ANSWER = {
    "id": "read-and-write",
    "label": "A request is read and written",
    "steps": [
        {
            "edge": ["Reader", "Writer"],
            "acts": ["Reader"],
            "measures": [],
            "say": "The reader turns what arrived into a request and hands it over.",
        }
    ],
}


def answering(*answers: str) -> tuple[agent.Run, list[str]]:
    """A transport that answers from a list and keeps the questions it was asked."""
    asked: list[str] = []

    def run(command: str, question: str, cwd: Path, timeout: float) -> str:
        asked.append(question)
        return answers[min(len(asked) - 1, len(answers) - 1)]

    return run, asked


# ---- what is left to walk ----------------------------------------------------------


def facts_with(points: list[dict[str, str]]) -> dict[str, Any]:
    return {"entry_points": points, "components": {"pkg.reader": {"file": "pkg/reader.py"}}}


def route(name: str) -> dict[str, str]:
    return {"kind": "route", "name": name, "module": "pkg.reader", "target": "read"}


def test_a_way_in_a_journey_already_starts_from_is_not_asked_about() -> None:
    facts = facts_with([route("GET /a"), route("GET /b")])
    walk = Journey(id="a", label="read one", steps=(), starts="GET /a")
    left = journeys.uncovered(Meaning(plain={}, journeys=(walk,)), facts)
    assert [p["name"] for p in left] == ["GET /b"]


def test_the_agent_is_told_the_cards_the_flows_and_where_to_read(sample: Any) -> None:
    where = route("GET /a")
    told = journeys.context(sample.model, sample.meaning, facts_with([where]), where)
    assert told["way_in"] == {
        "named": "GET /a (route)",
        "kind": "route",
        "module": "pkg.reader",
        "file": "pkg/reader.py",
        "function": "read",
    }
    assert told["cards"]["Reader"].startswith("the part that reads")
    assert ["Reader", "Parser", "parse", "The reader calls the parser on each request."] in (
        told["flows"]
    )
    assert told["journeys_already_written"] == ["An input becomes a record"]


# ---- what comes back, checked against the map --------------------------------------


def two_card_model() -> Model:
    from systemap.model import Component, Container, Flow, Region

    return Model(
        canvas=(600, 300),
        containers=(Container("system", "PKG", (0, 0, 600, 300)),),
        regions=(Region("core", "CORE", (10, 10, 580, 280), container="system"),),
        components=(
            Component("Reader", "Reads.", implemented_by=("pkg.reader",), region="core"),
            Component("Writer", "Writes.", implemented_by=("pkg.writer",), region="core"),
        ),
        flows=(Flow("Reader", "Writer", "request", "data"),),
        flow_kinds=(),
    )


def read(answer: dict[str, Any] | str) -> journeys.Draft:
    text = answer if isinstance(answer, str) else json.dumps(answer)
    return journeys.read_answer(text, two_card_model(), route("GET /a"))


def test_a_walk_the_map_can_hold_becomes_a_journey_marked_as_a_draft() -> None:
    draft = read(ANSWER)
    assert draft.journey is not None
    assert draft.journey.id == "read-and-write" and draft.journey.drafted
    assert draft.journey.starts == "GET /a", "the walk says which way in it begins at"
    assert draft.journey.steps[0].edge == ("Reader", "Writer")
    assert draft.problems == ()


def test_a_step_tracing_a_flow_the_map_does_not_draw_is_refused() -> None:
    answer = {**ANSWER, "steps": [{**ANSWER["steps"][0], "edge": ["Writer", "Reader"]}]}
    draft = read(answer)
    assert draft.journey is None
    assert draft.problems == (
        "step 1 traces Writer -> Reader, which is not a flow",
        "no step of the walk could be used",
    )


def test_a_step_naming_a_card_that_is_not_on_the_map_is_refused() -> None:
    bad = {**ANSWER["steps"][0], "acts": ["Ledger"]}
    draft = read({**ANSWER, "steps": [ANSWER["steps"][0], bad]})
    assert draft.journey is not None, "the step that holds is kept"
    assert len(draft.journey.steps) == 1
    assert draft.problems == ("step 2 names Ledger, which the map has no card for",)


def test_an_answer_that_is_not_json_is_said_so_never_guessed_at() -> None:
    assert read("I read the code and here is what I found.").problems == (
        "the agent did not answer with JSON",
    )
    assert "could not be read" in read("{not json}").problems[0]


def test_the_walk_is_written_into_the_model_where_its_journeys_are_named() -> None:
    draft = read(ANSWER)
    assert draft.journey is not None
    source = "JOURNEYS = (\n)\n"
    grown = journeys.add_to_source(source, draft.journey)
    assert grown is not None and 'id="read-and-write"' in grown
    assert "drafted=True,  # read it, then remove this line" in grown
    assert grown.startswith("JOURNEYS = (\n    Journey(")
    # a model file that names its journeys somewhere this cannot find is said so
    assert journeys.add_to_source("MEANING = Meaning(plain={})\n", draft.journey) is None


# ---- the command -------------------------------------------------------------------


@pytest.fixture
def two_cards(tmp_path: Path) -> Config:
    """The two-card map, with a route into the reader that no journey walks from."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            **STARTER_MODULES,
            "pkg/reader.py": '@app.get("/read")\ndef read(source: str) -> str:\n    return source\n',
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return load(tmp_path)


def args_for(cfg: Config, **kw: Any) -> argparse.Namespace:
    values: dict[str, Any] = {"root_path": cfg.root, "limit": 3, "dry_run": False, **kw}
    return argparse.Namespace(**values)


def test_the_route_with_no_walk_is_listed_and_nothing_is_written(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    before = (two_cards.model_path).read_text()
    assert cmd_journeys(args_for(two_cards, dry_run=True)) == 0
    out = capsys.readouterr().out
    assert "1 way into the system with no walk from them" in out
    assert "GET /read (route)" in out
    assert (two_cards.model_path).read_text() == before


def test_with_no_agent_set_it_says_so_and_writes_nothing(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cmd_journeys(args_for(two_cards)) == 0
    assert agent.NO_AGENT in capsys.readouterr().out


def with_agent(cfg: Config) -> Config:
    toml = cfg.root / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[agent]\ncommand = "agent -p"\n')
    return load(cfg.root)


def test_the_walk_that_comes_back_is_written_in_and_judgement_asks_about_it(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = with_agent(two_cards)
    run, asked = answering(json.dumps(ANSWER))
    assert cmd_journeys(args_for(cfg), run_command=run) == 0
    out = capsys.readouterr().out
    assert "wrote read-and-write (A request is read and written) for GET /read (route)" in out
    assert "each marked drafted=True" in out
    assert "pkg/reader.py" in asked[0], "the agent is told where to read"

    meaning = nest.load(cfg).top.meaning
    written = [j for j in meaning.journeys if j.id == "read-and-write"]
    assert written and written[0].starts == "GET /read" and written[0].drafted
    assert main(["--root", str(cfg.root), "refresh"]) == 0
    assert main(["--root", str(cfg.root), "check"]) == 0

    assert main(["--root", str(cfg.root), "judgement"]) == 0
    lines = capsys.readouterr().out
    assert "drafted journey: read-and-write" in lines
    # and the way in it walks from is no longer asked for a journey
    assert "GET /read" not in lines.split("drafted journey")[0]


def test_a_walk_the_map_cannot_hold_is_reported_and_the_model_is_left_alone(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = with_agent(two_cards)
    bad = {**ANSWER, "steps": [{**ANSWER["steps"][0], "edge": ["Writer", "Reader"]}]}
    before = cfg.model_path.read_text()
    run, _asked = answering(json.dumps(bad))
    assert cmd_journeys(args_for(cfg), run_command=run) == 0
    out = capsys.readouterr().out
    assert "no walk written for GET /read (route)" in out
    assert "which is not a flow" in out
    assert cfg.model_path.read_text() == before


def test_a_way_in_the_extractor_finds_is_the_one_the_agent_is_asked_about(
    two_cards: Config,
) -> None:
    facts = json.loads(two_cards.facts_path.read_text())
    points = [extract.entry_label(p) for p in facts["entry_points"]]
    assert "GET /read (route)" in points
