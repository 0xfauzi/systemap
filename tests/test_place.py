"""`systemap place`: a position for every card without one, and `--all`.

The acceptance lines of ROADMAP.md, gap 1, each as a test: the anonymised
144-module fixture with every position stripped is placed and the
geometry check is clean with no manual move, in under ten seconds; a
card with a position is kept where it was; a second run changes nothing;
the self-map with its positions stripped is clean after `place`. Then
the edit in place: only the `x=` and `y=` values, the boxes and the
canvas move, byte for byte, and the file reloads to the positions
computed. Then `place --all`: every card laid out again but the ones
marked `pinned=True`, which stay, and the refusal for a full box names
it.

"Clean" here is the geometry the placement decides: placement, routes,
labels, type size and wheels (`check.Result.problems`, `through` and
`across`). The fixture's facts are module names only, so its coverage
and entry rules are not what these tests measure.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
import time
from pathlib import Path
from typing import Any

import fixture_workspace
import pytest
from conftest import STARTER_MODULES, sample_model, write_tree

from systemap import check, config, place
from systemap import theme as theme_mod
from systemap.cli import main
from systemap.model import Component, Container, Flow, Meaning, Model, Region, all_layers, problems

ROOT = Path(__file__).resolve().parent.parent


def stripped(model: Model) -> Model:
    """The model with every position removed: what a first draft looks like."""
    return dataclasses.replace(
        model,
        components=tuple(dataclasses.replace(c, x=None, y=None) for c in model.components),
    )


def geometry(model: Model, meaning: Meaning, facts: dict[str, Any]) -> check.Result:
    t = theme_mod.resolve({}, all_layers(model, meaning))
    return check.run(model, meaning, t, facts)


def assert_clean(model: Model, meaning: Meaning, facts: dict[str, Any]) -> None:
    assert problems(model, meaning) == []
    result = geometry(model, meaning, facts)
    assert result.problems == [], result.problems
    assert (result.through, result.across) == (0, 0)


# ---- (a) the fixture, stripped: clean, no manual move, under ten seconds -------------


def test_fixture_stripped_is_clean_after_place_in_under_ten_seconds() -> None:
    model, meaning = stripped(fixture_workspace.MODEL), fixture_workspace.MEANING
    assert not any(c.positioned for c in model.components)
    # The fixture's pinned card is stripped too: a pinned card with no
    # position is placed like any other, in both modes.
    assert [c.id for c in model.components if c.pinned] == ["CropPicker"]
    t0 = time.perf_counter()
    placement = place.compute(model)
    placed = place.apply(model, placement)
    elapsed = time.perf_counter() - t0
    assert elapsed < 10.0, f"place took {elapsed:.2f}s"
    assert placement.fresh and placement.kept == ()
    assert len(placement.positions) == len(model.components) == 28
    assert_clean(placed, meaning, fixture_workspace.facts())
    # Every card is on its region's grid: 20 in from the left, 40 below the
    # top, columns 190 apart, rows 92 apart.
    for c in placed.components:
        if c.region is None:
            continue
        rx, ry, _w, _h = placement.regions[c.region]
        assert (c.x - rx - 20) % 190 == 0 and (c.y - ry - 40) % 92 == 0, c.id  # type: ignore[operator]
    # The regions of one container sit on a two-column grid with the
    # corridors layout.md specifies: 48 between the columns, 36 between rows.
    server = [r for r in placed.regions if r.container == "server"]
    xs = sorted({r.box[0] for r in server})
    assert len(xs) == 2
    left = max(r.box[0] + r.box[2] for r in server if r.box[0] == xs[0])
    assert xs[1] - left == 48
    rows = sorted({r.box[1] for r in server})
    for above, below in zip(rows, rows[1:], strict=False):
        tallest = max(r.box[3] for r in server if r.box[1] == above)
        assert below - (above + tallest) == 36
    # Every region holds its cards and every container its regions.
    for r in placed.regions:
        assert r.container is not None
        cx, cy, cw, ch = placement.containers[r.container]
        assert r.box[0] >= cx and r.box[1] >= cy
        assert r.box[0] + r.box[2] <= cx + cw and r.box[1] + r.box[3] <= cy + ch
    # A second computation is the same computation, and --all on a model
    # with no position is the same layout: nothing is kept either way.
    assert place.compute(model) == placement
    assert place.compute(model, all_cards=True) == dataclasses.replace(placement, all_cards=True)


# ---- (b) a card with a position stays where it was --------------------------------


def test_a_positioned_card_stays_where_it_was() -> None:
    meaning = fixture_workspace.MEANING
    fresh = place.apply(
        stripped(fixture_workspace.MODEL), place.compute(stripped(fixture_workspace.MODEL))
    )
    gateway = fresh.component("Gateway")
    # Everything stripped again but Gateway: the boxes stay as written and
    # the other cards take the free slots around it.
    partly = dataclasses.replace(
        fresh,
        components=tuple(
            c if c.id == "Gateway" else dataclasses.replace(c, x=None, y=None)
            for c in fresh.components
        ),
    )
    placement = place.compute(partly)
    assert not placement.fresh
    assert placement.kept == ("Gateway",)
    assert "Gateway" not in placement.positions
    assert len(placement.positions) == 27
    assert placement.regions == {r.id: r.box for r in fresh.regions}
    assert placement.canvas == fresh.canvas
    placed = place.apply(partly, placement)
    assert (placed.component("Gateway").x, placed.component("Gateway").y) == (
        gateway.x,
        gateway.y,
    )
    assert_clean(placed, meaning, fixture_workspace.facts())
    # Pinned off the grid, it still stays, and nothing is put on top of it.
    off = dataclasses.replace(
        partly,
        components=tuple(
            dataclasses.replace(c, x=gateway.x + 7, y=gateway.y + 5) if c.id == "Gateway" else c  # type: ignore[operator]
            for c in partly.components
        ),
    )
    placed = place.apply(off, place.compute(off))
    assert (placed.component("Gateway").x, placed.component("Gateway").y) == (
        gateway.x + 7,  # type: ignore[operator]
        gateway.y + 5,  # type: ignore[operator]
    )
    assert not [p for p in placed.layout_problems() if "overlaps" in p]


def test_place_all_lays_every_card_out_again_and_keeps_the_pinned_ones() -> None:
    """`place --all` on a placed model: the pinned card stays, every other
    card is laid out again inside the boxes as written, and the result is
    clean; on a model with no pinned card it is the whole layout again."""
    meaning = fixture_workspace.MEANING
    fresh = place.apply(
        stripped(fixture_workspace.MODEL), place.compute(stripped(fixture_workspace.MODEL))
    )
    assert all(c.positioned for c in fresh.components)
    picker = fresh.component("CropPicker")
    assert picker.pinned
    # Without --all there is nothing to do: every card has a position.
    nothing = place.compute(fresh)
    assert nothing.positions == {} and len(nothing.kept) == 28 and not nothing.all_cards
    assert place.lines(nothing) == [
        f"place: 0 cards placed, 28 kept (already positioned): {place.NOTHING_TO_PLACE}"
    ]
    # With --all the pinned card is the one kept; the boxes stay as written.
    placement = place.compute(fresh, all_cards=True)
    assert placement.all_cards and not placement.fresh
    assert placement.kept == ("CropPicker",)
    assert "CropPicker" not in placement.positions and len(placement.positions) == 27
    assert placement.regions == {r.id: r.box for r in fresh.regions}
    assert placement.canvas == fresh.canvas
    again = place.apply(fresh, placement)
    assert (again.component("CropPicker").x, again.component("CropPicker").y) == (
        picker.x,
        picker.y,
    )
    assert_clean(again, meaning, fixture_workspace.facts())
    assert place.lines(placement)[0] == "place: 27 cards placed, 1 kept (pinned)"
    # Deterministic: --all on its own result computes the same placement.
    assert place.compute(again, all_cards=True) == placement
    # Every card pinned: nothing to lay out again, and the line says so.
    pinned = dataclasses.replace(
        fresh, components=tuple(dataclasses.replace(c, pinned=True) for c in fresh.components)
    )
    assert place.lines(place.compute(pinned, all_cards=True)) == [
        f"place: 0 cards placed, 28 kept (pinned): {place.EVERY_CARD_PINNED}"
    ]
    # No card pinned: --all is the whole layout again, boxes and canvas included.
    unpinned = dataclasses.replace(
        fresh, components=tuple(dataclasses.replace(c, pinned=False) for c in fresh.components)
    )
    whole = place.compute(unpinned, all_cards=True)
    assert whole.fresh and whole.kept == () and len(whole.positions) == 28


def test_fill_puts_the_card_that_talks_next_to_its_neighbour_and_refuses_a_full_box() -> None:
    def model(*ids: str, flows: tuple[Flow, ...] = ()) -> Model:
        return Model(
            canvas=(600, 200),
            containers=(),
            regions=(Region("r", "R", (0, 0, 570, 112)),),
            components=(
                Component("A", "a", region="r", x=20, y=40),
                *(Component(i, i.lower(), region="r") for i in ids),
            ),
            flows=flows,
            flow_kinds=(),
        )

    # Three slots, A pinned in the first; C talks to A and takes the slot beside it.
    placement = place.compute(model("B", "C", flows=(Flow("A", "C", "x", "data"),)))
    assert placement.kept == ("A",)
    assert placement.positions == {"C": (210, 40), "B": (400, 40)}
    # A full box: the refusal names place --all, which lays every card out
    # again; under --all, with the pinned cards filling the box, it names
    # the pin instead.
    with pytest.raises(
        place.PlaceError,
        match=r"r has 2 free slots for 3 cards \(B, C, D\): run: systemap place --all, which lays "
        r"every card out again and keeps only the cards marked pinned=True; or widen",
    ):
        place.compute(model("B", "C", "D"))
    full = model("B", "C", "D")
    full = dataclasses.replace(
        full,
        components=(
            dataclasses.replace(full.components[0], pinned=True),
            *(dataclasses.replace(c, x=k, y=40) for k, c in enumerate(full.components[1:])),
        ),
    )
    with pytest.raises(
        place.PlaceError,
        match=r"r has 2 free slots for 3 cards \(B, C, D\): unpin a card \(drop pinned=True\), "
        r"widen or heighten its box, or move a pinned card",
    ):
        place.compute(full, all_cards=True)
    # A card pinned off the grid blocks the slots it comes near.
    near = Model(
        canvas=(600, 200),
        containers=(),
        regions=(Region("r", "R", (0, 0, 570, 112)),),
        components=(
            Component("A", "a", region="r", x=100, y=40),
            Component("B", "b", region="r"),
        ),
        flows=(),
        flow_kinds=(),
    )
    assert place.compute(near).positions == {"B": (400, 40)}


# ---- (c) idempotent, and written in place --------------------------------------------


def fixture_source_without_positions() -> str:
    """The fixture module with every `x=` and `y=` line removed."""
    text = (ROOT / "tests" / "fixture_workspace.py").read_text(encoding="utf-8")
    out = re.sub(r"^\s+[xy]=[^\n]*,\n", "", text, flags=re.M)
    assert "x=" not in out.split("COMPONENTS = (")[1].split("# (from, to")[0]
    return out


def test_place_writes_the_model_in_place_and_a_second_run_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"systemap.toml": "", "map/model.py": fixture_source_without_positions()})
    model_path = tmp_path / "map/model.py"
    before = model_path.read_text(encoding="utf-8")
    assert main(["--root", str(tmp_path), "place", "--print"]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("place: 28 cards placed, 0 kept, every box and the canvas laid out\n")
    assert "  Gateway: x=" in printed and "  region gateway: box=(" in printed
    assert "  container server: box=(" in printed and "  canvas: (" in printed
    assert model_path.read_text(encoding="utf-8") == before, "--print writes nothing"

    assert main(["--root", str(tmp_path), "place"]) == 0
    out = capsys.readouterr().out
    assert out == (
        "place: wrote map/model.py: 28 cards placed, 0 kept; every box and the canvas "
        "laid out\nrun: systemap check\n"
    )
    after = model_path.read_text(encoding="utf-8")
    # Only positions, boxes and the canvas moved: every other line is byte
    # for byte. With the inserted x and y lines taken out and every number
    # masked, the two files are the same text.
    changed = [
        line
        for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    assert changed and all(
        re.search(r"[xy]=\d+,|box=\(\d+, \d+, \d+, \d+\)|canvas=\(\d+, \d+\)", line)
        for line in changed
    ), changed
    inserted = re.sub(r"^\s+[xy]=\d+,\n", "", after, flags=re.M)
    assert re.sub(r"\d+", "N", inserted) == re.sub(r"\d+", "N", before)
    assert inserted != after, "the x and y lines were inserted"
    model, meaning = config.load_model(model_path)
    assert all(c.positioned for c in model.components)
    expected = place.apply(
        *(lambda m: (m, place.compute(m)))(config.load_model(tmp_path / "map/model.py")[0])
    )
    assert expected == model, "the written positions are the computed ones"
    assert_clean(model, meaning, fixture_workspace.facts())

    # Idempotent: a second run has nothing to place and changes nothing.
    assert main(["--root", str(tmp_path), "place"]) == 0
    assert capsys.readouterr().out == (
        f"place: 0 cards placed, 28 kept (already positioned): {place.NOTHING_TO_PLACE}\n"
    )
    assert model_path.read_text(encoding="utf-8") == after

    # --all lays every card out again but the pinned one, writes the file,
    # and a second --all changes nothing more; the result is clean.
    assert main(["--root", str(tmp_path), "place", "--all"]) == 0
    assert capsys.readouterr().out == (
        "place: wrote map/model.py: 27 cards placed, 1 kept (pinned)\nrun: systemap check\n"
    )
    relaid = model_path.read_text(encoding="utf-8")
    assert re.sub(r"\d+", "N", relaid) == re.sub(r"\d+", "N", after)
    model, meaning = config.load_model(model_path)
    assert model.component("CropPicker").pinned
    assert_clean(model, meaning, fixture_workspace.facts())
    assert main(["--root", str(tmp_path), "place", "--all"]) == 0
    assert model_path.read_text(encoding="utf-8") == relaid


def test_place_inserts_in_the_call_style_the_file_uses(tmp_path: Path) -> None:
    """An exploded call gets one keyword per line at its indent; a one-line
    call gets them inline; a value that is there is replaced where it is."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    model_path = tmp_path / "map/model.py"
    text = model_path.read_text(encoding="utf-8")
    text = (
        text.replace(
            "COMPONENTS: tuple[Component, ...] = ()\n",
            "COMPONENTS: tuple[Component, ...] = (\n"
            "    Component(\n"
            '        id="Reader",\n'
            '        region="a",\n'
            '        does="Reads.",\n'
            '        implemented_by=("pkg.reader",),\n'
            '        entry="read",\n'
            "    ),\n"
            '    Component(id="Writer", region="b", does="Writes.", implemented_by=("pkg.writer",), entry="write", x=None, y=None),\n'
            ")\n",
        )
        .replace(
            "FLOWS: tuple[Flow, ...] = ()\n",
            'FLOWS: tuple[Flow, ...] = (Flow("Reader", "Writer", "request", "data"),)\n',
        )
        .replace(
            "PLAIN: dict[str, str] = {}\n",
            'PLAIN: dict[str, str] = {"Reader": "r", "Writer": "w"}\n',
        )
        .replace(
            "RELATIONS: dict[tuple[str, str], str] = {}\n",
            'RELATIONS: dict[tuple[str, str], str] = {("Reader", "Writer"): "The reader hands over."}\n',
        )
    )
    model_path.write_text(text, encoding="utf-8")
    assert main(["--root", str(tmp_path), "place"]) == 0
    written = model_path.read_text(encoding="utf-8")
    assert re.search(r'        entry="read",\n        x=\d+,\n        y=\d+,\n    \),\n', written)
    assert re.search(r'entry="write", x=\d+, y=\d+\),\n', written)
    assert "x=None" not in written
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0


