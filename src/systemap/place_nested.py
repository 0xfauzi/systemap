"""The placement of a nested map: the neighbour actors stand around the internal cards.

A nested map shows the inside of one parent component, the opening card. Its actors are
other components of the parent map. After a fresh layout (`place.compute`), this module
puts each actor in one of four bands around the internal cards: top, right, bottom, or
left. The band faces the direction from the opening card to that component in the
parent layout. Thus a neighbour that is at the right of the opening card in the parent
map is at the right of the frame in the nested map.

In each band, the actors keep their parent order: from left to right in the top and the
bottom band, and from top to bottom in the left and the right band.

The module changes only a fresh layout. A placement that keeps known positions does not
move a card. The module does not change the layout if:

- the map is the top map, or the parent placement does not exist yet,
- the opening card or an actor has no position in the parent map,
- the actors are not all in one container that has no region and no internal card.

Then the layout of `place.compute` stays, and `arranged` is False.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from systemap import place
from systemap.model import CARD_H, CARD_W, Box, Component, Container, Model
from systemap.place import Placement
from systemap.schematic_nested import centre, frame_box, side

SIDES = ("top", "right", "bottom", "left")
# The space between the band of actors and the internal cards, for the flow lines and
# their labels.
BAND_GAP = 48


@dataclass(frozen=True)
class Nested:
    """The result of a nested placement. `arranged` tells if the actors are in bands."""

    placement: Placement
    arranged: bool


def parent_sides(parent: Model, card: str, actors: Iterable[str]) -> dict[str, str] | None:
    """Give the band of each actor from the parent layout, or None if the opening card or
    an actor has no position in the parent map."""
    opening = parent.find(card)
    if opening is None or not opening.positioned:
        return None
    ox, oy = centre(opening.box)
    out: dict[str, str] = {}
    for cid in actors:
        found = parent.find(cid)
        if found is None or not found.positioned:
            return None
        x, y = centre(found.box)
        out[cid] = side(x - ox, y - oy)
    return out


def compute(
    model: Model,
    parent: Model | None,
    card: str,
    all_cards: bool = False,
    keep_order: bool = False,
) -> Nested:
    """Calculate the placement of one map (`place.compute`). For a fresh layout of a
    nested map, put the actors in the bands that face their parent directions."""
    laid = place.compute(model, all_cards=all_cards, keep_order=keep_order)
    if parent is None or not laid.fresh:
        return Nested(laid, False)
    actors = [c for c in model.components if c.kind == "actor"]
    holder = _holder(model, actors)
    sides = parent_sides(parent, card, [c.id for c in actors])
    if holder is None or sides is None:
        return Nested(laid, False)
    order = _parent_order(parent, sides)
    moved = _bands(model, laid, holder, order)
    scored = place.apply(model, moved)
    return Nested(replace(moved, score=place.score(scored)), True)


def _holder(model: Model, actors: list[Component]) -> Container | None:
    """Give the one container of all actors, if it has no region and no internal card."""
    homes = {c.container for c in actors if c.region is None}
    if not actors or len(homes) != 1 or any(c.region is not None for c in actors):
        return None
    home = next(iter(homes))
    if any(r.container == home for r in model.regions):
        return None
    if any(c.container == home and c.kind != "actor" for c in model.components):
        return None
    return next((b for b in model.containers if b.id == home), None)


def _parent_order(parent: Model, sides: dict[str, str]) -> dict[str, list[str]]:
    """Give the actors of each band in their parent order."""
    out: dict[str, list[str]] = {s: [] for s in SIDES}
    for cid, where in sides.items():
        out[where].append(cid)
    for where, ids in out.items():
        axis = 0 if where in ("top", "bottom") else 1
        ids.sort(key=lambda cid: centre(_box(parent, cid))[axis])
    return out


def _box(model: Model, cid: str) -> Box:
    found = model.find(cid)
    assert found is not None
    return found.box


def _inner(model: Model, laid: Placement, holder: str) -> Box:
    """Give the bounds of the internal cards, regions, and containers of a layout."""
    boxes: list[Box] = [
        (x, y, CARD_W, CARD_H[model.kind_of(cid)])
        for cid, (x, y) in laid.positions.items()
        if model.kind_of(cid) != "actor"
    ]
    boxes += list(laid.regions.values())
    boxes += [box for cid, box in laid.containers.items() if cid != holder]
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return x0, y0, x1 - x0, y1 - y0


def _row(ids: list[str], start: float, room: float) -> dict[str, float]:
    """Give the left edge of each card of a band row, centred in `room`."""
    span = len(ids) * place.COL_PITCH - place.COL_GUTTER
    first = start + max(0.0, (room - span) / 2)
    return {cid: first + k * place.COL_PITCH for k, cid in enumerate(ids)}


def _column(ids: list[str], start: float, room: float) -> dict[str, float]:
    """Give the top edge of each card of a band column, centred in `room`."""
    h = CARD_H["actor"]
    span = len(ids) * place.ROW_PITCH - (place.ROW_PITCH - h)
    first = start + max(0.0, (room - span) / 2)
    return {cid: first + k * place.ROW_PITCH for k, cid in enumerate(ids)}


def _bands(
    model: Model, laid: Placement, holder: Container, order: dict[str, list[str]]
) -> Placement:
    """Move the internal layout and put the actors in their bands in one container."""
    ix, iy, iw, ih = _inner(model, laid, holder.id)
    m, pad, ah = place.CANVAS_MARGIN, place.CONTAINER_PAD, CARD_H["actor"]
    inner_x = m + pad + (CARD_W + BAND_GAP if order["left"] else 0)
    top_x = _row(order["top"], inner_x, iw)
    bottom_x = _row(order["bottom"], inner_x, iw)
    right_x = inner_x + iw + BAND_GAP
    ends = [inner_x + iw, *(x + CARD_W for x in [*top_x.values(), *bottom_x.values()])]
    ends += [right_x + CARD_W] if order["right"] else []
    w = place.container_width(holder.label, holder.sub, int(max(ends)) - m - pad)
    top_y = m + place.container_top(holder.sub, w)
    inner_y = top_y + (ah + BAND_GAP if order["top"] else 0)
    left_y = _column(order["left"], inner_y, ih)
    right_y = _column(order["right"], inner_y, ih)
    low = max([inner_y + ih, *(y + ah for y in [*left_y.values(), *right_y.values()])])
    bottom_y = low + BAND_GAP
    pos: dict[str, tuple[float, float]] = {cid: (x, top_y) for cid, x in top_x.items()}
    pos |= {cid: (x, bottom_y) for cid, x in bottom_x.items()}
    pos |= {cid: (m + pad, y) for cid, y in left_y.items()}
    pos |= {cid: (right_x, y) for cid, y in right_y.items()}
    low = bottom_y + ah if order["bottom"] else low
    h = int(low) + pad - m
    dx, dy = inner_x - ix, inner_y - iy
    out = {
        cid: (int(x + dx), int(y + dy))
        for cid, (x, y) in laid.positions.items()
        if model.kind_of(cid) != "actor"
    }
    out |= {cid: (int(x), int(y)) for cid, (x, y) in pos.items()}
    return replace(
        laid,
        positions={c.id: out[c.id] for c in model.components if c.id in out},
        regions={rid: _moved(box, dx, dy) for rid, box in laid.regions.items()},
        containers={
            cid: (m, m, w, h) if cid == holder.id else _moved(box, dx, dy)
            for cid, box in laid.containers.items()
        },
        canvas=(m + w + m, m + h + m),
    )


def _moved(box: Box, dx: float, dy: float) -> Box:
    x, y, w, h = box
    return (int(x + dx), int(y + dy), w, h)


def band_of(model: Model, cid: str) -> str:
    """Give the band of an actor from the drawn layout: the side of the frame that the
    actor is on. A map without a frame, or an actor on the frame, gives "inside"."""
    frame = frame_box(model)
    if frame is None:
        return "inside"
    x0, y0, fw, fh = frame
    x, y, w, h = _box(model, cid)
    tests = (
        ("top", y + h <= y0),
        ("bottom", y >= y0 + fh),
        ("left", x + w <= x0),
        ("right", x >= x0 + fw),
    )
    return next((name for name, found in tests if found), "inside")
