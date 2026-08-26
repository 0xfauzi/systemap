"""A first placement for every card without one: what `systemap place` writes.

Hand placement was the cost driver of a first map and its scale limit:
the agent learned the corridor rule by trial, a third of its turns went on
layout, and past sixty cards the hand stopped working. This module places
the cards the model leaves without a position, deterministically and from
the standard library alone, and the check decides, as it always did.

The rules are the ones references/layout.md gives a person:

    regions ...... on a two-column grid inside their container, in the
                   order the model lists them, 48 units between the
                   columns and 36 between the rows: the corridors every
                   route between regions runs along
    cards ........ on the grid inside their region, columns 190 apart and
                   rows 92 apart, three deep before a region takes a
                   second column; a region's box follows its card count
                   (and widens for a label that would not fit)
    order ........ a few barycentre sweeps over the flows: each card is
                   drawn towards the mean position of the cards it talks
                   to, and the cards of a region are assigned to its
                   slots so the sum of those distances is smallest, so
                   the parts that talk sit together
    containers ... sized to hold their regions, laid left to right in
                   the order the model lists them; an actor, or any card
                   in a container and no region, stands in a column of
                   its own beside the regions, level with the cards it
                   talks to

A card with `x` and `y` is pinned: it is never moved, and while any card
is pinned the region and container boxes and the canvas are kept as
written and the unpinned cards take the free slots inside their own
boxes. A model with no pinned card is laid out whole: boxes and canvas
included. Either way the positions are written into the model module in
place, editing only the `x=` and `y=` values, the `box=` tuples and the
canvas, and the rest of the file is kept byte for byte. `--print` prints
them instead.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from systemap.model import CARD_H, CARD_W, Box, Model, Region
from systemap.schematic import HEADER_LINES, LABEL_CHAR, SUB_CHAR, wrap_all

COL_PITCH = 190
ROW_PITCH = 92
COL_GUTTER = COL_PITCH - CARD_W
ROW_GUTTER = ROW_PITCH - CARD_H["component"]
REGION_GAP_X = 48
REGION_GAP_Y = 36
# Inside a region: the cards start 20 in from the left edge and 40 below
# the top (under the region's header), and the box ends 16 below the last
# row. Inside a container: 20 in from the side, and below the header.
REGION_PAD_LEFT = 20
REGION_PAD_TOP = 40
REGION_PAD_BOTTOM = 16
CONTAINER_PAD = 20
CONTAINER_GAP = 24
CANVAS_MARGIN = 16
REGION_COLUMNS = 2
# Cards stack this deep before a region takes another column.
ROWS_DEEP = 3
SWEEPS = 4
# The room a header needs: a region label starts 31 in and a container
# label 13 in, and both keep 8 clear at the end; a container's sub wraps
# at the width the drawing gives it.
REGION_LABEL_LEAD = 31 + 8
CONTAINER_LABEL_LEAD = 13 + 8


class PlaceError(Exception):
    """The placement cannot be made or written; the message says what to do."""


@dataclass(frozen=True)
class Placement:
    """What `systemap place` computed.

    `positions` holds the placed cards only, by id; the pinned cards are
    listed in `pinned` and never appear here. `regions`, `containers` and
    `canvas` are every box and the canvas as they should now be written:
    recomputed when nothing was pinned, as the model has them otherwise.
    """

    positions: dict[str, tuple[int, int]]
    regions: dict[str, Box]
    containers: dict[str, Box]
    canvas: tuple[int, int]
    pinned: tuple[str, ...] = ()
    fresh: bool = False

    @property
    def placed(self) -> tuple[str, ...]:
        return tuple(self.positions)


@dataclass
class _Slot:
    """One place a card may take: its top-left corner."""

    x: int
    y: int


@dataclass
class _Column:
    """The cards of one container that sit in no region, stacked in a column."""

    x: int
    top: int
    ids: list[str] = field(default_factory=list)


def _ceil(value: float) -> int:
    return int(math.ceil(value - 1e-9))


def region_slots(box: Box, top: int = REGION_PAD_TOP) -> list[_Slot]:
    """The grid a box offers, row-major: columns 190 apart, rows 92 apart."""
    x, y, w, h = box
    cols = max(1, (w - 2 * REGION_PAD_LEFT + COL_GUTTER) // COL_PITCH)
    rows = max(1, (h - top + ROW_GUTTER) // ROW_PITCH)
    return [
        _Slot(x + REGION_PAD_LEFT + c * COL_PITCH, y + top + r * ROW_PITCH)
        for r in range(rows)
        for c in range(cols)
    ]


def region_shape(n: int) -> tuple[int, int]:
    """(columns, rows) for a region of n cards: three deep, then wider."""
    cols = max(1, _ceil(n / ROWS_DEEP))
    rows = max(1, _ceil(n / cols))
    return cols, rows


def region_size(n: int, label: str) -> tuple[int, int]:
    """The box a region of n cards needs, widened for a label that would not fit."""
    cols, rows = region_shape(n)
    w = max(cols * COL_PITCH, _ceil(REGION_LABEL_LEAD + len(label) * LABEL_CHAR))
    h = REGION_PAD_TOP + rows * ROW_PITCH - ROW_GUTTER + REGION_PAD_BOTTOM
    return w, h


def sub_lines(sub: str, w: int) -> int:
    """How many lines a container's sub takes at width w, as the drawing wraps it."""
    if not sub:
        return 0
    chars = max(12, int((w - 26) / SUB_CHAR))
    return len(wrap_all(sub, chars))