# ---- (d) the self-map, stripped ------------------------------------------------------


def test_self_map_stripped_is_clean_after_place() -> None:
    model, meaning = config.load_model(ROOT / "map" / "model.py")
    facts = check.extract.read_facts(ROOT / "docs" / "map" / "map.json")
    placement = place.compute(stripped(model))
    placed = place.apply(stripped(model), placement)
    assert len(placement.positions) == len(model.components)
    assert_clean(placed, meaning, facts)


# ---- the rule, and describe -----------------------------------------------------------


def test_check_refuses_a_card_without_a_position() -> None:
    model, meaning = sample_model()
    partial = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(c, x=None) if c.id == "Parser" else c for c in model.components
        ),
    )
    assert "placement: Parser has no position (x, y); run: systemap place" in problems(
        partial, meaning
    )
    assert not [p for p in partial.layout_problems() if "overlaps" in p or "outside" in p]
    with pytest.raises(ValueError, match="Parser has no position"):
        _ = partial.component("Parser").box
    assert Component("X", "x").positioned is False and Component("X", "x", x=0, y=0).positioned
    assert Component("X", "x", x=0, y=0).pinned is False


def test_describe_reports_placed_and_pinned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    model_path = tmp_path / "map/model.py"
    text = (
        model_path.read_text(encoding="utf-8")
        .replace(
            "COMPONENTS: tuple[Component, ...] = ()\n",
            "COMPONENTS: tuple[Component, ...] = (\n"
            '    Component(id="Reader", region="a", does="Reads.", implemented_by=("pkg.reader",), entry="read", x=60, y=100, pinned=True),\n'
            '    Component(id="Writer", region="a", does="Writes.", implemented_by=("pkg.writer",), entry="write"),\n'
            ")\n",
        )
        .replace(
            "PLAIN: dict[str, str] = {}\n",
            'PLAIN: dict[str, str] = {"Reader": "r", "Writer": "w"}\n',
        )
    )
    model_path.write_text(text, encoding="utf-8")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "describe"]) == 0
    out = capsys.readouterr().out
    # Pinned is the flag, not a position: Reader is pinned, Writer is placed
    # for this look only.
    assert (
        "positions: 1 pinned, 0 placed, 1 placed for this look and not yet written (Writer); "
        "run: systemap place\n"
    ) in out
    assert "evidence: " in out
    # The check does not place: it refuses the card until place has written it.
    assert main(["--root", str(tmp_path), "check"]) == 1
    assert (
        "placement: Writer has no position (x, y); run: systemap place" in capsys.readouterr().out
    )


