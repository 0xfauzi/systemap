"""The placement algorithm sets positions for components without positions.

Existing positions stay the same if all_cards is false. Pinned positions stay the same
in both modes. Without fixed positions, the algorithm sets region, container, and canvas
boxes. It selects a region order with the smallest routing score. With fixed positions,
it uses free slots inside the existing boxes.

The modules `place_layout` (the fresh layout) and `place_order` (the region order) hold
the parts. This module fills free slots when positions stay, and gives the result lines.
`place_sides` has the rule that puts the actors of a nested map at the sides of its
frame. `compute(model, nested=True)` uses it. The commands do not use it: `sides_for`
gives False until the maintainer accepts the acceptance values of N3 (bench/jev/README.md).
"""

from __future__ import annotations

from dataclasses import replace

from systemap import place_sides
from systemap.config import Config
from systemap.model import CARD_H, CARD_W, KINDS, Model
from systemap.place_layout import (
    COL_GUTTER,
    REGION_PAD_TOP,
    ROUTED,
    ROW_GUTTER,
    SWEEPS,
    PlaceError,
    Placement,
    Score,
    _Column,
    _Slot,
    _sweep,
    apply,
    assign,
    container_top,
    container_width,
    region_shape,
    region_size,
    region_slots,
    sub_lines,
)
from systemap.place_order import (
    _greedy,
    _listed,
    _region_weights,
    _search,
    estimate,
    grid_order,
    order_line,
    score,
)
from systemap.schematic import LABEL_H, region_header

__all__ = [
    "EVERY_CARD_PINNED",
    "LABEL_H",
    "NOTHING_TO_PLACE",
    "ROUTED",
    "PlaceError",
    "Placement",
    "Score",
    "_greedy",
    "_region_weights",
    "apply",
    "assign",
    "compute",
    "container_top",
    "container_width",
    "estimate",
    "grid_order",
    "head",
    "kept_by",
    "lines",
    "order_line",
    "region_shape",
    "region_size",
    "region_slots",
    "score",
    "sub_lines",
]


# ---- filling the holes: some cards pinned ----------------------------------------


def _overlaps(
    slot: _Slot, h: int, box: tuple[float, float, float, float], pad_x: int, pad_y: int
) -> bool:
    bx, by, bw, bh = box
    return (
        slot.x < bx + bw + pad_x
        and bx - pad_x < slot.x + CARD_W
        and slot.y < by + bh + pad_y
        and by - pad_y < slot.y + h
    )


def _region_walls(model: Model) -> list[tuple[float, float, float, float]]:
    """This function gives each region box and region header box. A card in a container
    slot must not touch them.
    """
    return [*(r.box for r in model.regions), *(region_header(r)[0] for r in model.regions)]


def _covered(model: Model, home: str, nested: bool) -> list[tuple[float, float, float, float]]:
    """This function gives the box of the frame of a nested map when home is the container
    of its actors. With the actors at the sides, the frame is inside the box of the actors,
    and a new actor must not go into the frame. In each other case it gives no box, so the
    fill of a map that is not nested does not change.
    """
    found = place_sides.frame_of(model) if nested else None
    if found is None or found[1] != home:
        return []
    x, y, w, h = next(b.box for b in model.containers if b.id == home)
    return [
        b.box
        for b in model.containers
        if b.id != home
        and b.box[0] < x + w
        and x < b.box[0] + b.box[2]
        and b.box[1] < y + h
        and y < b.box[1] + b.box[3]
    ]


def _fill_layout(model: Model, keep: set[str], all_cards: bool, nested: bool) -> Placement:
    """This function assigns free slots inside existing boxes to components without
    retained positions.
    """
    regions = {r.id: r.box for r in model.regions}
    containers = {b.id: b.box for b in model.containers}
    pinned = [c for c in model.components if c.id in keep]
    unplaced = [c for c in model.components if c.id not in keep]
    pos: dict[str, tuple[int, int]] = {c.id: (c.x, c.y) for c in pinned}  # type: ignore[misc]
    free: dict[str, list[str]] = {}
    for c in unplaced:
        home = c.region if c.region is not None else c.container
        if not home:
            raise PlaceError(f"{c.id} has no region or container. Set a region or container.")
        if home not in regions and home not in containers:
            raise PlaceError(f"{c.id} specifies an unknown region or container {home}")
        free.setdefault(home, []).append(c.id)
    taken: list[tuple[float, float, float, float]] = [c.box for c in pinned]
    walls = _region_walls(model)
    slots: dict[str, list[_Slot]] = {}
    columns: dict[str, _Column] = {}
    for home, ids in free.items():
        if home in regions:
            box = regions[home]
            top = REGION_PAD_TOP
            blocked = taken
        else:
            box = containers[home]
            holder = next(b for b in model.containers if b.id == home)
            top = container_top(holder.sub, box[2])
            blocked = taken + walls + _covered(model, home, nested)
        tallest = max(CARD_H[model.kind_of(i)] for i in ids)
        room = [
            s
            for s in region_slots(box, top)
            if s.x + CARD_W <= box[0] + box[2]
            and s.y + tallest <= box[1] + box[3]
            and not any(_overlaps(s, tallest, t, COL_GUTTER - 1, ROW_GUTTER - 1) for t in blocked)
        ]
        if len(room) < len(ids):
            fix = (
                (
                    "remove pinned=True from a component, increase the box width or height, or "
                    "move a pinned component."
                )
                if all_cards
                else (
                    "Use systemap place --all to set unpinned component positions again, or "
                    "increase the box width or height."
                )
            )
            raise PlaceError(
                f"{home} has {len(room)} free slot{('s' if len(room) != 1 else '')} for "
                f"{len(ids)} component{('s' if len(ids) != 1 else '')} ({', '.join(ids)}): "
                f"{fix}"
            )
        slots[home] = room
        for k, cid in enumerate(ids):
            pos[cid] = (room[k].x, room[k].y)
    for _ in range(SWEEPS):
        pos = _sweep(model, pos, free, slots, columns)
    placed = {cid: pos[cid] for c in unplaced for cid in [c.id]}
    return Placement(
        placed,
        regions,
        containers,
        model.canvas,
        kept=tuple(c.id for c in pinned),
        all_cards=all_cards,
    )


