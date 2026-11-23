"""The placer rule for a nested map: the actors at the four sides of the frame.

`place.compute(model, nested=True)` uses the rule. From N5 (bench/jev/README.md),
`place.SIDES_IN_COMMANDS` is True: the commands give nested=True for each map that is not
the top map when `[render] page = "atlas"`, the default. These tests examine the rule, the
commands with the value True and with the value False, and that the default of
`place.compute` stays the column layout.

Acceptance values, written before the tests:

1. With nested=True, each actor of a nested fixture is outside the frame, at a distance
   of SIDE_GAP from one side of it, and the layout has no layout problems.
2. An actor goes to the side that is nearest to the mean centre of its parts.
3. Without nested, the placement is the column layout: each actor is at the left of
   the frame.
4. A map with a different shape (a third container) keeps the column layout with
   nested=True.
5. `spread` keeps ACTOR_GAP between the items and keeps them between lo and hi.
6. When a side has more actors than room, one actor goes to a different side. When the
   four sides have too little room, the result is None.
7. A new actor in a map with the actors at the sides does not go into the frame.

Acceptance values 8 to 12, written on 2026-11-19 for the repair of stage 7, before these
tests ran:

8. On a full side, the actor that moves is the actor with the smallest added distance,
   and it goes to its nearest side with free room. When that side is full, it goes to the
   next nearest side with free room.
9. Along its side, the centre of each actor of the nested fixtures is the mean centre of
   the parts that it has flows with, within 1 unit, when that centre is along the frame.
10. An actor goes to the top side or the right side when that side is the nearest to the
    mean centre of its parts, and `seat` puts it SIDE_GAP above or at the right of the frame.
11. The fill of free slots of `place` with the boxes of the other containers
    (`place._covered`) gives the same positions as the fill without them, on maps with the
    column layout: the nested fixtures, the top map of the fixture, and the map of this
    repository, each with one card that has no position.
12. With nested="study", each actor is 70 units from one side of the frame, the layout has
    no layout problems, and the frame is higher than with the form BOX, because the actor
    container keeps no room for its label.

Acceptance values 13 to 17, written on 2026-11-19 for the second repair of stage 7, before
these tests ran (the first copy gave the wrong date 2026-11-20):

13. With `[render] page = "atlas"`, `systemap place` writes the nested maps of the fixture
    with the actors at the sides of the frame, and the top map with no change from
    `place.compute` without nested. `systemap describe` gives the canvas of the same
    layout for a nested map without positions. `systemap place` with positions keeps them.
    `systemap parts --stub` writes a stub with the actor at a side. Without that setting,
    the three commands give the column layout.
14. An actor with no flow to a part goes to the side with the most free room.
15. When the four sides have too little room for the actors, `around` gives the column
    layout with no change.
16. `place._covered` gives no box without nested, and no box for a map that does not have
    the shape of a nested map. Thus the fill of each other map does not change.
17. With nested=True, the form is `place_sides.KEPT`, the form BOX.
    Replaced on 2026-11-20 (the repair of stage 2 of the open faults) by acceptance 17b,
    because the rule changed under P5: the atlas page draws no label for the actor
    container of a nested map, thus the form of the commands keeps no room for it.
17b. With nested=True, the form is `place_sides.KEPT`, the form ATLAS: the form BOX with
    no room for the label of the actor container. Acceptance 12 compares STUDY with BOX,
    as before.

Acceptance values 18 and 19, written on 2026-11-19 for the third repair of stage 7, before
these tests ran. Acceptance 13 is now for the commands with `place.SIDES_IN_COMMANDS` set to
True:

18. With `place.SIDES_IN_COMMANDS` False (the value in the repository until N5), `systemap place`,
    `systemap describe` and `systemap parts --stub` give the column layout also with
    `[render] page = "atlas"`, and `systemap place --all` keeps the column layout.
19. With `place.SIDES_IN_COMMANDS` True and `[render] page = "atlas"`, a nested map that
    already has the positions of the column layout keeps them after `systemap place`.
    After `systemap place --all`, its actors are at the sides of the frame, and the
    layout is the layout of `place.compute` with all_cards and nested.

Acceptance values 20 and 21, written on 2026-11-19 for the third repair of stage 10, after
N5 passed and before these tests ran. Acceptance 18 is now for the commands with
`place.SIDES_IN_COMMANDS` set to False:

20. `place.SIDES_IN_COMMANDS` is True in the repository. With no `[render] page` setting,
    `systemap place` writes the nested maps of the fixture with the actors at the sides.
21. On the nested map Page of this repository (map/page.py), the sides layout of
    `place_sides.around` with no side move has one label collision (N4). With the side
    moves of `place_order`, the fresh sides layout has no label collision and no refused
    route, its actors are at three sides or more, and no side has all the actors.
    Replaced on 2026-11-20 (stage 2 of the open faults of the atlas page) by acceptance 21b.
    The value "one label collision" was a value of the layout of N4, not of the rule. The
    rule of the side moves is: while a move of one actor to a different side removes a
    label collision or a refused route, the placer makes the best such move. The change of
    the count of region columns (N6, N7) changed the layout of Page, and the value changed
    with it, but the rule did not change.
    Acceptance 21b also does not keep the two conditions "its actors are at three sides or
    more" and "no side has all the actors" (added to this text on 2026-11-20, after a
    review). They are values of the layout of Page, not of the rule of the side moves that
    acceptance 21 stands for, and acceptance 26 of tests/test_atlas_browser.py holds them
    on the layout of map/page.py. Thus the check is not lost: it is in one test.

Acceptance values 21b to 23, written on 2026-11-20 for stage 2 of the open faults of the
atlas page, before these tests ran:

21b. On the nested map Page, for each count of region columns of `place_sides.grid_counts`
     (from the repair of stage 2 of the open faults: REGION_COLUMNS only, for two region
     orders):
     the side moves (`place_order._clear_sides`) give no more label collisions and refused
     routes than the sides layout with no move, and fewer when that layout has one or more.
     After the moves, no move of one more actor to a different side gives fewer. At least one
     of these layouts has a label collision or a refused route before the moves, thus the
     test examines the moves.
22. P4 of the coordinator: on the nested map Page (map/page.py) and on the nested fixtures,
    each neighbour is at the side of the frame nearest to the parts it has flows with. The
    measure of "nearest": the point is the mean of the centres of the parts that the
    neighbour has flows with. The distance to a side is the distance from that point to the
    line of that side of the frame. The side of the neighbour has the smallest distance of
    the four sides (an equal distance is permitted).
23. When the sides layout has more label collisions or more refused routes than the column
    layout, the placer gives the column layout (`place_sides.kept_or_column`, N7).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import test_nested
import test_parts
from conftest import write_tree

from systemap import config, model_load, nest, place, place_order, place_sides
from systemap.cli import main
from systemap.model import CARD_W, Container, Model

REPO = Path(__file__).resolve().parent.parent


def model_of(source: str) -> Model:
    """Give the MODEL of the text of a model file of a fixture."""
    space: dict[str, Any] = {}
    exec(compile(source, "<fixture>", "exec"), space)  # noqa: S102
    model = space["MODEL"]
    assert isinstance(model, Model)
    return model


def _laid(model: Model, nested: bool) -> Model:
    return place.apply(model, place.compute(model, all_cards=True, nested=nested))


def _frame(model: Model) -> tuple[int, int, int, int]:
    found = place_sides.frame_of(model)
    assert found is not None
    return next(b.box for b in model.containers if b.id == found[0])


def _side(
    box: tuple[int, int, int, int],
    frame: tuple[int, int, int, int],
    gap: int = place_sides.SIDE_GAP,
) -> str:
    x, y, w, h = box
    fx, fy, fw, fh = frame
    sides = {
        "left": x + w + gap == fx,
        "right": x == fx + fw + gap,
        "top": y + h + gap == fy,
        "bottom": y == fy + fh + gap,
    }
    found = [s for s, yes in sides.items() if yes]
    assert len(found) == 1, (box, frame, sides)
    return found[0]


def test_the_actors_are_at_the_sides_of_the_frame() -> None:
    """Acceptance 1 and 2."""
    for source in (test_nested.GATEWAY, test_nested.STYLE):
        laid = _laid(model_of(source), nested=True)
        assert laid.layout_problems() == []
        frame = _frame(laid)
        for c in laid.components:
            if c.kind == "actor":
                _side(c.box, frame)
    style = _laid(model_of(test_nested.STYLE), nested=True)
    frame = _frame(style)
    # Writer gets the guide from Compiler at the top of the frame, and Gateway looks up
    # Cache at the bottom. The nearest sides are the left and the bottom.
    assert _side(style.component("Writer").box, frame) == "left"
    assert _side(style.component("Gateway").box, frame) == "bottom"


def test_the_default_is_the_column() -> None:
    """Acceptance 3."""
    model = model_of(test_nested.GATEWAY)
    laid = _laid(model, nested=False)
    assert laid == place.apply(model, place.compute(model, all_cards=True))
    frame = _frame(laid)
    for c in laid.components:
        if c.kind == "actor":
            assert c.box[0] + CARD_W < frame[0]


def test_a_different_shape_keeps_the_column() -> None:
    """Acceptance 4. The top map of the fixture has the shape of a nested map, thus the
    rule needs nested=True. With a third container it has a different shape."""
    top = model_of(test_nested.TOP)
    assert place_sides.frame_of(top) == ("system", "outside")
    more = Container(id="more", label="MORE", box=(0, 0, 0, 0))
    top = replace(top, containers=(*top.containers, more))
    assert place_sides.frame_of(top) is None
    assert _laid(top, nested=True) == _laid(top, nested=False)


def test_spread_keeps_the_gaps_inside_the_side() -> None:
    """Acceptance 5."""
    gap = place_sides.ACTOR_GAP
    starts = place_sides.spread([0.0, 10.0, 500.0], 44, 100, 400)
    assert starts[0] >= 100
    assert starts[-1] + 44 <= 400
    assert all(b - a >= 44 + gap for a, b in zip(starts, starts[1:], strict=False))
    # An item that wants a position in the side keeps it.
    assert place_sides.spread([250.0], 44, 100, 400) == [228.0]


def test_a_full_side_gives_an_actor_to_a_different_side() -> None:
    """Acceptance 6. The left side of a frame 140 high has room for two actors."""
    frame = (300, 300, 600, 140)
    wanted: dict[str, tuple[float, float] | None] = {
        a: (310.0, 370.0 + k) for k, a in enumerate(("A", "B", "C"))
    }
    sides = place_sides.assign_sides(["A", "B", "C"], wanted, frame)
    assert sides is not None
    assert len(sides["left"]) == 2
    assert sum(len(v) for v in sides.values()) == 3
    small = (300, 300, 150, 44)
    many = {f"A{k}": (310.0, 320.0) for k in range(5)}
    assert place_sides.assign_sides(list(many), dict(many), small) is None


def test_a_new_actor_does_not_go_into_the_frame() -> None:
    """Acceptance 7. The map has the actors at the sides. One more actor gets a free place
    in the actor container, outside the frame."""
    model = model_of(test_nested.GATEWAY)
    laid = _laid(model, nested=True)
    frame = _frame(laid)
    added = replace(laid.component("Reader"), id="Extra", x=None, y=None)
    grown = replace(laid, components=(*laid.components, added))
    placed = place.apply(grown, place.compute(grown, nested=True))
    assert placed.layout_problems() == []
    x, y, w, h = placed.component("Extra").box
    fx, fy, fw, fh = frame
    assert x + w <= fx or x >= fx + fw or y + h <= fy or y >= fy + fh


def test_the_actor_with_the_smallest_added_distance_moves() -> None:
    """Acceptance 8. The left side of a frame 140 high has room for two actors, and the
    top and the bottom have room for three. A, B and C are nearest to the left. C is as
    near to the bottom as to the left, B is 20 units farther from the top, and A is 65
    units farther from the top and the bottom."""
    frame = (300, 300, 600, 140)
    wanted: dict[str, tuple[float, float] | None] = {
        "A": (305.0, 370.0),
        "B": (310.0, 330.0),
        "C": (320.0, 420.0),
    }
    sides = place_sides.assign_sides(["A", "B", "C"], wanted, frame)
    assert sides == {"left": ["A", "B"], "right": [], "top": [], "bottom": ["C"]}
    # With the bottom full, C would add 100 units at the top, and B adds 20: B moves.
    low = {k: (x, 438.0) for k, x in (("D", 400.0), ("E", 600.0), ("F", 800.0))}
    wanted.update(low)
    sides = place_sides.assign_sides([*wanted], wanted, frame)
    assert sides == {"left": ["A", "C"], "right": [], "top": ["B"], "bottom": ["D", "E", "F"]}


def _centre(box: tuple[int, int, int, int]) -> tuple[float, float]:
    return (box[0] + box[2] / 2, box[1] + box[3] / 2)


def test_an_actor_is_near_the_mean_centre_of_its_parts() -> None:
    """Acceptance 9."""
    checked = 0
    for source in (test_nested.GATEWAY, test_nested.STYLE):
        laid = _laid(model_of(source), nested=True)
        fx, fy, fw, fh = _frame(laid)
        actors = [c.id for c in laid.components if c.kind == "actor"]
        centre = {c.id: _centre(c.box) for c in laid.components}
        wanted = place_sides._wanted(laid, actors, centre)
        for a in actors:
            want = wanted[a]
            assert want is not None
            vertical = _side(laid.component(a).box, (fx, fy, fw, fh)) in ("left", "right")
            axis, lo, hi = (1, fy, fy + fh) if vertical else (0, fx, fx + fw)
            if lo <= want[axis] <= hi:
                assert abs(centre[a][axis] - want[axis]) <= 1, (a, centre[a], want)
                checked += 1
    assert checked >= 4


def test_an_actor_goes_to_the_top_or_the_right() -> None:
    """Acceptance 10."""
    frame = (300, 300, 600, 400)
    wanted: dict[str, tuple[float, float] | None] = {"T": (600.0, 310.0), "R": (880.0, 500.0)}
    sides = place_sides.assign_sides(["T", "R"], wanted, frame)
    assert sides == {"left": [], "right": ["R"], "top": ["T"], "bottom": []}
    gap = place_sides.SIDE_GAP
    f = place_sides._Frame(x=300, y=300, w=600, h=400, left=16, top=16, gap=gap)
    assert f.seat("right", 480) == (300 + 600 + gap, 480)
    assert f.seat("top", 525) == (525, 16)
    assert f.seat("bottom", 525) == (525, 300 + 400 + gap)


def _column_maps() -> list[Model]:
    out = [
        place.apply(m, place.compute(m, all_cards=True))
        for m in map(model_of, (test_nested.GATEWAY, test_nested.STYLE, test_nested.TOP))
    ]
    return [*out, nest.load(config.load(REPO)).top.model]


def _fill(model: Model) -> place.Placement | str:
    """Give the placement of the fill, or the error when the boxes have no free slot."""
    try:
        return place.compute(model, nested=True)
    except place.PlaceError as err:
        return str(err)


@pytest.mark.parametrize("k", range(4))
def test_the_cover_term_keeps_the_column_fill(k: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance 11. Each map loses the position of its last actor and of its last part.
    The fill with `_covered` and the fill without it give the same placement, or the same
    error when the box has no free slot."""
    model = _column_maps()[k]
    placed = 0
    for kind_is_actor in (True, False):
        card = [c for c in model.components if (c.kind == "actor") == kind_is_actor][-1]
        free = replace(card, x=None, y=None)
        lost = replace(
            model, components=tuple(free if c.id == card.id else c for c in model.components)
        )
        with_cover = _fill(lost)
        monkeypatch.setattr(place, "_covered", lambda _m, _h, _n: [])
        without = _fill(lost)
        monkeypatch.undo()
        assert with_cover == without
        if not isinstance(with_cover, str):
            assert place.apply(lost, with_cover).layout_problems() == []
            placed += 1
    assert placed >= 1