def container_width(label: str, sub: str, inner: int) -> int:
    """The width a container needs: its content, its label, and a sub that fits two lines."""
    w = max(inner + 2 * CONTAINER_PAD, _ceil(CONTAINER_LABEL_LEAD + len(label) * LABEL_CHAR))
    while sub and sub_lines(sub, w) > HEADER_LINES:
        w += 10
    return w


def container_top(sub: str, w: int) -> int:
    """Where a container's content starts: below its label and its sub lines."""
    return 52 + 12 * sub_lines(sub, w)


# ---- the barycentre sweeps ------------------------------------------------------


def _neighbours(model: Model) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c.id: [] for c in model.components}
    for f in model.flows:
        if f.src in out and f.dst in out and f.src != f.dst:
            out[f.src].append(f.dst)
            out[f.dst].append(f.src)
    return out


def _centre(cid: str, pos: dict[str, tuple[int, int]], model: Model) -> tuple[float, float]:
    x, y = pos[cid]
    return x + CARD_W / 2, y + CARD_H[model.kind_of(cid)] / 2


def _barycentre(
    cid: str, near: dict[str, list[str]], pos: dict[str, tuple[int, int]], model: Model
) -> tuple[float, float] | None:
    others = [o for o in near[cid] if o in pos]
    if not others:
        return None
    xs = [_centre(o, pos, model)[0] for o in others]
    ys = [_centre(o, pos, model)[1] for o in others]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def assign(
    ids: list[str],
    slots: list[_Slot],
    bary: dict[str, tuple[float, float] | None],
    heights: dict[str, int],
) -> dict[str, tuple[int, int]]:
    """Cards to slots so the sum of distances to their barycentres is smallest.

    The cards are first laid row-major in the order of their barycentres
    (the ones with none last, in the order given), then any two whose
    swap lowers the total are swapped until no swap does. Deterministic:
    the same input always gives the same assignment. An empty slot is a
    card with no barycentre, so which slots stay empty is decided by the
    same rule.
    """
    if len(ids) > len(slots):
        raise ValueError("more cards than slots")
    order = sorted(
        range(len(ids)),
        key=lambda i: (bary[ids[i]] is None, bary[ids[i]] or (0.0, 0.0), i),
    )
    seats: list[str | None] = [ids[i] for i in order] + [None] * (len(slots) - len(ids))

    def cost(k: int, cid: str | None) -> float:
        if cid is None or bary[cid] is None:
            return 0.0
        bx, by = bary[cid]  # type: ignore[misc]
        s = slots[k]
        return abs(s.x + CARD_W / 2 - bx) + abs(s.y + heights[cid] / 2 - by)

    for _round in range(len(slots) * len(slots) + 1):
        improved = False
        for a in range(len(seats)):
            for b in range(a + 1, len(seats)):
                before = cost(a, seats[a]) + cost(b, seats[b])
                after = cost(a, seats[b]) + cost(b, seats[a])
                if after < before - 1e-9:
                    seats[a], seats[b] = seats[b], seats[a]
                    improved = True
        if not improved:
            break
    return {cid: (slots[k].x, slots[k].y) for k, cid in enumerate(seats) if cid is not None}


