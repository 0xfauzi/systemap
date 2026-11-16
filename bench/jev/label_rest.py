"""A2: fewer lines and fewer labels at rest, for the labels that are hard to read.

L2 and A1 found that a line of a different flow goes through most flow labels, and that a
different position of the labels or of the actors does not remove the fault. This script
measures two other changes, alone and together. It changes no product code and writes no
file. It uses the router and the label placement of the product.

The changes:

- `pairs`: one line for each pair of cards that has one flow or more, in the two
  directions. The label of the line is the list of the different artifacts of its flows,
  with ", " between them. The script calculates the position of the label with the full
  list, also for a layer that shows only a part of the flows.
- `rest`: a label shows at rest only when the path of no different line of the same set
  goes through its box, and when its position has no collision. The other labels show when
  the reader points at the line or selects it. The script counts the labels that show at
  rest (`shown`).
- `near`: a different order of the candidate positions of a label (trial 2 of L2): a
  position without a collision first, then a position on its line or adjacent to it, then
  fewer other lines through the box, then the longest segment. The script puts this order
  in a subclass of `Seating`. The product class does not change.
- `wide`: the system and its cards are 80 map units more to the right (A1).

For each variant, for the lines of the System context layer and for all lines:

- `lines`: the count of lines, which is also the count of labels.
- `shown`: the count of labels that show at rest with the rule of `rest`.
- `strip`: as in A1.
- `collisions`: the count of labels with a position that has a collision (all lines only).

Acceptance values, written before the first run on 2026-11-16, for the System context
layer of the map of this repository. A1 gave 13 of 17 labels with a path through them for
the product as it is. Thus the first row is known to have 4 labels that show.

1. A variant is a candidate when 70 percent or more of its labels show at rest in the
   System context layer, and when its `collisions` are not more than those of the product
   as it is.
2. A variant with `pairs` must also have 12 lines or fewer in the System context layer.
3. If no variant is a candidate, the result is FAIL.

The other layers have no acceptance value. The map of this repository is the only input.

Run from the repository root:
    uv run python bench/jev/label_rest.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import actor_sides as a1  # noqa: E402

SHARE = 0.7
LINES = 12
APART = 6.0


def _near_seating() -> Any:
    """Give a subclass of the product `Seating` with the order of trial 2 of L2."""
    from systemap.seat_grid import Placed, SeatGrid, Seating  # noqa: PLC0415

    class Near(Seating):  # type: ignore[misc]
        paths: dict[int, list[tuple[float, float]]] = {}

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.wires = SeatGrid()
            self.wire_of: list[tuple[int, tuple[float, float, float, float]]] = []
            self.own: dict[int, list[tuple[float, float, float, float]]] = {}
            self.memo: dict[tuple[int, int], tuple[bool, int]] = {}
            for k, points in Near.paths.items():
                for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
                    box = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
                    self.wires.put(len(self.wire_of), box)
                    self.wire_of.append((k, box))
                    self.own.setdefault(k, []).append(box)

        def facts(self, k: int, n: int) -> tuple[bool, int]:
            key = (k, n)
            if key not in self.memo:
                x, y, w, h = self.cands[k][n][2]
                apart = True
                for sx, sy, sw, sh in self.own.get(k, []):
                    dx = max(0.0, x - (sx + sw), sx - (x + w))
                    dy = max(0.0, y - (sy + sh), sy - (y + h))
                    if dx + dy <= APART:
                        apart = False
                        break
                x0, y0, x1, y1 = x + 1, y + 1, x + w - 1, y + h - 1
                owners = set()
                for i in self.wires.near((x0, y0, x1 - x0, y1 - y0)):
                    j, (sx, sy, sw, sh) = self.wire_of[i]
                    if j != k and sx <= x1 and sx + sw >= x0 and sy <= y1 and sy + sh >= y0:
                        owners.add(j)
                self.memo[key] = (apart, len(owners))
            return self.memo[key]

        def seat(self, k: int) -> Any:
            best, best_rank = None, None
            for n, (seg, on_longest, box) in enumerate(self.cands[k]):
                cost = self.fixed(k, n) + self.soft(box, k)
                apart, through = self.facts(k, n)
                rank = (cost > 0, apart, through, not on_longest, cost)
                if best_rank is None or rank < best_rank:
                    best = Placed(box=box, segment=seg, on_longest=on_longest, cost=cost)
                    best_rank = rank
                if cost == 0 and on_longest and through == 0:
                    break
            return best

    return Near


def _lines(
    model: Any, layer: list[int], pairs: bool
) -> tuple[list[tuple[str, str]], list[str], list[int]]:
    """Give the edges, the label of each edge, and the edges of the layer."""
    if not pairs:
        return [(f.src, f.dst) for f in model.flows], [f.artifact for f in model.flows], layer
    edges: list[tuple[str, str]] = []
    texts: list[list[str]] = []
    index: dict[frozenset[str], int] = {}
    in_layer: set[int] = set()
    for i, f in enumerate(model.flows):
        key = frozenset((f.src, f.dst))
        if key not in index:
            index[key] = len(edges)
            edges.append((f.src, f.dst))
            texts.append([])
        k = index[key]
        if f.artifact not in texts[k]:
            texts[k].append(f.artifact)
        if i in layer:
            in_layer.add(k)
    return edges, [", ".join(t) for t in texts], sorted(in_layer)


def measure(model: Any, layer: list[int], pairs: bool, near: bool) -> dict[str, Any]:
    from systemap import place, route  # noqa: PLC0415
    from systemap.schematic_cards import LABEL_CHAR_W, geometry  # noqa: PLC0415

    geo = geometry(model)
    canvas = (float(model.canvas[0]), float(model.canvas[1]))
    edges, texts, ids = _lines(model, layer, pairs)
    routes = route.route_all(
        edges, geo.boxes, geo.actors, geo.blocks, geo.region_boxes, geo.region_of, canvas
    )
    widths = {i: len(texts[i]) * LABEL_CHAR_W + 6 for i in routes}
    product = route.Seating
    if near:
        cls = _near_seating()
        cls.paths = {k: routes[k].points for k in routes}
        route.Seating = cls
    try:
        seats = route.place_labels(
            routes,
            widths,
            place.LABEL_H,
            geo.obstacles,
            canvas,
            cards=geo.boxes,
            region_of=geo.region_of,
        )
    finally:
        route.Seating = product
    everything = sorted(routes)

    def _one(i: int, which: list[int]) -> bool:
        x, y, w, h = seats[i].box
        for j in which:
            if j == i:
                continue
            pts = routes[j].points
            for a, b in zip(pts, pts[1:], strict=False):
                if (
                    min(a[0], b[0]) <= x + w - 1
                    and max(a[0], b[0]) >= x + 1
                    and min(a[1], b[1]) <= y + h - 1
                    and max(a[1], b[1]) >= y + 1
                ):
                    return True
        return False

    def rest(which: list[int]) -> int:
        return sum(1 for i in which if seats[i].cost == 0 and not _one(i, which))

    return {
        "lines": len(ids),
        "shown": rest(ids),
        "strip": a1._strip(routes, ids),
        "lines_all": len(everything),
        "shown_all": rest(everything),
        "collisions": sum(1 for s in seats.values() if s.cost > 0),
        "longest": max(len(texts[i]) for i in ids),
    }


def main() -> int:
    model, layer = a1._load()
    actors = {c.id for c in model.components if c.kind == "actor"}
    wide = a1._shift(model, a1.WINDOW, 0.0, actors)
    outside = {c.id: c for c in model.containers}
    wide = replace(
        wide,
        canvas=(model.canvas[0] + a1.WINDOW, model.canvas[1]),
        containers=tuple(outside[c.id] if c.id == "outside" else c for c in wide.containers),
    )
    rows = []
    for name, m in (("", model), ("wide", wide)):
        for pairs in (False, True):
            for near in (False, True):
                label = " + ".join(
                    p for p in (name, "pairs" if pairs else "", "near" if near else "") if p
                )
                rows.append((label or "product", pairs, measure(m, layer, pairs, near)))
    base = rows[0][2]
    print(
        "variant               lines shown share strip | lines shown share collisions | longest label"
    )
    found = []
    for label, pairs, r in rows:
        share = r["shown"] / r["lines"]
        ok = (
            share >= SHARE
            and r["collisions"] <= base["collisions"]
            and (not pairs or r["lines"] <= LINES)
        )
        if ok:
            found.append(label)
        print(
            f"{label:21} {r['lines']:5} {r['shown']:5} {share:5.0%} {r['strip']:5} | {r['lines_all']:5} "
            f"{r['shown_all']:5} {r['shown_all'] / r['lines_all']:5.0%} {r['collisions']:10} | {r['longest']:4} characters"
            f"   {'candidate' if ok else ''}"
        )
    print("candidates:", ", ".join(found) or "none")
    print("RESULT:", "PASS" if found else "FAIL")
    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