def test_the_study_form_has_no_room_for_the_label() -> None:
    """Acceptance 12."""
    for source in (test_nested.GATEWAY, test_nested.STYLE):
        model = model_of(source)
        study = place.apply(model, place.compute(model, all_cards=True, nested="study"))
        box = place.apply(model, place.compute(model, all_cards=True, nested="box"))
        assert study.layout_problems() == []
        frame = _frame(study)
        for c in study.components:
            if c.kind == "actor":
                _side(c.box, frame, place_sides.STUDY.gap)
        assert frame[1] < _frame(box)[1]


ATLAS = '[render]\npage = "atlas"\n'
CANVAS = '[render]\npage = "canvas"\n'


def _tree(root: Path, setting: str = ATLAS) -> None:
    config_text = test_nested.CONFIG + setting
    write_tree(root, {**test_nested.TREE, "systemap.toml": config_text, **test_nested.MODELS})


def _loaded(root: Path) -> dict[str, Model]:
    return {m.id: m.model for m in nest.load(config.load(root)).maps}


@pytest.fixture
def sides_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the side rule on in the commands, as when the maintainer accepts N3."""
    monkeypatch.setattr(place, "SIDES_IN_COMMANDS", True)


@pytest.mark.usefixtures("sides_on")
def test_the_commands_put_the_actors_at_the_sides(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 13."""
    _tree(tmp_path)
    before = _loaded(tmp_path)
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "describe"]) == 0
    described = capsys.readouterr().out
    assert main(["--root", str(tmp_path), "place"]) == 0
    after = _loaded(tmp_path)
    assert after[""] == place.apply(before[""], place.compute(before[""]))
    for mid in ("Gateway", "Style"):
        laid = after[mid]
        assert laid == _laid(before[mid], nested=True)
        assert laid != _laid(before[mid], nested=False)
        frame = _frame(laid)
        for c in laid.components:
            if c.kind == "actor":
                _side(c.box, frame)
        w, h = laid.canvas
        assert f"{mid}: canvas {w} x {h}:" in described
    # A second place keeps the positions.
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "place"]) == 0
    assert _loaded(tmp_path) == after