def _stack(
    ids: list[str],
    column: _Column,
    bary: dict[str, tuple[float, float] | None],
    heights: dict[str, int],
    pos: dict[str, tuple[int, int]],
) -> dict[str, tuple[int, int]]:
    """A container column: each card level with what it talks to, 92 apart at least."""

    def wanted(cid: str) -> float:
        b = bary[cid]
        return pos[cid][1] if b is None else b[1] - heights[cid] / 2

    out: dict[str, tuple[int, int]] = {}
    y = column.top
    for cid in sorted(ids, key=lambda c: (wanted(c), ids.index(c))):
        y = max(y, int(round(wanted(cid))))
        out[cid] = (column.x, y)
        y += ROW_PITCH
    return out


def _sweep(
    model: Model,
    pos: dict[str, tuple[int, int]],
    free: dict[str, list[str]],
    slots: dict[str, list[_Slot]],
    columns: dict[str, _Column],
) -> dict[str, tuple[int, int]]:
    """Every free card of every region and column reassigned once, from the
    barycentres the current positions give."""
    near = _neighbours(model)
    heights = {c.id: CARD_H[c.kind] for c in model.components}
    for rid, ids in free.items():
        if not ids:
            continue
        bary = {cid: _barycentre(cid, near, pos, model) for cid in ids}
        if rid in columns:
            pos.update(_stack(ids, columns[rid], bary, heights, pos))
        else:
            pos.update(assign(ids, slots[rid], bary, heights))
    return pos


# ---- a fresh layout: nothing pinned -----------------------------------------------


