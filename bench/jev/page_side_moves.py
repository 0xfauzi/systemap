"""M1: the label collisions that the side moves of the rule remove on the nested map Page.

A review of the repair of stage 2 of the open faults found that acceptance 22 of
tests/test_place_sides.py fails on Page (Judgement is at the bottom, and its nearest side
is the right), and that no script recorded the label collision that the side move of
Judgement removes. This script gives that record. It has no acceptance value and changes
no rule.

The script reads the region order and the count of region columns of map/page.py, and
makes the layout of the side rule before the side moves (`place_sides.around` with the form
of the commands). For that layout and for the layout after the side moves
(`place_order._clear_sides`), it gives each label of the label placer of the canvas page
(`route.place_labels`, the placer of `place_order.score`) that has a cost more than 0: the
flow, the artifact, the width of the label, and what the box of the label touches. It also
gives the side of each neighbour before and after the moves.

Run from the repository root:
    uv run python bench/jev/page_side_moves.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from systemap import model_load, place, place_order, place_sides
from systemap.model import Model
from systemap.place_layout import Placement
from systemap.route import place_labels, route_all
from systemap.schematic import LABEL_CHAR_W, LABEL_H, geometry

ROOT = Path(__file__).resolve().parent.parent.parent


def collisions(model: Model) -> list[str]:
    """Give one line for each label with a cost more than 0, as `place_order.score` counts."""
    geo = geometry(model)
    edges = [(f.src, f.dst) for f in model.flows]
    canvas = (float(model.canvas[0]), float(model.canvas[1]))
    routes = route_all(
        edges, geo.boxes, geo.actors, geo.blocks, geo.region_boxes, geo.region_of, canvas
    )
    widths = {i: len(model.flows[i].artifact) * LABEL_CHAR_W + 6 for i in routes}
    names = {i: f"label of {model.flows[i].src} -> {model.flows[i].dst}" for i in routes}
    seats = place_labels(
        routes,
        widths,
        LABEL_H,
        geo.obstacles,
        canvas,
        names=names,
        cards=geo.boxes,
        region_of=geo.region_of,
    )
    out = []
    for i, seat in sorted(seats.items()):
        if seat.cost <= 0:
            continue
        f = model.flows[i]
        out.append(
            f'  {f.src} -> {f.dst}, "{f.artifact}", label {widths[i]:.0f} units wide, '
            f"cost {seat.cost:.2f}, touches {', '.join(seat.hits) or 'nothing named'}"
        )
    return out


def sides(model: Model) -> dict[str, str]:
    """Give the side of each neighbour."""
    found = place_sides.frame_of(model)
    assert found is not None
    fx, fy, fw, fh = next(b.box for b in model.containers if b.id == found[0])
    out = {}
    for c in model.components:
        if c.kind != "actor":
            continue
        x, y, w, h = c.box
        out[c.id] = next(
            s
            for s, yes in (
                ("left", x + w <= fx),
                ("right", x >= fx + fw),
                ("top", y + h <= fy),
                ("bottom", y >= fy + fh),
            )
            if yes
        )
    return out


def report(name: str, free: Model, laid: Placement) -> Model:
    model = place.apply(free, laid)
    found = collisions(model)
    print(f"{name}: canvas {model.canvas[0]} x {model.canvas[1]}, {len(found)} label collisions")
    for line in found:
        print(line)
    return model


def main() -> int:
    page = model_load.read(ROOT / "map/page.py", "map/page.py", ROOT)["MODEL"]
    assert isinstance(page, Model)
    ids = place_order.grid_order(page)
    columns = len({r.box[0] for r in page.regions})
    order = tuple(next(r for r in page.regions if r.id == i) for i in ids)
    free = replace(page, components=tuple(replace(c, x=None, y=None) for c in page.components))
    print(f"Page: region order {', '.join(ids)}, {columns} region columns")
    column = place_order._column(free, order, columns)
    plain = place_sides.around(free, column, place_sides.KEPT)
    plain = replace(
        plain, order=ids, grid_columns=columns, score=place.score(place.apply(free, plain))
    )
    before = report("Before the side moves", free, plain)
    after = report("After the side moves", free, place_order._clear_sides(free, plain, True))
    one, two = sides(before), sides(after)
    moved = [f"{a} {one[a]} -> {two[a]}" for a in sorted(one) if one[a] != two[a]]
    print("Side moves: " + (", ".join(moved) or "none"))
    same = all(after.component(c.id).box == c.box for c in page.components)
    print(f"The layout after the moves is the layout of map/page.py: {same}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