@pytest.mark.parametrize(
    ("setting", "on"), [("", False), ('[render]\npage = "canvas"\n', True), (ATLAS, False)]
)
def test_the_commands_keep_the_column(
    tmp_path: Path,
    setting: str,
    on: bool,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance 13, without the atlas page, and acceptance 18, with the rule off."""
    monkeypatch.setattr(place, "SIDES_IN_COMMANDS", on)
    _tree(tmp_path, setting)
    before = _loaded(tmp_path)
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "describe"]) == 0
    described = capsys.readouterr().out
    assert main(["--root", str(tmp_path), "place"]) == 0
    after = _loaded(tmp_path)
    for mid in ("Gateway", "Style"):
        assert after[mid] == _laid(before[mid], nested=False)
        w, h = after[mid].canvas
        assert f"{mid}: canvas {w} x {h}:" in described
    assert main(["--root", str(tmp_path), "place", "--all"]) == 0
    assert _loaded(tmp_path) == after


def test_a_map_with_positions_keeps_them_until_place_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 19. The first place has the rule off, and writes the column layout."""
    monkeypatch.setattr(place, "SIDES_IN_COMMANDS", False)
    _tree(tmp_path)
    before = _loaded(tmp_path)
    assert main(["--root", str(tmp_path), "extract"]) == 0
    assert main(["--root", str(tmp_path), "place"]) == 0
    column = _loaded(tmp_path)
    for mid in ("Gateway", "Style"):
        assert column[mid] == _laid(before[mid], nested=False)
    monkeypatch.setattr(place, "SIDES_IN_COMMANDS", True)
    assert main(["--root", str(tmp_path), "place"]) == 0
    assert _loaded(tmp_path) == column
    assert main(["--root", str(tmp_path), "place", "--all"]) == 0
    moved = _loaded(tmp_path)
    for mid in ("Gateway", "Style"):
        assert moved[mid] == _laid(column[mid], nested=True)
        frame = _frame(moved[mid])
        for c in moved[mid].components:
            if c.kind == "actor":
                _side(c.box, frame)


def test_an_actor_with_no_flow_goes_to_the_most_free_room() -> None:
    """Acceptance 14. The frame is 600 wide and 140 high: the left and the right have room
    for two actors, the top and the bottom for three. Two actors want the top."""
    frame = (300, 300, 600, 140)
    wanted: dict[str, tuple[float, float] | None] = {
        "A": (400.0, 305.0),
        "B": (700.0, 305.0),
        "C": None,
    }
    sides = place_sides.assign_sides(["A", "B", "C"], wanted, frame)
    assert sides == {"left": [], "right": [], "top": ["A", "B"], "bottom": ["C"]}
    alone = place_sides.assign_sides(["C"], {"C": None}, frame)
    assert alone == {"left": [], "right": [], "top": ["C"], "bottom": []}


def test_too_little_room_keeps_the_column() -> None:
    """Acceptance 15. Twenty actors need more room than the sides of a small frame give."""
    model = model_of(test_nested.GATEWAY)
    actor = model.component("Reader")
    many = tuple(replace(actor, id=f"Actor{k}") for k in range(20))
    model = replace(model, components=(*model.components, *many))
    column = place.compute(model, all_cards=True)
    frame = column.containers["gateway"]
    actors = [c.id for c in model.components if c.kind == "actor"]
    wanted = place_sides._wanted(model, actors, place_sides._centres(model, column.positions))
    assert place_sides.assign_sides(actors, wanted, frame) is None
    assert place_sides.around(model, column) == column


def test_the_cover_is_only_for_a_nested_map() -> None:
    """Acceptance 16."""
    laid = _laid(model_of(test_nested.GATEWAY), nested=True)
    frame = _frame(laid)
    assert place._covered(laid, "around", True) == [frame]
    assert place._covered(laid, "around", False) == []
    assert place._covered(laid, "gateway", True) == []
    # The top map of this repository has the shape of a nested map, but the commands give
    # nested=False for a top map. Its two containers do not overlap.
    repo = nest.load(config.load(REPO)).top.model
    for nested in (False, True):
        assert all(place._covered(repo, b.id, nested) == [] for b in repo.containers)
    other = model_of(test_nested.TOP)
    more = Container(id="more", label="MORE", box=(0, 0, 0, 0))
    assert (
        place._covered(replace(other, containers=(*other.containers, more)), "outside", True) == []
    )


def test_nested_gives_the_kept_form() -> None:
    """Acceptance 17b."""
    assert place_sides.KEPT == place_sides.ATLAS == place_sides.FORMS["atlas"]
    assert place_sides.ATLAS == replace(place_sides.BOX, labelled=False)
    model = model_of(test_nested.STYLE)
    assert _laid(model, nested=True) == place.apply(
        model, place.compute(model, all_cards=True, nested="atlas")
    )


@pytest.mark.parametrize(("atlas", "on"), [(True, True), (False, True), (True, False)])
def test_the_stub_of_a_part_has_the_kept_form(
    tmp_path: Path, atlas: bool, on: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 13 and 18, for `systemap parts --stub`. The stub has no flow, thus its
    actor goes to the side with the most free room."""
    monkeypatch.setattr(place, "SIDES_IN_COMMANDS", on)
    root = test_parts._gate(tmp_path)
    # The atlas page is the default. The canvas page gets its setting.
    with (root / "systemap.toml").open("a", encoding="utf-8") as out:
        out.write(ATLAS if atlas else CANVAS)
    assert test_parts.run(root, "parts", "--stub", "Gate") == 0
    stub = model_load.read(root / "map/gate.py", "map/gate.py", root)["MODEL"]
    bare = replace(
        stub,
        components=tuple(replace(c, x=None, y=None) for c in stub.components),
        containers=tuple(replace(b, box=(0, 0, 0, 0)) for b in stub.containers),
        regions=tuple(replace(r, box=(0, 0, 0, 0)) for r in stub.regions),
        canvas=(0, 0),
    )
    sides = place.apply(bare, place.compute(bare, nested=True))
    column = place.apply(bare, place.compute(bare))
    assert sides != column
    assert stub == (sides if atlas and on else column)
    if atlas and on:
        _side(stub.component("App").box, _frame(stub))


def test_the_commands_use_the_rule_by_default(tmp_path: Path) -> None:
    """Acceptance 20."""
    assert place.SIDES_IN_COMMANDS is True
    _tree(tmp_path, "")
    before = _loaded(tmp_path)
    assert main(["--root", str(tmp_path), "extract"]) == 0
    assert main(["--root", str(tmp_path), "place"]) == 0
    after = _loaded(tmp_path)
    for mid in ("Gateway", "Style"):
        assert after[mid] == _laid(before[mid], nested=True)


def _page() -> Model:
    model = model_load.read(REPO / "map/page.py", "map/page.py", REPO)["MODEL"]
    assert isinstance(model, Model)
    return model


def _sides_now(model: Model, laid: place.Placement) -> dict[str, str]:
    placed = place.apply(model, laid)
    frame = _frame(placed)
    return {c.id: _side(c.box, frame) for c in placed.components if c.kind == "actor"}


def _no_move_left(page: Model, column: place.Placement, laid: place.Placement) -> None:
    """After the side moves, no move of one more actor gives fewer collisions and refused
    routes. The moves are the actors that are not at the side of `place_sides.sides_of`."""
    assert laid.score is not None
    got = (laid.score.collisions, laid.score.refused)
    first = place_sides.sides_of(page, column) or {}
    home = {a: s for s, ids in first.items() for a in ids}
    moves = {a: s for a, s in _sides_now(page, laid).items() if home[a] != s}
    assert place_sides.around(page, column, place_sides.KEPT, moves).positions == laid.positions
    trials = place_order._move_trials(page, column, place_sides.KEPT, moves)
    best = min((t[0][:2] for t in trials), default=None)
    assert best is None or best >= got, (best, got)


def test_the_side_moves_remove_what_a_move_can_remove() -> None:
    """Acceptance 21b. From the repair of stage 2 of the open faults, the frame has
    REGION_COLUMNS columns of regions (no `grid_counts`), and the test examines the region
    order of the column layout and the region order of map/page.py, with the form KEPT."""
    page = _page()
    examined = 0
    for order_ids in (place.compute(page, all_cards=True).order, place_order.grid_order(page)):
        order = tuple(next(r for r in page.regions if r.id == i) for i in order_ids)
        column = place_order._column(page, order)
        plain = place_sides.around(page, column, place_sides.KEPT)
        before = place.score(place.apply(page, plain))
        was = (before.collisions, before.refused)
        laid = place_order._clear_sides(page, replace(plain, order=order_ids), True)
        assert laid.score is not None
        got = (laid.score.collisions, laid.score.refused)
        assert got < was if any(was) else got == was, (order_ids, got, was)
        examined += any(was)
        _no_move_left(page, column, laid)
    assert examined >= 1


def _nearest(model: Model) -> list[tuple[str, str, dict[str, float]]]:
    """Give each neighbour with flows, its side and the distance to each side."""
    frame = _frame(model)
    fx, fy, fw, fh = frame
    actors = {c.id for c in model.components if c.kind == "actor"}
    centre = {c.id: _centre(c.box) for c in model.components}
    out = []
    for a in sorted(actors):
        parts = [
            f.dst if f.src == a else f.src
            for f in model.flows
            if a in (f.src, f.dst) and (f.dst if f.src == a else f.src) not in actors
        ]
        if not parts:
            continue
        mx = sum(centre[p][0] for p in parts) / len(parts)
        my = sum(centre[p][1] for p in parts) / len(parts)
        far = {"left": mx - fx, "right": fx + fw - mx, "top": my - fy, "bottom": fy + fh - my}
        out.append((a, _side(model.component(a).box, frame), far))
    return out


# A neighbour that a side move put off its nearest side to remove label collisions. Each item
# names the record that measured the collisions. Only the maintainer adds an item.
MOVED = {"Judgement": Path("bench/jev/page_side_moves_M1.txt")}


def test_each_neighbour_is_at_the_nearest_side() -> None:
    """Acceptance 22.

    Changed on 2026-11-20, after its measurement, by a decision of the maintainer. Judgement on
    Page is at the bottom, not at its nearest side (the right). M1
    (bench/jev/page_side_moves_M1.txt) measured that the side move removes 2 label collisions,
    and every layout that meets this test and acceptance 26 with no collision fails the phone
    test Z4d (P9). The maintainer chose the layout that looks better, judged by the coordinator to be the side
    rule. Thus a neighbour in MOVED
    may be off its nearest side, if its record shows collisions before the move and none
    after. Each other neighbour must be at its nearest side.
    """
    maps = [_page()] + [
        _laid(model_of(s), nested=True) for s in (test_nested.GATEWAY, test_nested.STYLE)
    ]
    checked = 0
    for model in maps:
        for actor, side, far in _nearest(model):
            checked += 1
            if far[side] <= min(far.values()):
                continue
            assert actor in MOVED, (actor, side, far)
            record = (Path(__file__).resolve().parent.parent / MOVED[actor]).read_text("utf-8")
            assert f"Side moves: {actor} " in record, record
            assert "0 label collisions" in record.split("After the side moves:")[1], record
    assert checked >= 12


def test_a_sides_layout_with_more_collisions_gives_the_column() -> None:
    """Acceptance 23."""
    one = place.Score(collisions=1, refused=0, bends=0, length=0)
    none = place.Score(collisions=0, refused=0, bends=9, length=99)
    sides = place.Placement({}, {}, {}, (1, 1), score=one)
    column = place.Placement({}, {}, {}, (2, 2), score=none)
    assert place_sides.kept_or_column(sides, column) is column
    assert place_sides.kept_or_column(column, sides) is column
    refused = replace(column, score=place.Score(0, 1, 0, 0))
    assert place_sides.kept_or_column(refused, column) is column
