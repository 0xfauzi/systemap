"""An incorrect sequence from the agent is refused with a clear problem.

Codex result change-9. An agent answer can give a step edge with one value or three
values. Acceptance value: the draft has no sequence, and its problem says that an edge
has two component identifiers. Before the repair, `read_answer` raised `IndexError` for
a step with a flow identifier and an edge with one value.

Codex result change-11. An agent answer can give a sequence id that the map or an
earlier draft of the same command already uses. Acceptance value: the command writes
the first sequence and refuses the second with a clear problem. The model has the id
one time. A model file with two sequences of one id gives a check problem. Before the
repair, the command wrote two sequences with one id, and the check accepted the model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, TWO_CARD_MODEL, init_two_cards, write_tree
from test_journeys import ANSWER, answering, args_for, read, with_agent

from systemap import nest
from systemap.cli import main
from systemap.config import Config, load
from systemap.jev_cli import cmd_journeys

EDGE_PROBLEM = "has an edge with {n} values. An edge has two component identifiers"


def with_step(**fields: Any) -> dict[str, Any]:
    step = {key: value for key, value in ANSWER["steps"][0].items() if key != "edge"}
    return {**ANSWER, "steps": [{**step, **fields}]}


@pytest.mark.parametrize(
    "fields",
    [
        {"flow": "Reader->Writer", "edge": ["Reader"]},
        {"flow": "Reader->Writer", "edge": ["Reader", "Writer", "Reader"]},
        {"edge": ["Reader"]},
        {"edge": ["Reader", "Writer", "Reader"]},
    ],
    ids=["flow-and-one", "flow-and-three", "one", "three"],
)
def test_a_step_edge_without_two_values_is_refused(fields: dict[str, Any]) -> None:
    draft = read(with_step(**fields))
    assert draft.journey is None
    n = len(fields["edge"])
    assert draft.problems[0] == "step 1 " + EDGE_PROBLEM.format(n=n)


def test_a_step_without_an_edge_and_with_a_flow_is_accepted() -> None:
    draft = read(with_step(flow="Reader->Writer"))
    assert draft.journey is not None
    assert draft.journey.steps[0].edge == ("Reader", "Writer")


@pytest.fixture
def two_routes(tmp_path: Path) -> Config:
    """The two-card map, with two routes into the reader that no sequence covers."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            **STARTER_MODULES,
            "pkg/reader.py": (
                "from fastapi import FastAPI\napp = FastAPI()\n"
                '@app.get("/read")\ndef read(source: str) -> str:\n    return source\n'
                '@app.get("/again")\ndef again(source: str) -> str:\n    return source\n'
            ),
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return with_agent(load(tmp_path))


def ids(cfg: Config) -> list[str]:
    return [j.id for j in nest.load(cfg).top.meaning.journeys]


def test_a_second_draft_with_the_same_id_is_refused(
    two_routes: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    run, asked = answering(json.dumps(ANSWER))
    cmd_journeys(args_for(two_routes), run_command=run)
    out = capsys.readouterr().out
    assert len(asked) == 2
    assert out.count("journeys: wrote read-and-write") == 1
    assert "the map has a sequence with the id read-and-write. Give each sequence its own id" in out
    assert ids(two_routes).count("read-and-write") == 1


def test_a_draft_with_the_id_of_a_sequence_in_the_map_is_refused(
    two_routes: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    run, _asked = answering(json.dumps({**ANSWER, "id": "input-to-output"}))
    before = two_routes.model_path.read_text(encoding="utf-8")
    assert cmd_journeys(args_for(two_routes), run_command=run) == 1, "no sequence was written"
    out = capsys.readouterr().out
    assert "the map has a sequence with the id input-to-output" in out
    assert two_routes.model_path.read_text(encoding="utf-8") == before


def test_the_check_refuses_a_model_with_two_sequences_of_one_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    twice = TWO_CARD_MODEL.replace(
        "JOURNEYS = (\n",
        'JOURNEYS = (\n    Journey(id="input-to-output", label="Again", steps=(Step(acts=("Reader",), '
        'measures=(), edge=("Reader", "Writer"), say="The reader hands on a request."),)),\n',
    )
    (tmp_path / "map/model.py").write_text(twice, encoding="utf-8")
    assert main(["--root", str(tmp_path), "refresh"]) == 1
    out = capsys.readouterr().out
    assert (
        "meaning: journey input-to-output is the id of two sequences. "
        "Give each sequence its own id" in out
    )