def _first_layout(model: Model) -> Placement:
    """Regions on a two-column grid per container, containers left to right."""
    by_region: dict[str, list[str]] = {r.id: [] for r in model.regions}
    loose: dict[str, list[str]] = {}
    for c in model.components:
        if c.region is not None:
            if c.region not in by_region:
                raise PlaceError(f"{c.id} names unknown region {c.region}")
            by_region[c.region].append(c.id)
        elif c.container:
            loose.setdefault(c.container, []).append(c.id)
        else:
            raise PlaceError(f"{c.id} names no region or container; give it one")
    known = {b.id for b in model.containers}
    for cid in loose:
        if cid not in known:
            raise PlaceError(f"a card names unknown container {cid}")
    regions_of: dict[str | None, list[Region]] = {}
    for r in model.regions:
        if r.container is not None and r.container not in known:
            raise PlaceError(f"region {r.id} names unknown container {r.container}")
        regions_of.setdefault(r.container, []).append(r)

    region_boxes: dict[str, Box] = {}
    container_boxes: dict[str, Box] = {}
    slots: dict[str, list[_Slot]] = {}
    columns: dict[str, _Column] = {}
    pos: dict[str, tuple[int, int]] = {}

    def grid(regions: list[Region], x0: int, y0: int) -> tuple[int, int]:
        """Lay regions on the two-column grid from (x0, y0); (width, height) used."""
        sizes = {r.id: region_size(len(by_region[r.id]), r.label) for r in regions}
        cols = [regions[k::REGION_COLUMNS] for k in range(REGION_COLUMNS)]
        col_w = [max((sizes[r.id][0] for r in col), default=0) for col in cols]
        rows = [regions[k : k + REGION_COLUMNS] for k in range(0, len(regions), REGION_COLUMNS)]
        y = y0
        for row in rows:
            row_h = max(sizes[r.id][1] for r in row)
            x = x0
            for k, r in enumerate(row):
                w, h = sizes[r.id]
                region_boxes[r.id] = (x, y, w, h)
                slots[r.id] = region_slots(region_boxes[r.id])
                x += col_w[k] + REGION_GAP_X
            y += row_h + REGION_GAP_Y
        used = [w for w in col_w if w]
        width = sum(used) + REGION_GAP_X * (len(used) - 1) if used else 0
        height = y - y0 - REGION_GAP_Y if rows else 0
        return width, height

    x = CANVAS_MARGIN
    bottom = CANVAS_MARGIN
    # Regions with no container form a grid straight on the canvas.
    if None in regions_of:
        w, h = grid(regions_of[None], x, CANVAS_MARGIN)
        x += w + CONTAINER_GAP
        bottom = max(bottom, CANVAS_MARGIN + h)
    for box in model.containers:
        regions = regions_of.get(box.id, [])
        ids = loose.get(box.id, [])
        sizes = [region_size(len(by_region[r.id]), r.label) for r in regions]
        cols = [sizes[k::REGION_COLUMNS] for k in range(REGION_COLUMNS)]
        col_w = [max((s[0] for s in col), default=0) for col in cols]
        used = [w for w in col_w if w]
        inner = sum(used) + REGION_GAP_X * (len(used) - 1) if used else 0
        if ids:
            inner += (REGION_GAP_X if inner else 0) + CARD_W
        w = container_width(box.label, box.sub, inner)
        top = container_top(box.sub, w)
        gw, gh = grid(regions, x + CONTAINER_PAD, CANVAS_MARGIN + top)
        h = top + gh
        if ids:
            column = _Column(
                x + CONTAINER_PAD + (gw + REGION_GAP_X if gw else 0), top + CANVAS_MARGIN, ids
            )
            columns[box.id] = column
            for k, cid in enumerate(ids):
                pos[cid] = (column.x, column.top + k * ROW_PITCH)
            h = max(h, top + len(ids) * ROW_PITCH - ROW_GUTTER)
        h += CONTAINER_PAD
        container_boxes[box.id] = (x, CANVAS_MARGIN, w, h)
        x += w + CONTAINER_GAP
        bottom = max(bottom, CANVAS_MARGIN + h)
    for rid, ids in by_region.items():
        for k, cid in enumerate(ids):
            pos[cid] = (slots[rid][k].x, slots[rid][k].y)

    free: dict[str, list[str]] = dict(by_region)
    free.update(loose)
    for _ in range(SWEEPS):
        pos = _sweep(model, pos, free, slots, columns)
    # A column may have grown past its container: the container follows.
    for cid, column in columns.items():
        cx, cy, cw, ch = container_boxes[cid]
        low = max(pos[i][1] + CARD_H[model.kind_of(i)] for i in column.ids)
        container_boxes[cid] = (cx, cy, cw, max(ch, low + CONTAINER_PAD - cy))
        bottom = max(bottom, cy + container_boxes[cid][3])
    canvas = (x - CONTAINER_GAP + CANVAS_MARGIN, bottom + CANVAS_MARGIN)
    return Placement(pos, region_boxes, container_boxes, canvas, pinned=(), fresh=True)


# ---- filling the holes: some cards pinned ----------------------------------------


def _overlaps(slot: _Slot, h: int, box: Box, pad_x: int, pad_y: int) -> bool:
    bx, by, bw, bh = box
    return (
        slot.x < bx + bw + pad_x
        and bx - pad_x < slot.x + CARD_W
        and slot.y < by + bh + pad_y
        and by - pad_y < slot.y + h
    )