def kept_by(model: Model, all_cards: bool) -> tuple[str, ...]:
    """This function selects existing positions to keep, or only pinned existing positions
    for all_cards.
    """
    return tuple(c.id for c in model.components if c.positioned and (c.pinned or not all_cards))


def _references(model: Model) -> None:
    """Refuse an unknown component kind and a flow to an unknown component. The placement
    cannot size or route them. A component without a position is not refused."""
    ids = model.ids
    for c in model.components:
        if c.kind not in KINDS:
            raise PlaceError(f"{c.id} has unknown kind {c.kind}. Use {', '.join(KINDS)}.")
    for f in model.flows:
        if f.src not in ids or f.dst not in ids:
            raise PlaceError(f"flow {f.src} -> {f.dst} has an unknown component. Correct the flow.")


def compute(
    model: Model, all_cards: bool = False, keep_order: bool = False, nested: bool | str = False
) -> Placement:
    """This function calculates a fresh layout if no position stays the same. otherwise, it
    fills free slots.

    The all_cards option keeps only positioned components with pinned=True. The default
    keeps all existing component positions. With nested, a fresh layout puts the actors
    of a nested map at the sides of its frame (`place_sides`): True gives the form of the
    commands (`place_sides.KEPT`), and "box" or "study" gives the form of that name. The
    commands give nested=True for each map that is not the top map only when `sides_for`
    is true.
    """
    keep = kept_by(model, all_cards)
    if len(keep) == len(model.components):
        return Placement(
            {},
            {r.id: r.box for r in model.regions},
            {b.id: b.box for b in model.containers},
            model.canvas,
            kept=keep,
            all_cards=all_cards,
        )
    _references(model)
    if keep:
        return _fill_layout(model, set(keep), all_cards, bool(nested))
    laid = _listed(model, nested) if keep_order else _search(model, nested)
    return replace(laid, all_cards=all_cards)


# The commands do not use the side rule. N1 and N2 failed their acceptance values, and N3
# changed two of the values after the results were known (bench/jev/README.md). Only the
# maintainer can accept the values of N3. Until then, this value stays False.
SIDES_IN_COMMANDS = False


def sides_for(cfg: Config) -> bool:
    """Tell if the commands put the actors of a nested map at the sides of its frame.

    The answer is False while SIDES_IN_COMMANDS is False. When the maintainer accepts the
    rule, only the atlas page uses it (`[render] page = "atlas"`). The canvas page and the
    linked page keep the column layout until the atlas page is the default, because their
    boundary flows on a phone need the actors at the left (N3 in bench/jev/README.md).
    """
    return SIDES_IN_COMMANDS and cfg.render_page == "atlas"


def head(placement: Placement) -> str:
    """This function formats new-position and retained-position counts."""
    n, m = len(placement.positions), len(placement.kept)
    what = "pinned" if placement.all_cards else "already positioned"
    kept = f"{m} kept ({what})" if m else "0 kept"
    return f"{n} component{('s' if n != 1 else '')} placed, {kept}"


NOTHING_TO_PLACE = (
    "nothing to place: All components have positions. Use systemap place --all to "
    "set positions again, except for components with pinned=True."
)
EVERY_CARD_PINNED = "nothing to place: All components are pinned."


def lines(placement: Placement) -> list[str]:
    """This function gives the position and box lines for systemap place --print."""
    first = f"place: {head(placement)}"
    if not placement.positions:
        if not placement.kept:
            return [first]
        return [f"{first}: {EVERY_CARD_PINNED if placement.all_cards else NOTHING_TO_PLACE}"]
    out = [first + (". The command set all boxes and the canvas." if placement.fresh else "")]
    if placement.fresh:
        out.append(f"  {order_line(placement)}")
    out += [f"  {cid}: x={x}, y={y}" for cid, (x, y) in placement.positions.items()]
    if placement.fresh:
        out += [f"  region {rid}: box={box}" for rid, box in placement.regions.items()]
        out += [f"  container {cid}: box={box}" for cid, box in placement.containers.items()]
        out.append(f"  canvas: {placement.canvas}")
    return out
