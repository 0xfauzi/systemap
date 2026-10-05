"""The placement algorithm sets positions for components without positions.

Existing positions stay the same if all_cards is false. Pinned positions stay the same
in both modes. Without fixed positions, the algorithm sets region, container, and canvas
boxes. It selects a region order with the smallest routing score. With fixed positions,
it uses free slots inside the existing boxes.
"""

from __future__ import annotations

import ast
import itertools
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path

from systemap.model import CARD_H, CARD_W, Box, Model, Region
from systemap.route import place_labels, route_all
from systemap.schematic import (
    HEADER_LINES,
    LABEL_CHAR,
    LABEL_CHAR_W,
    LABEL_H,
    SUB_CHAR,
    geometry,
    wrap_all,
)

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


def _first_layout(model: Model) -> Placement:
    """This function sets regions in two-column container grids and containers from left to
    right.
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
    known = {b.id for b in model.containers}
    for cid in loose:
        if cid not in known:
            raise PlaceError(f"A component specifies an unknown container {cid}")
    regions_of: dict[str | None, list[Region]] = {}
    for r in model.regions:
        if r.container is not None and r.container not in known:
            raise PlaceError(f"region {r.id} specifies an unknown container {r.container}")
        regions_of.setdefault(r.container, []).append(r)

    region_boxes: dict[str, Box] = {}
    container_boxes: dict[str, Box] = {}
    slots: dict[str, list[_Slot]] = {}
    columns: dict[str, _Column] = {}
    pos: dict[str, tuple[int, int]] = {}

    def grid(regions: list[Region], x0: int, y0: int) -> tuple[int, int]:
        """This function sets regions on a two-column grid and gives the occupied width and
        height.
        """
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
    return Placement(pos, region_boxes, container_boxes, canvas, kept=(), fresh=True)


# ---- the region order: every order tried, the best routed --------------------------


def score(model: Model) -> Score:
    """This function calculates the routing cost with the page router and label-placement
    algorithm.
    """
    geo = geometry(model)
    edges = [(f.src, f.dst) for f in model.flows]
    canvas = (float(model.canvas[0]), float(model.canvas[1]))
    routes = route_all(
        edges, geo.boxes, geo.actors, geo.blocks, geo.region_boxes, geo.region_of, canvas
    )
    widths = {i: len(model.flows[i].artifact) * LABEL_CHAR_W + 6 for i in routes}
    seats = place_labels(
        routes,
        widths,
        LABEL_H,
        geo.obstacles,
        canvas,
        cards=geo.boxes,
        region_of=geo.region_of,
    )
    length = 0.0
    for route in routes.values():
        pts = route.points
        length += sum(
            abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(pts, pts[1:], strict=False)
        )
    return Score(
        collisions=sum(1 for seat in seats.values() if seat.cost > 0),
        refused=sum(1 for route in routes.values() if route.fallback),
        bends=sum(max(0, len(route.points) - 2) for route in routes.values()),
        length=int(round(length)),
    )


def _crosses(a: tuple[float, float], b: tuple[float, float], box: Box) -> bool:
    """This function finds whether segment a-b crosses a box with route clearance."""
    x, y, w, h = box
    x0, y0 = x - ROUTE_CLEAR, y - ROUTE_CLEAR
    x1, y1 = x + w + ROUTE_CLEAR, y + h + ROUTE_CLEAR
    if abs(a[1] - b[1]) < 1e-9:
        lo, hi = min(a[0], b[0]), max(a[0], b[0])
        return y0 < a[1] < y1 and lo < x1 and hi > x0
    lo, hi = min(a[1], b[1]), max(a[1], b[1])
    return x0 < a[0] < x1 and lo < y1 and hi > y0


def _clear(a: tuple[float, float], b: tuple[float, float], walls: list[Box]) -> bool:
    return not any(_crosses(a, b, wall) for wall in walls)


def estimate(model: Model) -> tuple[int, float]:
    """This function calculates minimum bend counts and path lengths from component boxes
    and port reach.
    """
    cards = {c.id: c.box for c in model.components}
    region_of = {c.id: c.region or "" for c in model.components}
    regions = {r.id: r.box for r in model.regions}
    bends = 0
    length = 0.0
    for f in model.flows:
        if f.src == f.dst or f.src not in cards or f.dst not in cards:
            continue
        a, b = cards[f.src], cards[f.dst]
        ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
        bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
        dx, dy = bx - ax, by - ay
        length += abs(dx) + abs(dy)
        allowed = {region_of[f.src], region_of[f.dst]}
        walls = [box for cid, box in cards.items() if cid not in (f.src, f.dst)]
        walls += [box for rid, box in regions.items() if rid not in allowed]
        # The side of a facing b, and of b facing a, as a port on each.
        a_side_x = a[0] + a[2] if dx > 0 else a[0]
        b_side_x = b[0] if dx > 0 else b[0] + b[2]
        a_side_y = a[1] + a[3] if dy > 0 else a[1]
        b_side_y = b[1] if dy > 0 else b[1] + b[3]
        if abs(dy) <= PORT_REACH_Y and abs(dx) > a[2]:
            bends += 0 if _clear((a_side_x, ay), (b_side_x, ay), walls) else 2
        elif abs(dx) <= PORT_REACH_X and abs(dy) > a[3]:
            bends += 0 if _clear((ax, a_side_y), (ax, b_side_y), walls) else 2
        elif (
            _clear((a_side_x, ay), (bx, ay), walls) and _clear((bx, ay), (bx, b_side_y), walls)
        ) or (_clear((ax, a_side_y), (ax, by), walls) and _clear((ax, by), (b_side_x, by), walls)):
            bends += 1
        else:
            bends += 2
    return bends, length


def _region_weights(model: Model) -> dict[tuple[str, str], int]:
    """This function counts flows for each region pair in either direction."""
    region_of = {c.id: c.region for c in model.components}
    out: dict[tuple[str, str], int] = {}
    for f in model.flows:
        a, b = region_of.get(f.src), region_of.get(f.dst)
        if a is None or b is None or a == b:
            continue
        out[(a, b)] = out.get((a, b), 0) + 1
        out[(b, a)] = out.get((b, a), 0) + 1
    return out


def _greedy(
    group: list[Region], weights: dict[tuple[str, str], int], ids: list[str]
) -> list[Region]:
    """This function selects region order by connection counts. Equal counts use the listed
    order.
    """
    total = {r.id: sum(w for (a, _b), w in weights.items() if a == r.id) for r in group}
    rank = {rid: k for k, rid in enumerate(ids)}
    left = list(group)
    out: list[Region] = []
    while left:
        if not out:
            pick = max(left, key=lambda r: (total[r.id], -rank[r.id]))
        else:
            pick = max(
                left,
                key=lambda r: (
                    sum(weights.get((r.id, o.id), 0) for o in out),
                    total[r.id],
                    -rank[r.id],
                ),
            )
        out.append(pick)
        left.remove(pick)
    return out


def _groups(model: Model) -> list[list[Region]]:
    """This function groups regions by container in model order, with uncontained regions
    first.
    """
    by: dict[str | None, list[Region]] = {}
    for r in model.regions:
        by.setdefault(r.container, []).append(r)
    return list(by.values())


def _orders(model: Model) -> Iterator[tuple[Region, ...]]:
    """This function gives region-order combinations within each container, with the model
    order first.
    """
    perms = [list(itertools.permutations(group)) for group in _groups(model)]
    for combo in itertools.product(*perms):
        yield tuple(r for part in combo for r in part)


def _laid(model: Model, order: tuple[Region, ...]) -> Placement:
    """This function sets the layout with the selected region order."""
    laid = _first_layout(replace(model, regions=order))
    return replace(laid, regions={r.id: laid.regions[r.id] for r in model.regions})


def _search(model: Model) -> Placement:
    """This function selects the layout with the smallest measured routing score."""
    if len(model.regions) <= 1:
        laid = _laid(model, model.regions)
        placed = apply(model, laid)
        return replace(laid, order=tuple(r.id for r in model.regions), score=score(placed))

    # Every order laid out and estimated, keyed by its ids; the estimate
    # carries the index so a tie goes to the order tried first.
    seen: dict[tuple[str, ...], tuple[tuple[int, float, int], Placement]] = {}

    def try_order(order: tuple[Region, ...]) -> tuple[int, float, int]:
        ids = tuple(r.id for r in order)
        if ids in seen:
            return seen[ids][0]
        laid = _laid(model, order)
        bends, length = estimate(apply(model, laid))
        key = (bends, length, len(seen))
        seen[ids] = (key, laid)
        return key

    if len(model.regions) <= SEARCH_ALL:
        for order in _orders(model):
            try_order(order)
    else:
        try_order(model.regions)
        weights = _region_weights(model)
        listed_ids = [r.id for r in model.regions]
        groups = [_greedy(group, weights, listed_ids) for group in _groups(model)]
        current = tuple(r for group in groups for r in group)
        best = try_order(current)
        while True:
            improved: tuple[tuple[int, float, int], tuple[Region, ...]] | None = None
            for g, group in enumerate(groups):
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        swapped = [list(part) for part in groups]
                        swapped[g][i], swapped[g][j] = swapped[g][j], swapped[g][i]
                        order = tuple(r for part in swapped for r in part)
                        key = try_order(order)
                        if key[:2] < best[:2] and (improved is None or key < improved[0]):
                            improved = (key, order)
            if improved is None:
                break
            best, current = improved
            groups = [[r for r in current if r.container == group[0].container] for group in groups]

    listed = tuple(r.id for r in model.regions)
    ranked = sorted(seen, key=lambda ids: seen[ids][0])
    shortlist = ranked[:ROUTED]
    if listed not in shortlist:
        shortlist.append(listed)
    winner: tuple[Score, int, tuple[str, ...]] | None = None
    for ids in shortlist:
        key, laid = seen[ids]
        got = (score(apply(model, laid)), key[2], ids)
        if winner is None or got < winner:
            winner = got
    assert winner is not None
    best_score, _index, best_ids = winner
    return replace(
        seen[best_ids][1],
        order=best_ids,
        score=best_score,
        tried=len(seen),
        routed=len(shortlist),
    )


def _listed(model: Model) -> Placement:
    """This function sets the layout in the model region order for --keep-order."""
    laid = _laid(model, model.regions)
    return replace(laid, order=tuple(r.id for r in model.regions), score=score(apply(model, laid)))


def grid_order(model: Model) -> tuple[str, ...]:
    """This function reads region order from a positioned model, by container and grid row."""
    out: list[str] = []
    for group in _groups(model):
        out += [r.id for r in sorted(group, key=lambda r: (r.box[1], r.box[0]))]
    return tuple(out)


def order_line(placement: Placement) -> str:
    """This function formats the region order, routing score, and search counts."""
    assert placement.score is not None
    order = ", ".join(placement.order) if placement.order else "none"
    how = (
        f"{placement.tried} orders examined, {placement.routed} routed"
        if placement.tried
        else "as listed"
    )
    return f"region order: {order}; {placement.score.text()}; {how}"


# ---- filling the holes: some cards pinned ----------------------------------------


def _overlaps(slot: _Slot, h: int, box: Box, pad_x: int, pad_y: int) -> bool:
    bx, by, bw, bh = box
    return (
        slot.x < bx + bw + pad_x
        and bx - pad_x < slot.x + CARD_W
        and slot.y < by + bh + pad_y
        and by - pad_y < slot.y + h
    )


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
    if keep:
        return _fill_layout(model, set(keep), all_cards)
    laid = _listed(model) if keep_order else _search(model)
    return replace(laid, all_cards=all_cards)


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
    """This function calculates byte offsets for source lines to convert AST positions."""
    out = [0]
    for k, b in enumerate(source):
        if b == 0x0A:
            out.append(k + 1)
    return out


def edits(source: str, placement: Placement) -> list[_Edit]:
    """This function prepares source-byte edits for component positions and layout boxes.

    It replaces existing x and y arguments or inserts missing arguments in explicit
    Component calls.
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
    """This function formats missing x and y arguments in the existing call style."""
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
    """This function gives the model source with placement edits."""
    raw = bytearray(source.encode("utf-8"))
    for edit in sorted(edits(source, placement), key=lambda e: (e.start, e.end), reverse=True):
        raw[edit.start : edit.end] = edit.text
    return raw.decode("utf-8")


def write(path: Path, placement: Placement) -> str:
    """Write the placement into the model file and return the previous source.

    The caller reloads the model and uses unwritten to find positions that the edit did
    not change.
    """
    source = path.read_text(encoding="utf-8")
    path.write_text(written(source, placement), encoding="utf-8", newline="\n")
    return source


def unwritten(reloaded: Model, placement: Placement) -> list[str]:
    """This function finds calculated positions that the reloaded model does not contain."""
    return sorted(
        cid
        for cid, (x, y) in placement.positions.items()
        if (reloaded.component(cid).x, reloaded.component(cid).y) != (x, y)
    )