def _fill_layout(model: Model) -> Placement:
    """The free slots of the boxes as written, for the cards without a position."""
    regions = {r.id: r.box for r in model.regions}
    containers = {b.id: b.box for b in model.containers}
    pinned = [c for c in model.components if c.pinned]
    unplaced = [c for c in model.components if not c.pinned]
    pos: dict[str, tuple[int, int]] = {c.id: (c.x, c.y) for c in pinned}  # type: ignore[misc]
    free: dict[str, list[str]] = {}
    for c in unplaced:
        home = c.region if c.region is not None else c.container
        if not home:
            raise PlaceError(f"{c.id} names no region or container; give it one")
        if home not in regions and home not in containers:
            raise PlaceError(f"{c.id} names unknown region or container {home}")
        free.setdefault(home, []).append(c.id)
    taken = [c.box for c in pinned]
    slots: dict[str, list[_Slot]] = {}
    columns: dict[str, _Column] = {}
    for home, ids in free.items():
        if home in regions:
            box = regions[home]
            top = REGION_PAD_TOP
        else:
            box = containers[home]
            holder = next(b for b in model.containers if b.id == home)
            top = container_top(holder.sub, box[2])
        tallest = max(CARD_H[model.kind_of(i)] for i in ids)
        room = [
            s
            for s in region_slots(box, top)
            if s.x + CARD_W <= box[0] + box[2]
            and s.y + tallest <= box[1] + box[3]
            and not any(_overlaps(s, tallest, t, COL_GUTTER - 1, ROW_GUTTER - 1) for t in taken)
        ]
        if len(room) < len(ids):
            raise PlaceError(
                f"{home} has {len(room)} free slot{'s' if len(room) != 1 else ''} for "
                f"{len(ids)} card{'s' if len(ids) != 1 else ''} ({', '.join(ids)}): widen or "
                "heighten its box, move a pinned card, or strip every position and run "
                "place again"
            )
        slots[home] = room
        for k, cid in enumerate(ids):
            pos[cid] = (room[k].x, room[k].y)
    for _ in range(SWEEPS):
        pos = _sweep(model, pos, free, slots, columns)
    placed = {cid: pos[cid] for c in unplaced for cid in [c.id]}
    return Placement(placed, regions, containers, model.canvas, pinned=tuple(c.id for c in pinned))


def compute(model: Model) -> Placement:
    """The placement for a model: whole when nothing is pinned, the holes otherwise."""
    if all(c.pinned for c in model.components):
        return Placement(
            {},
            {r.id: r.box for r in model.regions},
            {b.id: b.box for b in model.containers},
            model.canvas,
            pinned=tuple(c.id for c in model.components),
        )
    if any(c.pinned for c in model.components):
        return _fill_layout(model)
    return _first_layout(model)


def apply(model: Model, placement: Placement) -> Model:
    """The model with the placement in it: every placed card positioned, the boxes set."""
    components = tuple(
        replace(c, x=placement.positions[c.id][0], y=placement.positions[c.id][1])
        if c.id in placement.positions
        else c
        for c in model.components
    )
    regions = tuple(replace(r, box=placement.regions.get(r.id, r.box)) for r in model.regions)
    containers = tuple(
        replace(b, box=placement.containers.get(b.id, b.box)) for b in model.containers
    )
    return replace(
        model,
        components=components,
        regions=regions,
        containers=containers,
        canvas=placement.canvas,
    )


def lines(placement: Placement) -> list[str]:
    """What `systemap place --print` prints: one line per placed card, box and the canvas."""
    n, m = len(placement.positions), len(placement.pinned)
    head = f"place: {n} card{'s' if n != 1 else ''} placed, {m} pinned"
    if not placement.positions:
        return [head + ": nothing to place" if m else head]
    out = [head + (", every box and the canvas laid out" if placement.fresh else "")]
    out += [f"  {cid}: x={x}, y={y}" for cid, (x, y) in placement.positions.items()]
    if placement.fresh:
        out += [f"  region {rid}: box={box}" for rid, box in placement.regions.items()]
        out += [f"  container {cid}: box={box}" for cid, box in placement.containers.items()]
        out.append(f"  canvas: {placement.canvas}")
    return out


# ---- writing the positions into the model module -----------------------------------


