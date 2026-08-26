"""Layout is the hard part: the starter's grid, the label diagnosis, describe.

The rule the router enforces (an edge may not cross a region it does not
belong to) is stated in references/layout.md, built into the starter
model `init` writes (a 2x2 grid of regions with corridors between, which
`systemap place` lays out again from the cards), named in a label
collision (the gutter is full, or the label is too wide), and read back
in numbers by `systemap describe`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import Sample, write_tree

from systemap import describe, route, scaffold, skill
from systemap.check import check_labels
from systemap.cli import main
from systemap.schematic import render as render_schematic

FOUR_MODULES = {f"pkg/{m}.py": f"def run_{m}() -> None:\n    pass\n" for m in "abcd"}


def run(*argv: str) -> int:
    return main(list(argv))


def fill_starter(model: Path, both_ways: bool) -> None:
    """One card in each of the starter's four regions, written without a
    position and placed by `systemap place`, and a flow between every pair:
    the routes must run along the corridors."""
    text = model.read_text()
    cards = "".join(
        f'    Component(id="{cid}", does="{cid}", region="{cid.lower()}", '
        f'implemented_by=("pkg.{cid.lower()}",), entry="run_{cid.lower()}"),\n'
        for cid in "ABCD"
    )
    pairs = [(a, b) for a in "ABCD" for b in "ABCD" if (a != b if both_ways else a < b)]
    flows = "".join(
        f'    Flow("{a}", "{b}", "{a.lower()}{b.lower()}", "data"),\n' for a, b in pairs
    )
    relations = "".join(f'    ("{a}", "{b}"): "{a} hands {b} a thing.",\n' for a, b in pairs)
    for old, new in (
        (
            "COMPONENTS: tuple[Component, ...] = ()\n",
            f"COMPONENTS: tuple[Component, ...] = (\n{cards})\n",
        ),
        ("FLOWS: tuple[Flow, ...] = ()\n", f"FLOWS: tuple[Flow, ...] = (\n{flows})\n"),
        (
            "PLAIN: dict[str, str] = {}\n",
            'PLAIN: dict[str, str] = {"A": "a", "B": "b", "C": "c", "D": "d"}\n',
        ),
        (
            "RELATIONS: dict[tuple[str, str], str] = {}\n",
            f"RELATIONS: dict[tuple[str, str], str] = {{\n{relations}}}\n",
        ),
    ):
        assert old in text, old
        text = text.replace(old, new)
    model.write_text(text)
    assert run("--root", str(model.parent.parent), "place") == 0


# ---- the starter: a 2x2 grid whose corridors reach every pair -----------------------


def test_starter_is_a_2x2_grid_with_corridors(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **FOUR_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    text = (tmp_path / "map/model.py").read_text()
    boxes = [
        tuple(int(v) for v in m.groups())
        for m in re.finditer(
            r"Region\(id=\"\w\", label=\"REGION \w\", box=\((\d+), (\d+), (\d+), (\d+)\)", text
        )
    ]
    assert len(boxes) == 4
    (ax, ay, aw, ah), (bx, by, _bw, _bh), (cx, cy, _cw, _ch), (dx, dy, _dw, _dh) = boxes
    assert bx - (ax + aw) == 48, "48 units between the region columns"
    assert cy - (ay + ah) == 36, "36 units between the region rows"
    assert (ax, ay) == (cx, dy - (cy - ay)) or ax == cx
    assert by == ay and dx == bx and dy == cy
    assert "corridors" in text and "references/layout.md" in text
    assert "one to three words" in text
    assert "from systemap import (" in text and "    Layer,\n" in text
    # The position tables are fenced from the formatter, with the reason
    # beside the fence; every schema name is imported and used.
    assert text.count("# fmt: off") == 2 and text.count("# fmt: on") == 2
    assert text.index("# fmt: off") < text.index("REGIONS = (") < text.index("# fmt: on")
    off2 = text.index("# fmt: off", text.index("# fmt: on"))
    assert off2 < text.index("COMPONENTS: tuple[Component, ...] = ()") < text.rindex("# fmt: on")
    assert "the formatter is turned off" in text
    assert "Steps = tuple[Step, ...]" in text


@pytest.mark.parametrize("both_ways", [False, True])
def test_starter_corridors_route_every_pair_of_regions(
    tmp_path: Path, both_ways: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **FOUR_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    fill_starter(tmp_path / "map/model.py", both_ways)
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    out = capsys.readouterr().out
    assert "map routes: 0 edges through a card they do not connect, 0 across a region" in out
    assert "map layout: clean (4 cards" in out


def test_starter_is_ruff_formatted_at_88_and_100_columns(tmp_path: Path) -> None:
    """The consumer's formatter must accept the starter as written, whatever
    its line length; trailing commas keep the collections exploded."""
    pytest.importorskip("ruff")
    files = scaffold.files("demo", "pkg", [("pkg", "pkg")], ci=False)
    model = tmp_path / "model.py"
    model.write_text(files["map/model.py"])
    for width in ("88", "100"):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "--isolated",
                "--line-length",
                width,
                str(model),
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"line length {width}:\n{proc.stdout}{proc.stderr}"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--select",
            "E,F,I,B,UP,W",
            str(model),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout
    # Every import is used and the only pragma is E501, for the prose the
    # agent writes: once a sentence is in the file, RUF100 has nothing to
    # say, where the old F401 pragma tripped it as soon as every import was used.
    model.write_text(files["map/model.py"] + "# " + "a sentence the agent wrote " * 4 + "\n")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--select",
            "E,F,RUF100",
            str(model),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout


# ---- the label diagnosis: gutter full, or label too wide ----------------------------

CARDS = {"A": (0.0, 50.0, 150.0, 56.0), "B": (190.0, 50.0, 150.0, 56.0)}
CANVAS = (400.0, 200.0)
RUN = [(150.0, 78.0), (190.0, 78.0)]


def obstacles() -> list[tuple[str, tuple[float, float, float, float]]]:
    return [(cid, (x - 3, y - 3, w + 6, h + 6)) for cid, (x, y, w, h) in CARDS.items()]


def test_a_full_gutter_names_its_seats_and_the_fix() -> None:
    """Five short labels on one 40-unit run: none fits on the line, the router
    seats two above the row and two below, and the fifth lands on one."""
    routes = {i: route.Route(points=list(RUN), src_side="right", dst_side="left") for i in range(5)}
    names = {i: f"label 'art{i}' (A -> B)" for i in range(5)}
    placed = route.place_labels(
        routes, dict.fromkeys(routes, 30.0), 13.0, obstacles(), CANVAS, names=names, cards=CARDS
    )
    clean = [p for p in placed.values() if p.cost == 0]
    assert len(clean) == 4, "two seats above the row and two below"
    (hit,) = [p for p in placed.values() if p.cost > 0]
    assert any(h.startswith("label 'art") for h in hit.hits), hit.hits
    assert re.fullmatch(
        r"gutter (above|below) the row of A, B \(y \d+ to \d+\) holds 2 of 2 seats: "
        r"move a card or raise the row pitch",
        hit.fix,
    ), hit.fix
    # With the regions the cards sit in, the fix names the region to open up.
    placed = route.place_labels(
        routes,
        dict.fromkeys(routes, 30.0),
        13.0,
        obstacles(),
        CANVAS,
        names=names,
        cards=CARDS,
        region_of={"A": "work", "B": "work"},
    )
    (hit,) = [p for p in placed.values() if p.cost > 0]
    assert hit.fix.endswith("move a card or raise the row pitch of region work"), hit.fix
    placed = route.place_labels(
        routes,
        dict.fromkeys(routes, 30.0),
        13.0,
        obstacles(),
        CANVAS,
        names=names,
        cards=CARDS,
        region_of={"A": "work", "B": "keep"},
    )
    (hit,) = [p for p in placed.values() if p.cost > 0]
    assert hit.fix.endswith("raise the row pitch of region keep or work"), hit.fix
    # Without the cards there is no gutter to count, and no fix is claimed.
    placed = route.place_labels(
        routes, dict.fromkeys(routes, 30.0), 13.0, obstacles(), CANVAS, names=names
    )
    assert all(p.fix == "" for p in placed.values())


def test_a_label_with_no_seat_off_a_card_is_too_wide() -> None:
    """Headers above and below the row leave the label nowhere but the 40-unit
    run, which a 90-unit label overhangs: the fix is to shorten it."""
    blocked = obstacles() + [
        ("r header", (0.0, 0.0, 400.0, 47.0)),
        ("foot", (0.0, 109.0, 400.0, 91.0)),
    ]
    one = {0: route.Route(points=list(RUN), src_side="right", dst_side="left")}
    placed = route.place_labels(
        one, {0: 90.0}, 13.0, blocked, CANVAS, names={0: "label 'x' (A -> B)"}, cards=CARDS
    )
    # 40 units of run minus the port and arrow clearances (6 and 16) hold 18.
    assert placed[0].fix == "label is 72 units wider than its seat: shorten the artifact"


def test_the_collision_line_carries_the_fix(sample: Sample) -> None:
    """A sentence as an artifact, wider than the canvas: the check's line
    names what it overlaps and says to shorten it."""
    import dataclasses

    long = (
        "the reader hands the parser one request at a time and waits for the parts to come "
        "back before it reads the next line of the source, which is what a sentence does here"
    )
    model = dataclasses.replace(
        sample.model,
        flows=tuple(
            dataclasses.replace(f, artifact=long) if f.edge == ("Reader", "Parser") else f
            for f in sample.model.flows
        ),
    )
    _svg, detail = render_schematic(model, sample.meaning, sample.theme, sample.facts)
    lines = [
        line
        for line in check_labels(json.loads(detail)["_meta"])
        if line.startswith("label collision")
    ]
    assert len(lines) == 1, lines
    assert lines[0].startswith(f"label collision: '{long}' (Reader -> Parser) overlaps ")
    assert re.search(
        r"; label is \d+ units wider than its seat: shorten the artifact$", lines[0]
    ), lines[0]


# ---- gutters ------------------------------------------------------------------------


def test_gutters_are_named_from_the_card_grid() -> None:
    cards = {
        "A": (60.0, 100.0, 150.0, 56.0),
        "B": (250.0, 100.0, 150.0, 56.0),
        "C": (60.0, 192.0, 150.0, 56.0),
        "U": (10.0, 110.0, 150.0, 44.0),  # an actor overlapping row 1 in y: one row
    }
    rows, cols = route.gutters(cards, (500.0, 300.0))
    # Named by the cards on either side, in reading order, and the span covered.
    assert [g.name for g in rows] == [
        "above the row of U, A, B (y 0 to 100)",
        "between the row of U, A, B and the row of C (y 156 to 192)",
        "below the row of C (y 248 to 300)",
    ]
    assert (rows[1].lo, rows[1].hi) == (156.0, 192.0)
    assert rows[1].before == ("U", "A", "B") and rows[1].after == ("C",)
    assert rows[0].before == () and rows[0].after == ("U", "A", "B")
    assert [g.name for g in cols] == [
        "left of the column of A, U, C (x 0 to 10)",
        "between the column of A, U, C and the column of B (x 210 to 250)",
        "right of the column of B (x 400 to 500)",
    ]
    # More than three neighbours are counted, not listed.
    many = {f"C{k}": (60.0 + 190.0 * k, 100.0, 150.0, 56.0) for k in range(5)}
    rows, _cols = route.gutters(many, (1100.0, 300.0))
    assert rows[0].name == "above the row of C0, C1, C2 and 2 more (y 0 to 100)"
    assert route.seats(36.0, 13.0) == 2, (
        "two 13-unit labels with a 2-unit gap, 3 clear of each card"
    )
    assert route.seats(104.0, 13.0) == 6
    assert route.seats(10.0, 13.0) == 0
    assert route.locate((100.0, 160.0, 40.0, 13.0), True, rows, cols) is rows[1]
    # A horizontal label level with a card row sits in the column gutter instead.
    assert route.locate((215.0, 120.0, 30.0, 13.0), True, rows, cols) is cols[1]
    assert route.gutters({}, (100.0, 100.0)) == ([], [])


# ---- describe -----------------------------------------------------------------------


def test_describe_reads_the_picture_back(sample: Sample) -> None:
    lines = describe.run(sample.model, sample.meaning, sample.theme, sample.facts)
    text = "\n".join(lines)
    assert lines[0] == "canvas 900 x 400: 5 cards, 5 edges, 2 regions, 6 readings"
    assert "  work: 2 cards (Reader, Parser)" in lines
    assert "  keep: 2 cards (Ledger, Writer)" in lines
    assert "  in a container only: 1 card (User)" in lines
    edges = [line for line in lines if re.match(r"  \w+ -> \w+ \('", line)]
    assert len(edges) == 5
    bends = [int(re.search(r"(\d+) bends?", line).group(1)) for line in edges]  # type: ignore[union-attr]
    assert bends == sorted(bends, reverse=True), "worst first"
    assert all("long; label " in line for line in edges)
    gutters = [
        line for line in lines if re.match(r"  (above|below|between|left of|right of) ", line)
    ]
    assert gutters, "every gutter of the card grid is listed"
    for line in gutters:
        assert re.search(r"\(\d+ units\): \d+ of \d+ seats used, \d+ labels?$", line), line
    assert "  structure: 5 cards, 0 edges" in lines
    assert "  system: 2 cards, 1 edge" in lines
    assert "  data: 4 cards, 2 edges" in lines
    assert "  memory: 2 cards, 1 edge" in lines
    assert "check refuses" not in text, "a clean map has nothing to refuse"


def test_describe_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **FOUR_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    capsys.readouterr()
    # The empty starter has nothing to describe, and says what the check says.
    assert run("--root", str(tmp_path), "describe") == 1
    assert capsys.readouterr().out == "the model has no components yet; see the skill\n"
    fill_starter(tmp_path / "map/model.py", False)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "describe") == 0
    out = capsys.readouterr().out
    assert re.match(r"canvas \d+ x \d+: 4 cards, 6 edges, 4 regions, 4 readings\n", out)
    assert "positions: 0 pinned, 4 placed\n" in out
    assert "  a: 1 card (A)\n" in out and "  d: 1 card (D)\n" in out
    assert "gutters: seats used" in out and "readings: the cards and edges each lights" in out
    # A model that contradicts itself cannot be drawn: the same refusal as check.
    model = tmp_path / "map/model.py"
    text = model.read_text()
    a = re.search(r'id="A".*?(x=\d+, y=\d+)', text, re.S)
    b = re.search(r'id="B".*?(x=\d+, y=\d+)', text, re.S)
    assert a and b
    model.write_text(text.replace(b.group(1), a.group(1)))
    assert run("--root", str(tmp_path), "describe") == 1
    assert "placement: A overlaps B" in capsys.readouterr().out


def test_layout_reference_says_what_place_does_and_what_the_agent_decides() -> None:
    layout = skill.files()["references/layout.md"]
    for phrase in (
        "what is still yours to decide",
        "`systemap place` places every card that has no `x` and `y`",
        "may not cross a region it does not belong to",
        "two-column grid",
        "48 units between the region columns, 36 between the region\n  rows",
        "columns 190 apart and rows\n  92 apart",
        "barycentre sweeps",
        "`systemap place --print`",
        "a second run changes nothing",
        "**Which region a card is in.**",
        "**The order of the regions.**",
        "**When to pin a card.**",
        "`place --all` keeps it\n  where it is",
        "`systemap place --all` lays every card out\nagain and keeps only the cards marked `pinned=True`",
        "one to three\n  words",
        "raise the row\n  pitch of region X",
        "systemap describe",
        "how\nmany cards are pinned",
        "between the row of A, B and\nthe row of C (y 160 to 226)",
        "observed, external and declared",
    ):
        assert phrase in layout, phrase
    # What place does is no longer the agent's to do by hand.
    for gone in ("Put the cards on the grid", "never tile a container", "Leave one empty"):
        assert gone not in layout, gone
