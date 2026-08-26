"""The card text budget: what fits is drawn, what does not is refused, nothing is cut.

A card's name is mono at 11.5px and its plain word sans at 11px, in 140
units of inner width. A session's map passed the check with plain words
the drawing had cut short with an ellipsis; the check now refuses a card
whose text does not fit, stating the budget, after trying a two-line
wrap where the card kind has room.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import Sample, init_two_cards, write_tree

from systemap import schematic
from systemap.check import check_labels
from systemap.cli import main
from systemap.schematic import card_text, wrap_id
from systemap.schematic import render as render_schematic

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def test_wrap_id_breaks_at_the_words_of_a_name() -> None:
    assert wrap_id("FactsExtractor", 20) == ["FactsExtractor"]
    assert wrap_id("TheVeryLongComponentName", 20) == ["TheVeryLongComponent", "Name"]
    assert wrap_id("AVeryLongCamelCaseIdentifierIndeed", 20) == [
        "AVeryLongCamelCase",
        "IdentifierIndeed",
    ]
    assert wrap_id("snake_case_name_here", 12) == ["snake_case_", "name_here"]
    assert wrap_id("Supercalifragilisticexpialidocious", 20) == [
        "Supercalifragilisticexpialidocious"
    ]
    assert wrap_id("CLI", 20) == ["CLI"]


def test_card_text_budgets_by_kind() -> None:
    assert card_text("component", "Reader", "the part that reads") == (
        ["Reader"],
        ["the part that reads"],
        [],
    )
    # An actor has one plain line of about 26 characters.
    name, plain, problems = card_text("actor", "User", "the person who confirms the judgement")
    assert name == ["User"] and plain == ["the person who confirms"]
    assert problems == [
        "card User: plain word does not fit (actor cards fit about 26 characters on one "
        "line; this one has 37)"
    ]
    # A component, a store and a context card have two plain lines.
    for kind in ("component", "store", "context", "agent", "tool"):
        assert card_text(kind, "A", "the person who confirms the judgement")[2] == [], kind
    sixty = "a plain word long enough to need three lines of twenty six each"
    assert card_text("component", "A", sixty)[2] == [
        "card A: plain word does not fit (component cards fit about 26 characters on two "
        f"lines; this one has {len(sixty)})"
    ]
    assert card_text("store", "A", sixty)[2] == [
        "card A: plain word does not fit (store cards fit about 26 characters on two "
        f"lines; this one has {len(sixty)})"
    ]
    # A single word wider than the line does not fit either.
    assert card_text("component", "A", "supercalifragilisticexpialidocious")[2] == [
        "card A: plain word does not fit (component cards fit about 26 characters on two "
        "lines; this one has 34)"
    ]
    # A long name wraps over two lines on a component, agent or tool card,
    # and the plain word then has one line left under it.
    name, plain, problems = card_text("component", "TheVeryLongComponentName", "the part")
    assert name == ["TheVeryLongComponent", "Name"] and plain == ["the part"]
    assert problems == []
    assert card_text("agent", "TheVeryLongComponentName", "x")[2] == []
    name, plain, problems = card_text(
        "component", "TheVeryLongComponentName", "the part that reads the input"
    )
    assert problems == [
        "card TheVeryLongComponentName: plain word does not fit (component cards fit about "
        "26 characters on one line under a two-line name; this one has 29)"
    ]
    # A store, a context card and an actor have no second name line.
    for kind in ("store", "context", "actor"):
        name, _plain, problems = card_text(kind, "TheVeryLongComponentName", "x")
        assert name == ["TheVeryLongComponentName"], kind
        assert problems == [
            f"card TheVeryLongComponentName: name does not fit ({kind} cards fit a name of "
            "about 20 characters on one line; this one has 24)"
        ], kind
    # A name with no break points, or one that needs three lines, is refused.
    assert card_text("component", "Supercalifragilisticexpialidocious", "x")[2] == [
        "card Supercalifragilisticexpialidocious: name does not fit (component cards fit a "
        "name of about 20 characters over two lines; this one has 34)"
    ]
    long_id = "AVeryLongCamelCaseIdentifierIndeedTooLongForTwo"
    (problem,) = card_text("component", long_id, "x")[2]
    assert problem.startswith(f"card {long_id}: name does not fit")


def test_the_drawing_reports_unfit_text_and_never_elides(sample: Sample) -> None:
    long_plain = "the person who types the input in"
    model = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, id="AVeryLongParserComponentName") if c.id == "Parser" else c
            for c in sample.model.components
        ),
        flows=tuple(
            dataclasses.replace(
                f,
                src="AVeryLongParserComponentName" if f.src == "Parser" else f.src,
                dst="AVeryLongParserComponentName" if f.dst == "Parser" else f.dst,
            )
            for f in sample.model.flows
        ),
    )
    plain = {
        k if k != "Parser" else "AVeryLongParserComponentName": v
        for k, v in sample.meaning.plain.items()
    }
    plain["User"] = long_plain
    relations = {
        tuple("AVeryLongParserComponentName" if x == "Parser" else x for x in edge): say
        for edge, say in sample.meaning.relations.items()
    }
    meaning = dataclasses.replace(
        sample.meaning, plain=plain, relations=relations, journeys=(), layer_overrides={}
    )
    svg, detail = render_schematic(model, meaning, sample.theme, sample.facts)
    problems = check_labels(json.loads(detail)["_meta"])
    assert (
        "card User: plain word does not fit (actor cards fit about 26 characters on one "
        f"line; this one has {len(long_plain)})"
    ) in problems
    assert len(problems) == 1, problems
    assert "..." not in svg and "…" not in svg, "nothing is elided"
    # What fits is drawn: the first plain line, and the name over two lines
    # (fifteen and thirteen characters), which is why it was not refused.
    assert ">the person who types the</text>" in svg
    assert ">AVeryLongParser</text>" in svg and ">ComponentName</text>" in svg
    assert not hasattr(schematic, "wrap_words"), "the eliding wrap is gone"


def test_check_refuses_a_card_whose_text_does_not_fit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "refresh") == 0
    model = tmp_path / "map/model.py"
    # Two lines on a component card: fine.
    model.write_text(
        model.read_text().replace(
            '"Reader": "the part that reads"',
            '"Reader": "the part that reads the input line by line"',
        )
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    capsys.readouterr()
    three_lines = "the part that reads the input line by line and hands each one on"
    model.write_text(
        model.read_text().replace(
            '"Reader": "the part that reads the input line by line"', f'"Reader": "{three_lines}"'
        )
    )
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "map layout: 1 problem" in out
    assert (
        "card Reader: plain word does not fit (component cards fit about 26 characters on "
        f"two lines; this one has {len(three_lines)})"
    ) in out
    assert run("--root", str(tmp_path), "refresh") == 1
