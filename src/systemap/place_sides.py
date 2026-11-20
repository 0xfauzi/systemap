"""The placer rule for a nested map: the neighbours at the four sides of its frame.

A nested map has one container, the frame, that holds all its parts, and one container
that holds only its actors. The actors are the neighbours: the cards of the map above
that have flows with the part. The fresh layout (`place_layout`) puts the actors in one
column at the left of the frame. This rule moves each actor to a side of the frame:

- The mean centre of the parts that the actor has flows with gives the side. The actor
  goes to the side that is nearest to that centre, in the order left, right, top, bottom
  for equal distances.
- An actor with no flow to a part goes to the side with the most free room.
- The size of a side gives its room: the count of actor cards that fit along it with
  ACTOR_GAP between them. When a side has more actors than room, the actor with the
  smallest added distance moves to a different side with free room. When the four sides
  together have less room than the actors need, the column layout stays.
- Along its side, each actor is near the position of its centre. Two actors on one side
  have ACTOR_GAP or more between them, and all of them stay along the frame.
- When the layout has a label collision or a refused route, the placer tries each actor
  at each other side with free room (`moved`, `place_order`). It keeps the move that gives
  the fewest collisions and refused routes, then the smallest map, while a move removes a
  collision or a refused route (N5 in bench/jev/README.md).
- The frame keeps its regions in REGION_COLUMNS columns, as each other map. More columns
  make the map wider, and the phone opens a map at a zoom of 0.5 at its top left part
  (rule "Phone" of docs/design/atlas.md): then regions and neighbours are outside the
  phone view (P6 in bench/jev/README.md). The placer keeps the layout with the fewest
  collisions and refused routes, then the actors at three sides or more (`few_sides`),
  then the smallest area of the map, then the score (`size_rank`). The area also selects
  the region orders that the placer routes and moves. The rule uses no size of a screen.
  When that layout has more collisions or more refused routes than the column layout, the
  placer keeps the column layout (`kept_or_column`, the column step). Thus the column step
  always meets acceptance 1 of N4 (no more collisions and refused routes than the column),
  and that value is measured on the layout before the column step
  (bench/jev/neighbour_sides_n6.py). N6 to N9 in bench/jev/README.md measure this form of
  the rule.
- The actor container becomes a box around the frame and the actors, so that each actor
  stays in its container. The form (`Form`) gives the space between the frame and an
  actor, the space inside the edge of that box, and whether the box keeps the room for
  its label above the actors. BOX keeps that room. STUDY does not, as the design study
  (docs/design/atlas/tools/sides.py.txt), where the actors have no box. ATLAS, the form of
  the commands from N8, does not keep it either: the atlas page draws no label for the
  actor container of a nested map (`drawBoxes` in atlas_draw.py), thus that room was empty.

A map that does not have this shape keeps the column layout.

`place.compute(model, nested=True)` gives the form ATLAS (`KEPT`), and
`place.compute(model, nested="study")` gives the form STUDY, for the measurements. N1
(BOX, SIDE_GAP 48), N2 (STUDY) and N4 (BOX, SIDE_GAP 44) failed. N3 passed with two
acceptance values that were changed after the results were known. N5 added the moves to a
different side and passed the six acceptance values of N4. Thus `place.sides_for` is true
for the atlas page, and `systemap place`, `systemap describe` and `systemap parts --stub`
use this rule for each map that is not the top map. The records in `bench/jev/README.md`
give the values. A map that has positions keeps them until `systemap place --all` runs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from systemap.model import CARD_H, CARD_W, Box, Container, Model
from systemap.place_layout import (
    CANVAS_MARGIN,
    CONTAINER_PAD,
    Placement,
    Score,
    container_top,
)
from systemap.place_layout import container_width as _container_width

SIDES = ("left", "right", "top", "bottom")
# The space between the frame and an actor in the form BOX: the gap of the column layout
# (N1 measured 48, N3 measured 44). ACTOR_GAP is the space between two actors on one side.
SIDE_GAP = 44
ACTOR_GAP = 26
ACTOR_H = CARD_H["actor"]

Point = tuple[float, float]


def frame_of(model: Model) -> tuple[str, str] | None:
    """Give the ID of the frame and the ID of the actor container of a nested map, or None
    when the map does not have that shape.
    """
    actors = [c for c in model.components if c.kind == "actor"]
    parts = [c for c in model.components if c.kind != "actor"]
    rings = {c.container if c.region is None else None for c in actors}
    region_home = {r.id: r.container for r in model.regions}
    frames = {c.container if c.region is None else region_home.get(c.region) for c in parts}
    if not actors or not parts or len(rings) != 1 or len(frames) != 1:
        return None
    ring, frame = rings.pop(), frames.pop()
    if ring is None or frame is None or ring == frame:
        return None
    if {b.id for b in model.containers} != {ring, frame}:
        return None
    if any(r.container != frame for r in model.regions):
        return None
    return frame, ring


def _centres(model: Model, pos: dict[str, tuple[int, int]]) -> dict[str, Point]:
    return {
        c.id: (pos[c.id][0] + CARD_W / 2, pos[c.id][1] + CARD_H[c.kind] / 2)
        for c in model.components
        if c.id in pos
    }


def _wanted(model: Model, actors: list[str], centre: dict[str, Point]) -> dict[str, Point | None]:
    """Give the mean centre of the parts that each actor has flows with, or None."""
    out: dict[str, Point | None] = {}
    for a in actors:
        others = [
            f.dst if f.src == a else f.src
            for f in model.flows
            if a in (f.src, f.dst) and f.src != f.dst
        ]
        near = [centre[o] for o in others if o in centre and o not in actors]
        out[a] = (
            (sum(p[0] for p in near) / len(near), sum(p[1] for p in near) / len(near))
            if near
            else None
        )
    return out


def _distances(at: Point, frame: Box) -> dict[str, float]:
    x0, y0, w, h = frame
    return {
        "left": at[0] - x0,
        "right": x0 + w - at[0],
        "top": at[1] - y0,
        "bottom": y0 + h - at[1],
    }


def _room(frame: Box) -> dict[str, int]:
    """Give the count of actor cards that fit along each side of the frame."""
    _x, _y, w, h = frame
    down = int((h + ACTOR_GAP) // (ACTOR_H + ACTOR_GAP))
    across = int((w + ACTOR_GAP) // (CARD_W + ACTOR_GAP))
    return {"left": down, "right": down, "top": across, "bottom": across}


def _free(room: dict[str, int], sides: dict[str, list[str]]) -> Callable[[str], int]:
    return lambda s: room[s] - len(sides[s])


def _move_one(
    side: str,
    sides: dict[str, list[str]],
    room: dict[str, int],
    far: dict[str, dict[str, float]],
) -> None:
    """Move one actor from a full side to a different side with free room. The actor with
    the smallest added distance moves, and it goes to its nearest side with free room.
    """
    free = _free(room, sides)
    open_sides = [s for s in SIDES if s != side and free(s) > 0]
    best = min(
        (
            (far[a][s] - far[a][side], k, a, s)
            for k, a in enumerate(sides[side])
            for s in open_sides
        ),
    )
    _cost, _k, actor, to = best
    sides[side].remove(actor)
    sides[to].append(actor)


def _apply_moves(
    sides: dict[str, list[str]], room: dict[str, int], moves: Mapping[str, str]
) -> None:
    """Move each actor of `moves` to its side, when that side has free room."""
    for actor, to in moves.items():
        here = next((s for s in SIDES if actor in sides[s]), None)
        if here is None or here == to or len(sides[to]) >= room[to]:
            continue
        sides[here].remove(actor)
        sides[to].append(actor)


def assign_sides(
    actors: list[str],
    wanted: dict[str, Point | None],
    frame: Box,
    moves: Mapping[str, str] | None = None,
) -> dict[str, list[str]] | None:
    """Give the actors of each side, or None when the four sides have too little room.
    `moves` gives a side for some actors (the search of `place_order`)."""
    room = _room(frame)
    if sum(room.values()) < len(actors):
        return None
    sides: dict[str, list[str]] = {s: [] for s in SIDES}
    far: dict[str, dict[str, float]] = {}
    alone: list[str] = []
    for a in actors:
        at = wanted[a]
        if at is None:
            alone.append(a)
            continue
        far[a] = _distances(at, frame)
        sides[min(SIDES, key=lambda s: far[a][s])].append(a)
    for side in SIDES:
        while len(sides[side]) > room[side]:
            _move_one(side, sides, room, far)
    for a in alone:
        free = _free(room, sides)
        sides[max(SIDES, key=free)].append(a)
    _apply_moves(sides, room, moves or {})
    return sides


def spread(wants: list[float], size: float, lo: float, hi: float) -> list[float]:
    """Give the start of each item along one side, in the order of `wants` (the centres).

    Each item starts near its wanted centre, at lo or more, ACTOR_GAP after the item
    before it. Then the items that end after hi move back, with the same gaps. The caller
    gives the items sorted by their centres, and they fit between lo and hi.
    """
    out: list[float] = []
    last = lo - ACTOR_GAP
    for want in wants:
        start = max(want - size / 2, last + ACTOR_GAP)
        out.append(start)
        last = start + size
    end = hi - size
    for i in range(len(out) - 1, -1, -1):
        out[i] = min(out[i], end)
        end = out[i] - size - ACTOR_GAP
    return out


def _along(
    side: str, ids: list[str], wanted: dict[str, Point | None], frame: Box
) -> dict[str, float]:
    """Give the position of each actor along its side: y at the left and the right, x at
    the top and the bottom. An actor with no wanted centre wants the middle of the side.
    """
    x0, y0, w, h = frame
    vertical = side in ("left", "right")
    axis = 1 if vertical else 0
    middle = (x0 + w / 2, y0 + h / 2)

    def key(a: str) -> float:
        return (wanted[a] or middle)[axis]

    order = sorted(ids, key=lambda a: (key(a), ids.index(a)))
    size = ACTOR_H if vertical else CARD_W
    lo, hi = (y0, y0 + h) if vertical else (x0, x0 + w)
    starts = spread([key(a) for a in order], size, lo, hi)
    return dict(zip(order, starts, strict=True))


def _shift(box: Box, dx: int, dy: int) -> tuple[int, int, int, int]:
    x, y, w, h = box
    return (int(x + dx), int(y + dy), int(w), int(h))


@dataclass(frozen=True)
class Form:
    """This record gives the form of the rule: the space between the frame and an actor,
    the space from the edge of the actor container to the actors, and whether the actor
    container keeps the room for its label above the actors.
    """

    gap: int
    pad: int
    labelled: bool


# BOX is the form of stage 7: the actor container is a labelled box around the frame and
# the actors. STUDY is the form of docs/design/atlas/tools/sides.py.txt: no room for a
# label, 70 units from the frame to an actor, and 28 units from the edge of the map to
# the cards (CANVAS_MARGIN and 12).
BOX = Form(gap=SIDE_GAP, pad=CONTAINER_PAD, labelled=True)
STUDY = Form(gap=70, pad=28 - CANVAS_MARGIN, labelled=False)
# ATLAS is the form BOX with no room for the label of the actor container, because the
# atlas page draws that label only in the top map (`drawBoxes` in atlas_draw.py).
ATLAS = Form(gap=SIDE_GAP, pad=CONTAINER_PAD, labelled=False)
FORMS = {"box": BOX, "study": STUDY, "atlas": ATLAS}
# The form of the commands: `place.compute(model, nested=True)`. It was BOX until N8.
KEPT = ATLAS


@dataclass(frozen=True)
class _Frame:
    """This record gives the new place of the frame and the lines of the four sides."""

    x: int
    y: int
    w: int
    h: int
    left: int
    top: int
    gap: int

    def seat(self, side: str, v: int) -> tuple[int, int]:
        """Give the top left corner of an actor at position v along a side."""
        if side == "left":
            return (self.left, v)
        if side == "right":
            return (self.x + self.w + self.gap, v)
        if side == "top":
            return (v, self.top)
        return (v, self.y + self.h + self.gap)


def _frame(
    ring: Container, frame: Box, sides: dict[str, list[str]], form: Form
) -> tuple[_Frame, int]:
    """Give the new place of the frame inside the actor container, and the smallest width
    of that container (for its label in the labelled form).
    """
    _x0, _y0, w, h = frame
    left = CANVAS_MARGIN + form.pad
    inner_w = int(w) + sum(CARD_W + form.gap for s in ("left", "right") if sides[s])
    ring_w = _container_width(ring.label, ring.sub, inner_w) if form.labelled else 0
    top = CANVAS_MARGIN + (container_top(ring.sub, ring_w) if form.labelled else form.pad)
    fx = left + (CARD_W + form.gap if sides["left"] else 0)
    fy = top + (ACTOR_H + form.gap if sides["top"] else 0)
    return _Frame(fx, fy, int(w), int(h), left, top, form.gap), ring_w


def sides_of(
    model: Model, laid: Placement, moves: Mapping[str, str] | None = None
) -> dict[str, list[str]] | None:
    """Give the actors of each side of the frame for the column layout `laid`, or None when
    the map does not have the shape of a nested map or the sides have too little room.
    """
    found = frame_of(model)
    if found is None:
        return None
    actors = [c.id for c in model.components if c.kind == "actor"]
    wanted = _wanted(model, actors, _centres(model, laid.positions))
    return assign_sides(actors, wanted, laid.containers[found[0]], moves)


def around(
    model: Model, laid: Placement, form: Form = BOX, moves: Mapping[str, str] | None = None
) -> Placement:
    """Move the actors of a nested map to the sides of its frame. Give the placement
    unchanged when the map does not have that shape or the sides have too little room.
    `moves` gives a side for some actors.
    """
    found = frame_of(model)
    if found is None:
        return laid
    frame_id, ring_id = found
    frame = laid.containers[frame_id]
    actors = [c.id for c in model.components if c.kind == "actor"]
    wanted = _wanted(model, actors, _centres(model, laid.positions))
    sides = assign_sides(actors, wanted, frame, moves)
    if sides is None:
        return laid
    ring = next(b for b in model.containers if b.id == ring_id)
    f, ring_w = _frame(ring, frame, sides, form)
    dx, dy = int(f.x - frame[0]), int(f.y - frame[1])
    pos = {cid: (x + dx, y + dy) for cid, (x, y) in laid.positions.items()}
    moved: Box = (f.x, f.y, f.w, f.h)
    shifted_wants = {a: None if p is None else (p[0] + dx, p[1] + dy) for a, p in wanted.items()}
    for side in SIDES:
        for cid, v in _along(side, sides[side], shifted_wants, moved).items():
            pos[cid] = f.seat(side, int(round(v)))
    right = max([f.x + f.w] + [pos[a][0] + CARD_W for a in actors]) + form.pad
    bottom = max([f.y + f.h] + [pos[a][1] + ACTOR_H for a in actors]) + form.pad
    ring_box = (
        CANVAS_MARGIN,
        CANVAS_MARGIN,
        max(ring_w, right - CANVAS_MARGIN),
        bottom - CANVAS_MARGIN,
    )
    boxes = {
        b.id: _shift(frame, dx, dy) if b.id == frame_id else ring_box for b in model.containers
    }
    return replace(
        laid,
        positions=pos,
        regions={rid: _shift(box, dx, dy) for rid, box in laid.regions.items()},
        containers=boxes,
        canvas=(2 * CANVAS_MARGIN + ring_box[2], 2 * CANVAS_MARGIN + ring_box[3]),
    )


def area(laid: Placement) -> int:
    """Give the area of the map of a layout, in square map units."""
    return laid.canvas[0] * laid.canvas[1]


def few_sides(model: Model, laid: Placement) -> int:
    """Give 1 when the actors of a nested map are at fewer than three sides of the frame
    (fewer than the count of actors when it is less than three), else 0. The rule
    "Neighbours of a nested map" puts them around the frame, not in one column or two
    (docs/design/atlas.md, acceptance 26 of tests/test_atlas_browser.py)."""
    found = frame_of(model)
    if found is None or found[0] not in laid.containers:
        return 0
    fx, fy, fw, fh = laid.containers[found[0]]
    used: set[str] = set()
    for c in model.components:
        if c.kind != "actor" or c.id not in laid.positions:
            continue
        x, y = laid.positions[c.id]
        w, h = CARD_W, CARD_H[c.kind]
        used.update(
            side
            for side, yes in (
                ("left", x + w <= fx),
                ("right", x >= fx + fw),
                ("top", y + h <= fy),
                ("bottom", y >= fy + fh),
            )
            if yes
        )
    actors = sum(1 for c in model.components if c.kind == "actor")
    return int(len(used) < min(3, actors))


def size_rank(model: Model, laid: Placement) -> tuple[int, int, int, int, Score]:
    """Give the rank of a layout of a nested map: the label collisions, the refused routes,
    then the actors at fewer than three sides (`few_sides`), then the area of the map
    (`area`), then the score."""
    score = laid.score or Score(0, 0, 0, 0)
    return (score.collisions, score.refused, few_sides(model, laid), area(laid), score)


def kept_or_column(sides: Placement, column: Placement) -> Placement:
    """Give the sides layout, or the column layout when the sides layout has more label
    collisions or more refused routes than the column layout (N7 in bench/jev/README.md).
    Thus the result never has more of them than the column layout."""
    a, b = sides.score, column.score
    if a is None or b is None or (a.collisions <= b.collisions and a.refused <= b.refused):
        return sides
    return column
