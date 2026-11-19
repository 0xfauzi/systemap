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
- The actor container becomes a box around the frame and the actors, so that each actor
  stays in its container. The form (`Form`) gives the space between the frame and an
  actor, the space inside the edge of that box, and whether the box keeps the room for
  its label above the actors. BOX keeps that room. STUDY does not, as the design study
  (docs/design/atlas/tools/sides.py.txt), where the actors have no box.

A map that does not have this shape keeps the column layout.

The commands do not use this rule. `place.compute(model, nested=True)` (the form BOX) and
`place.compute(model, nested="study")` use it, and only the measurements N1 and N2
(`bench/jev/neighbour_sides.py`) call them. N1 (BOX) and N2 (STUDY) failed two of their
five acceptance values on the nested maps of the test fixtures (the mean distance to the
parts and the zoom of the fit), thus `systemap place` keeps the column layout. The records
in `bench/jev/README.md` give the values.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from systemap.model import CARD_H, CARD_W, Box, Container, Model
from systemap.place_layout import CANVAS_MARGIN, CONTAINER_PAD, Placement, container_top
from systemap.place_layout import container_width as _container_width

SIDES = ("left", "right", "top", "bottom")
# The space between the frame and an actor in the form BOX, and between two actors on one side.
SIDE_GAP = 48
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


def assign_sides(
    actors: list[str], wanted: dict[str, Point | None], frame: Box
) -> dict[str, list[str]] | None:
    """Give the actors of each side, or None when the four sides have too little room."""
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
FORMS = {"box": BOX, "study": STUDY}


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


def around(model: Model, laid: Placement, form: Form = BOX) -> Placement:
    """Move the actors of a nested map to the sides of its frame. Give the placement
    unchanged when the map does not have that shape or the sides have too little room.
    """
    found = frame_of(model)
    if found is None:
        return laid
    frame_id, ring_id = found
    frame = laid.containers[frame_id]
    actors = [c.id for c in model.components if c.kind == "actor"]
    wanted = _wanted(model, actors, _centres(model, laid.positions))
    sides = assign_sides(actors, wanted, frame)
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