def test_first_layout_refuses_a_card_with_no_home_and_places_loose_regions() -> None:
    homeless = Model(
        canvas=(100, 100),
        containers=(),
        regions=(),
        components=(Component("A", "a"),),
        flows=(),
        flow_kinds=(),
    )
    with pytest.raises(place.PlaceError, match="A names no region or container"):
        place.compute(homeless)
    # Regions with no container form the grid straight on the canvas, and a
    # container with a long sub is widened until the sub fits two lines.
    model = Model(
        canvas=(100, 100),
        containers=(
            Container("out", "OUTSIDE", (0, 0, 1, 1), sub="a sub line " * 12, tone="host"),
        ),
        regions=(Region("a", "A", (0, 0, 1, 1)), Region("b", "B", (0, 0, 1, 1))),
        components=(
            Component("U", "u", kind="actor", container="out"),
            Component("P", "p", region="a"),
            Component("Q", "q", region="b"),
        ),
        flows=(Flow("U", "P", "x", "data"), Flow("P", "Q", "y", "data")),
        flow_kinds=(),
    )
    placement = place.compute(model)
    placed = place.apply(model, placement)
    assert placed.layout_problems() == []
    assert placement.regions["b"][0] - (placement.regions["a"][0] + placement.regions["a"][2]) == 48
    (out,) = placed.containers
    assert out.box[2] > 190 and place.sub_lines(out.sub, out.box[2]) == 2
    meaning = Meaning(
        plain={"U": "u", "P": "p", "Q": "q"}, relations={f.edge: "s" for f in model.flows}
    )
    assert_clean(placed, meaning, {})
