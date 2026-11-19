"""The placement algorithm sets positions for components without positions.

Existing positions stay the same if all_cards is false. Pinned positions stay the same
in both modes. Without fixed positions, the algorithm sets region, container, and canvas
boxes. It selects a region order with the smallest routing score. With fixed positions,
it uses free slots inside the existing boxes.

The modules `place_layout` (the fresh layout) and `place_order` (the region order) hold
the parts. This module fills free slots when positions stay, and gives the result lines.
"""

from __future__ import annotations

from dataclasses import replace

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


def _fill_layout(model: Model, keep: set[str], all_cards: bool) -> Placement:
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
            blocked = taken + walls
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


def compute(model: Model, all_cards: bool = False, keep_order: bool = False) -> Placement:
    """This function calculates a fresh layout if no position stays the same. otherwise, it
    fills free slots.

    The all_cards option keeps only positioned components with pinned=True. The default
    keeps all existing component positions.
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
        return _fill_layout(model, set(keep), all_cards)
    laid = _listed(model) if keep_order else _search(model)
    return replace(laid, all_cards=all_cards)


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
