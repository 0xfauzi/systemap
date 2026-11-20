"""The fresh layout of the placer: the sizes of the boxes, the slots, and the sweeps.

`_first_layout` sets the regions in grids of two columns inside their containers, and
the containers from left to right. The barycentre sweeps then move each card near the
cards that it has flows with. `apply` writes a placement into a model.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from systemap.model import CARD_H, CARD_W, Box, Container, Model, Region
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
# Up to this many regions every order is tried; past it, greedy and swaps.
SEARCH_ALL = 6
# How many of the best-estimated orders the real router scores. Twelve
# holds the router's best order on the 144-module fixture (rank 2 by the
# estimate) and an order with the fewest bends on this repository's own
# map (rank 12), at about two seconds; measured in tests/test_place.py.
ROUTED = 12
# The straight run a port can reach: half the spread of the ports on a
# side (route.PORT_DX, route.PORT_DY), and the clearance a route keeps.
PORT_REACH_X = 50.0
PORT_REACH_Y = 16.0
ROUTE_CLEAR = 4.0


class PlaceError(Exception):
    """The program cannot calculate or write the placement. The message gives the necessary
    action.
    """


@dataclass(frozen=True, order=True)
class Score:
    """This record ranks routing costs by label collisions, unrelated-region crossings,
    bends, and path length.
    """

    collisions: int
    refused: int
    bends: int
    length: int

    def text(self) -> str:
        """This method formats label collisions, rejected routes, bends, and path length."""
        parts: list[str] = []
        if self.collisions:
            parts.append(f"{self.collisions} label collision{'s' if self.collisions != 1 else ''}")
        if self.refused:
            parts.append(f"{self.refused} route{'s' if self.refused != 1 else ''} refused")
        parts.append(f"{self.bends} bend{'s' if self.bends != 1 else ''}")
        parts.append(f"{self.length:,} units")
        return ", ".join(parts)


@dataclass(frozen=True)
class Placement:
    """This record contains new component positions and retained component IDs.

    A fresh layout also contains region, container, and canvas boxes, region order, and
    routing scores.
    """

    positions: dict[str, tuple[int, int]]
    regions: dict[str, Box]
    containers: dict[str, Box]
    canvas: tuple[int, int]
    kept: tuple[str, ...] = ()
    fresh: bool = False
    all_cards: bool = False
    order: tuple[str, ...] = ()
    score: Score | None = None
    tried: int = 0
    routed: int = 0
    grid_columns: int = REGION_COLUMNS

    @property
    def placed(self) -> tuple[str, ...]:
        return tuple(self.positions)


@dataclass
class _Slot:
    """This record gives a component slot by its top-left coordinate."""

    x: int
    y: int


@dataclass
class _Column:
    """This record groups components in a container column without a region."""

    x: int
    top: int
    ids: list[str] = field(default_factory=list)


def _ceil(value: float) -> int:
    return int(math.ceil(value - 1e-9))


def region_slots(box: Box, top: int = REGION_PAD_TOP) -> list[_Slot]:
    """This function gives slots in row-major order with 190-unit column spacing and
    92-unit row spacing.
    """
    x, y, w, h = box
    cols = max(1, (w - 2 * REGION_PAD_LEFT + COL_GUTTER) // COL_PITCH)
    rows = max(1, (h - top + ROW_GUTTER) // ROW_PITCH)
    return [
        _Slot(x + REGION_PAD_LEFT + c * COL_PITCH, y + top + r * ROW_PITCH)
        for r in range(rows)
        for c in range(cols)
    ]


def region_shape(n: int) -> tuple[int, int]:
    """This function selects the column and row counts for n components, with a maximum of
    three rows.
    """
    cols = max(1, _ceil(n / ROWS_DEEP))
    rows = max(1, _ceil(n / cols))
    return cols, rows


def region_size(n: int, label: str) -> tuple[int, int]:
    """This function calculates a region box from component count and label width."""
    cols, rows = region_shape(n)
    w = max(cols * COL_PITCH, _ceil(REGION_LABEL_LEAD + len(label) * LABEL_CHAR))
    h = REGION_PAD_TOP + rows * ROW_PITCH - ROW_GUTTER + REGION_PAD_BOTTOM
    return w, h


def sub_lines(sub: str, w: int) -> int:
    """This function calculates the wrapped container subheading line count at width w."""
    if not sub:
        return 0
    chars = max(12, int((w - 26) / SUB_CHAR))
    return len(wrap_all(sub, chars))


def container_width(label: str, sub: str, inner: int) -> int:
    """This function calculates the width for container contents, title, and a two-line
    subheading.
    """
    w = max(inner + 2 * CONTAINER_PAD, _ceil(CONTAINER_LABEL_LEAD + len(label) * LABEL_CHAR))
    while sub and sub_lines(sub, w) > HEADER_LINES:
        w += 10
    return w


def container_top(sub: str, w: int) -> int:
    """This function calculates the content start below the container title and subheading."""
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


def _exchange(seats: list[str | None], cost: Callable[[int, str | None], float]) -> bool:
    """This function exchanges two seats when the exchange decreases the total cost, for
    each pair in order. It gives True when it made an exchange.
    """
    improved = False
    for a, b in itertools.combinations(range(len(seats)), 2):
        before = cost(a, seats[a]) + cost(b, seats[b])
        after = cost(a, seats[b]) + cost(b, seats[a])
        if after < before - 1e-9:
            seats[a], seats[b] = seats[b], seats[a]
            improved = True
    return improved


def assign(
    ids: list[str],
    slots: list[_Slot],
    bary: dict[str, tuple[float, float] | None],
    heights: dict[str, int],
) -> dict[str, tuple[int, int]]:
    """This function assigns components to slots to decrease the total distance from their
    barycenters.

    The initial order uses barycenters. components without one occur last in the
    supplied order. Pair exchanges decrease the total distance until no exchange
    decreases the distance.
    """
    if len(ids) > len(slots):
        raise ValueError("There are more components than slots.")
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
        if not _exchange(seats, cost):
            break
    return {cid: (slots[k].x, slots[k].y) for k, cid in enumerate(seats) if cid is not None}


def _stack(
    ids: list[str],
    column: _Column,
    bary: dict[str, tuple[float, float] | None],
    heights: dict[str, int],
    pos: dict[str, tuple[int, int]],
) -> dict[str, tuple[int, int]]:
    """This function sets container-column positions near connected components with a
    minimum spacing of 92 units.
    """

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
    """This function assigns free components again from the barycenters of the existing
    positions.
    """
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


def _by_home(model: Model) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """This function groups the cards by region, and the cards with no region by
    container. It refuses an unknown region and a card with no home.
    """
    by_region: dict[str, list[str]] = {r.id: [] for r in model.regions}
    loose: dict[str, list[str]] = {}
    for c in model.components:
        if c.region is not None:
            if c.region not in by_region:
                raise PlaceError(f"{c.id} specifies an unknown region {c.region}")
            by_region[c.region].append(c.id)
        elif c.container:
            loose.setdefault(c.container, []).append(c.id)
        else:
            raise PlaceError(f"{c.id} has no region or container. Set a region or container.")
    return by_region, loose


def _homes(
    model: Model,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str | None, list[Region]]]:
    """This function groups the cards by region and by container, and the regions by
    container. It refuses an unknown region or container and a card with no home.
    """
    by_region, loose = _by_home(model)
    known = {b.id for b in model.containers}
    for cid in loose:
        if cid not in known:
            raise PlaceError(f"A component specifies an unknown container {cid}")
    regions_of: dict[str | None, list[Region]] = {}
    for r in model.regions:
        if r.container is not None and r.container not in known:
            raise PlaceError(f"region {r.id} specifies an unknown container {r.container}")
        regions_of.setdefault(r.container, []).append(r)
    return by_region, loose, regions_of


@dataclass
class _Laying:
    """This record holds the boxes, slots, columns and positions of a fresh layout while
    the layout grows.
    """

    by_region: dict[str, list[str]]
    grid_columns: int = REGION_COLUMNS
    region_boxes: dict[str, Box] = field(default_factory=dict)
    container_boxes: dict[str, Box] = field(default_factory=dict)
    slots: dict[str, list[_Slot]] = field(default_factory=dict)
    columns: dict[str, _Column] = field(default_factory=dict)
    pos: dict[str, tuple[int, int]] = field(default_factory=dict)

    def grid(self, regions: list[Region], x0: int, y0: int) -> tuple[int, int]:
        """This method sets regions on a grid of `grid_columns` columns and gives the occupied
        width and height.
        """
        sizes = {r.id: region_size(len(self.by_region[r.id]), r.label) for r in regions}
        n = self.grid_columns
        cols = [regions[k::n] for k in range(n)]
        col_w = [max((sizes[r.id][0] for r in col), default=0) for col in cols]
        rows = [regions[k : k + n] for k in range(0, len(regions), n)]
        y = y0
        for row in rows:
            row_h = max(sizes[r.id][1] for r in row)
            x = x0
            for k, r in enumerate(row):
                w, h = sizes[r.id]
                self.region_boxes[r.id] = (x, y, w, h)
                self.slots[r.id] = region_slots(self.region_boxes[r.id])
                x += col_w[k] + REGION_GAP_X
            y += row_h + REGION_GAP_Y
        used = [w for w in col_w if w]
        width = sum(used) + REGION_GAP_X * (len(used) - 1) if used else 0
        height = y - y0 - REGION_GAP_Y if rows else 0
        return width, height

    def container(self, box: Container, regions: list[Region], ids: list[str], x: int) -> int:
        """This method sets one container at x with its grid of regions and its column of
        cards. It gives the height of the container.
        """
        sizes = [region_size(len(self.by_region[r.id]), r.label) for r in regions]
        n = self.grid_columns
        cols = [sizes[k::n] for k in range(n)]
        col_w = [max((s[0] for s in col), default=0) for col in cols]
        used = [w for w in col_w if w]
        inner = sum(used) + REGION_GAP_X * (len(used) - 1) if used else 0
        if ids:
            inner += (REGION_GAP_X if inner else 0) + CARD_W
        w = container_width(box.label, box.sub, inner)
        top = container_top(box.sub, w)
        gw, gh = self.grid(regions, x + CONTAINER_PAD, CANVAS_MARGIN + top)
        h = top + gh
        if ids:
            column = _Column(
                x + CONTAINER_PAD + (gw + REGION_GAP_X if gw else 0), top + CANVAS_MARGIN, ids
            )
            self.columns[box.id] = column
            for k, cid in enumerate(ids):
                self.pos[cid] = (column.x, column.top + k * ROW_PITCH)
            h = max(h, top + len(ids) * ROW_PITCH - ROW_GUTTER)
        h += CONTAINER_PAD
        self.container_boxes[box.id] = (x, CANVAS_MARGIN, w, h)
        return h


def _first_layout(model: Model, columns: int = REGION_COLUMNS) -> Placement:
    """This function sets regions in container grids of `columns` columns (two by default)
    and containers from left to right.
    """
    by_region, loose, regions_of = _homes(model)
    lay = _Laying(by_region, columns)
    x = CANVAS_MARGIN
    bottom = CANVAS_MARGIN
    # Regions with no container form a grid straight on the canvas.
    if None in regions_of:
        w, h = lay.grid(regions_of[None], x, CANVAS_MARGIN)
        x += w + CONTAINER_GAP
        bottom = max(bottom, CANVAS_MARGIN + h)
    for box in model.containers:
        h = lay.container(box, regions_of.get(box.id, []), loose.get(box.id, []), x)
        x += lay.container_boxes[box.id][2] + CONTAINER_GAP
        bottom = max(bottom, CANVAS_MARGIN + h)
    for rid, ids in by_region.items():
        for k, cid in enumerate(ids):
            lay.pos[cid] = (lay.slots[rid][k].x, lay.slots[rid][k].y)

    free: dict[str, list[str]] = dict(by_region)
    free.update(loose)
    pos = lay.pos
    for _ in range(SWEEPS):
        pos = _sweep(model, pos, free, lay.slots, lay.columns)
    # A column may have grown past its container: the container follows.
    for cid, column in lay.columns.items():
        cx, cy, cw, ch = lay.container_boxes[cid]
        low = max(pos[i][1] + CARD_H[model.kind_of(i)] for i in column.ids)
        lay.container_boxes[cid] = (cx, cy, cw, max(ch, low + CONTAINER_PAD - cy))
        bottom = max(bottom, cy + lay.container_boxes[cid][3])
    canvas = (x - CONTAINER_GAP + CANVAS_MARGIN, bottom + CANVAS_MARGIN)
    return Placement(
        pos,
        lay.region_boxes,
        lay.container_boxes,
        canvas,
        kept=(),
        fresh=True,
        grid_columns=columns,
    )


def apply(model: Model, placement: Placement) -> Model:
    """This function adds the calculated positions and boxes to the model."""
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