def _name_of(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _const_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _kw(call: ast.Call, name: str) -> ast.keyword | None:
    return next((k for k in call.keywords if k.arg == name), None)


def _id_of(call: ast.Call) -> str | None:
    kw = _kw(call, "id")
    return _const_str(kw.value if kw else (call.args[0] if call.args else None))


def _box_node(call: ast.Call) -> ast.expr | None:
    kw = _kw(call, "box")
    if kw is not None:
        return kw.value
    return call.args[2] if len(call.args) > 2 else None


# What the source positions are read from: an expression or a keyword.
_Located = ast.expr | ast.keyword


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    text: bytes


def _offsets(source: bytes) -> list[int]:
    """The byte offset of the start of every line, so an ast position becomes one."""
    out = [0]
    for k, b in enumerate(source):
        if b == 0x0A:
            out.append(k + 1)
    return out


def edits(source: str, placement: Placement) -> list[_Edit]:
    """The byte edits that write a placement into a model module's source.

    A placed card's `x=` and `y=` values are replaced where they are and
    inserted after its last argument where they are not, one per line in
    an exploded call and inline in a one-line call. On a whole layout
    every region's and container's `box=` tuple (or third positional
    argument) and the model's `canvas=` are replaced too. Nothing else is
    touched.
    """
    raw = source.encode("utf-8")
    starts = _offsets(raw)

    def at(line: int, col: int) -> int:
        return starts[line - 1] + col

    def span(node: _Located) -> tuple[int, int]:
        assert node.end_lineno is not None and node.end_col_offset is not None
        return at(node.lineno, node.col_offset), at(node.end_lineno, node.end_col_offset)

    out: list[_Edit] = []
    seen: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _name_of(node.func)
        if name == "Component":
            cid = _id_of(node)
            if cid is None or cid not in placement.positions or cid in seen:
                continue
            seen.add(cid)
            x, y = placement.positions[cid]
            missing: list[tuple[str, int]] = []
            for key, value in (("x", x), ("y", y)):
                kw = _kw(node, key)
                if kw is None:
                    missing.append((key, value))
                else:
                    a, b = span(kw.value)
                    out.append(_Edit(a, b, str(value).encode()))
            if missing:
                out.append(_insertion(raw, node, missing, span))
        elif name in ("Region", "Container") and placement.fresh:
            table = placement.regions if name == "Region" else placement.containers
            rid = _id_of(node)
            box = _box_node(node)
            if rid is None or rid not in table or box is None:
                continue
            a, b = span(box)
            out.append(_Edit(a, b, repr(tuple(table[rid])).encode()))
        elif name == "Model" and placement.fresh:
            kw = _kw(node, "canvas")
            if kw is not None:
                a, b = span(kw.value)
                out.append(_Edit(a, b, repr(tuple(placement.canvas)).encode()))
    return out


def _insertion(
    raw: bytes,
    call: ast.Call,
    missing: list[tuple[str, int]],
    span: Callable[[_Located], tuple[int, int]],
) -> _Edit:
    """`x=` and `y=` after the call's last argument, in the call's own style."""
    last = max(
        (*call.args, *(k.value for k in call.keywords)),
        key=lambda n: span(n)[1],
    )
    _a, end = span(last)
    _call_start, call_end = span(call)
    between = raw[end : call_end - 1]
    if b"\n" in between:
        line_start = raw.rfind(b"\n", 0, span(last)[0]) + 1
        indent = raw[line_start : span(last)[0]]
        indent = indent[: len(indent) - len(indent.lstrip())]
        # The last argument may be a keyword: its line's indent is the one.
        kw = next((k for k in call.keywords if k.value is last), None)
        if kw is not None:
            line_start = raw.rfind(b"\n", 0, span(kw)[0]) + 1
            indent = raw[line_start : span(kw)[0]]
        text = b"".join(b",\n" + indent + f"{k}={v}".encode() for k, v in missing)
        return _Edit(end, end, text)
    text = b"".join(f", {k}={v}".encode() for k, v in missing)
    return _Edit(end, end, text)


def written(source: str, placement: Placement) -> str:
    """The model module's source with the placement written into it."""
    raw = bytearray(source.encode("utf-8"))
    for edit in sorted(edits(source, placement), key=lambda e: (e.start, e.end), reverse=True):
        raw[edit.start : edit.end] = edit.text
    return raw.decode("utf-8")


def write(path: Path, placement: Placement) -> str:
    """Write the placement into the model module; return the source it replaced.

    The caller reloads the module and passes it to `unwritten`, which
    names any card the edit could not reach (built in a loop, an id that
    is not a literal), so the write is verified against what the file
    now says rather than trusted.
    """
    source = path.read_text(encoding="utf-8")
    path.write_text(written(source, placement), encoding="utf-8")
    return source


def unwritten(reloaded: Model, placement: Placement) -> list[str]:
    """The placed cards whose position the reloaded module does not carry."""
    return sorted(
        cid
        for cid, (x, y) in placement.positions.items()
        if (reloaded.component(cid).x, reloaded.component(cid).y) != (x, y)
    )
