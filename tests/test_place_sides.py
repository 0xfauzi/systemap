"""The placer rule for a nested map: the actors at the four sides of the frame.

`systemap place` does not use the rule, because the measurement N1 failed two of its
acceptance values (bench/jev/README.md). `place.compute(model, nested=True)` uses it.
These tests examine the rule and that the default stays the column layout.

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
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import test_nested

from systemap import place, place_sides
from systemap.model import CARD_W, Container, Model


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


def _side(box: tuple[int, int, int, int], frame: tuple[int, int, int, int]) -> str:
    x, y, w, h = box
    fx, fy, fw, fh = frame
    gap = place_sides.SIDE_GAP
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
    placed = place.apply(grown, place.compute(grown))
    assert placed.layout_problems() == []
    x, y, w, h = placed.component("Extra").box
    fx, fy, fw, fh = frame
    assert x + w <= fx or x >= fx + fw or y + h <= fy or y >= fy + fh
