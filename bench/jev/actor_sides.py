"""A1: the lines of the System context layer with the actors at more than one side.

L2 found the cause of the labels that are hard to read: in the System context layer of the
map of this repository, 15 of the 34 vertical line parts are in one strip of 77 map units
at the right of the actor column. This script moves the actor cards in a copy of the model.
Then it uses the router and the label placement of the product. It changes no product code
and writes no file.

Variants:

- `base`: the model as it is. The 5 actors are in one column at the left.
- `wide`: as `base`, but the system and its cards are 80 map units more to the right. Thus
  the strip at the right of the actors is 80 units wider.
- `two`: each actor is at the left side or at the right side of the system, the side that
  is nearer to the mean center of the cards that it has a flow with.
- `four`: as `two`, but with the four sides.
- `hand`: added after the first run on 2026-11-16, with no acceptance value. The side of
  each actor is set by hand for this map: Agent left, Maintainer right, CI top, TypeSafe
  and OpenAI bottom. It shows the result when the actors are at four different sides.

In `two` and `four`, an actor has the position of that mean center along its side. Two
actors on one side have 30 units or more between them. The script does not do the search of
the placer for a better order of the regions. Thus a full implementation can give a better
result than `two` and `four`, and not a worse one.

For each variant, for the flows of the System context layer and for all flows:

- `strip`: the largest count of parallel line parts in a window of 80 map units. A vertical
  part counts in a window of x positions, and a horizontal part in a window of y positions.
  Parts on one line with a shared range count one time for each flow.
- `crossed`: the count of label boxes with the path of a different flow of the same set
  through them. The box is 1 unit smaller on each side.
- `collisions`, `refused`, `bends`, `length`: the values of `place.score` (all flows only).
- `canvas`: the width and the height of the map, and `zoom`: the smaller of 1440 / width
  and 790 / height. 790 is 900 less the approximate height of the header and the rows
  above the map. `zoom` is for a comparison of the variants only.

Acceptance values, written before the first run on 2026-11-16. They are for `two` and for
`four`, for the map of this repository:

1. System context: `strip` is 5 or less.
2. System context: `crossed` is 3 or less.
3. All flows: `crossed`, `collisions` and `refused` are not more than those of `base`.
4. `zoom` is 90 percent or more of the `zoom` of `base`.

The map of this repository is the only input. It is one map. The result does not show the
effect on other maps.

Run from the repository root:
    uv run python bench/jev/actor_sides.py
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

WINDOW = 80.0
GAP = 30.0
CARD_W, CARD_H = 150.0, 56.0
SIDE = 44.0  # the distance between the system box and an actor card
MARGIN = 16.0
STRIP, CROSSED, ZOOM = 5, 3, 0.9
HAND = {
    "Agent": "left",
    "Maintainer": "right",
    "CI": "top",
    "TypeSafe": "bottom",
    "OpenAI": "bottom",
}

Box = tuple[float, float, float, float]


def _load() -> tuple[Any, list[int]]:
    from systemap import canvas_data, config, facts_file, nest  # noqa: PLC0415

    cfg = config.load(ROOT)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not facts:
        raise SystemExit("The committed facts are necessary. Run: systemap refresh")
    tree = nest.load(cfg)
    data = canvas_data.build(cfg, tree, facts)["maps"][0]
    layer = next(lay for lay in data["layers"] if lay["id"] == "system")
    return tree.top.model, list(layer["e"])


def _shift(model: Any, dx: float, dy: float, keep: set[str]) -> Any:
    """Move each container, region and card by dx, dy. The cards in `keep` do not move."""
    return replace(
        model,
        containers=tuple(
            replace(c, box=(c.box[0] + dx, c.box[1] + dy, c.box[2], c.box[3]))
            for c in model.containers
        ),
        regions=tuple(
            replace(r, box=(r.box[0] + dx, r.box[1] + dy, r.box[2], r.box[3]))
            for r in model.regions
        ),
        components=tuple(
            c if c.id in keep else replace(c, x=c.x + dx, y=c.y + dy) for c in model.components
        ),
    )


def _spread(wants: list[tuple[str, float]], size: float) -> dict[str, float]:
    """Give each item a start position near its wanted center, with GAP between the items."""
    out: dict[str, float] = {}
    last = float("-inf")
    for cid, centre in sorted(wants, key=lambda w: w[1]):
        start = max(centre - size / 2, last + GAP)
        out[cid] = start
        last = start + size
    return out


def _sides(model: Any, four: bool, forced: dict[str, str] | None = None) -> Any:
    actors = [c for c in model.components if c.kind == "actor"]
    ids = {c.id for c in actors}
    centre = {c.id: (c.x + CARD_W / 2, c.y + CARD_H / 2) for c in model.components}
    system = next(c for c in model.containers if c.id != actors[0].container)
    x0, y0, w, h = system.box
    x1, y1 = x0 + w, y0 + h
    wants: dict[str, list[tuple[str, float]]] = {"left": [], "right": [], "top": [], "bottom": []}
    for a in actors:
        others = [f.dst if f.src == a.id else f.src for f in model.flows if a.id in (f.src, f.dst)]
        others = [o for o in others if o not in ids]
        bx = sum(centre[o][0] for o in others) / len(others)
        by = sum(centre[o][1] for o in others) / len(others)
        far = {"left": bx - x0, "right": x1 - bx}
        if four:
            far |= {"top": by - y0, "bottom": y1 - by}
        side = (forced or {}).get(a.id) or min(far, key=lambda s: far[s])
        wants[side].append((a.id, by if side in ("left", "right") else bx))
    top = CARD_H + SIDE if wants["top"] else 0.0
    moved = _shift(model, 0.0, top, ids)
    y0, y1 = y0 + top, y1 + top
    at: dict[str, tuple[float, float]] = {}
    for side, x in (("left", x0 - SIDE - CARD_W), ("right", x1 + SIDE)):
        shifted = [(cid, c + top) for cid, c in wants[side]]
        at |= {cid: (x, y) for cid, y in _spread(shifted, CARD_H).items()}
    for side, y in (("top", y0 - SIDE - CARD_H), ("bottom", y1 + SIDE)):
        at |= {cid: (x, y) for cid, x in _spread(wants[side], CARD_W).items()}
    comps = tuple(
        replace(c, x=round(at[c.id][0]), y=round(at[c.id][1])) if c.id in at else c
        for c in moved.components
    )
    right = max([x1] + [x + CARD_W for x, _y in at.values()]) + MARGIN
    low = max([y1] + [y + CARD_H for _x, y in at.values()]) + MARGIN
    keep = tuple(c for c in moved.containers if c.id == system.id)
    return replace(
        moved, components=comps, containers=keep, canvas=(round(right), round(low))
    ), wants


def _strip(routes: dict[int, Any], ids: list[int]) -> int:
    best = 0
    for axis in (0, 1):
        parts = []
        for i in ids:
            pts = routes[i].points
            for a, b in zip(pts, pts[1:], strict=False):
                if abs(a[axis] - b[axis]) < 1e-6 and abs(a[1 - axis] - b[1 - axis]) > 1:
                    parts.append(a[axis])
        parts.sort()
        for k, start in enumerate(parts):
            best = max(best, sum(1 for p in parts[k:] if p <= start + WINDOW))
    return best


def _crossed(routes: dict[int, Any], seats: dict[int, Any], ids: list[int]) -> int:
    count = 0
    for i in ids:
        x, y, w, h = seats[i].box
        bx0, by0, bx1, by1 = x + 1, y + 1, x + w - 1, y + h - 1
        hit = False
        for j in ids:
            if j == i or hit:
                continue
            pts = routes[j].points
            for a, b in zip(pts, pts[1:], strict=False):
                sx0, sx1 = min(a[0], b[0]), max(a[0], b[0])
                sy0, sy1 = min(a[1], b[1]), max(a[1], b[1])
                if sx0 <= bx1 and sx1 >= bx0 and sy0 <= by1 and sy1 >= by0:
                    hit = True
                    break
        count += hit
    return count


def measure(model: Any, layer: list[int]) -> dict[str, Any]:
    from systemap import place  # noqa: PLC0415
    from systemap.route import place_labels, route_all  # noqa: PLC0415
    from systemap.schematic_cards import LABEL_CHAR_W, geometry  # noqa: PLC0415

    geo = geometry(model)
    canvas = (float(model.canvas[0]), float(model.canvas[1]))
    edges = [(f.src, f.dst) for f in model.flows]
    routes = route_all(
        edges, geo.boxes, geo.actors, geo.blocks, geo.region_boxes, geo.region_of, canvas
    )
    widths = {i: len(model.flows[i].artifact) * LABEL_CHAR_W + 6 for i in routes}
    seats = place_labels(
        routes,
        widths,
        place.LABEL_H,
        geo.obstacles,
        canvas,
        cards=geo.boxes,
        region_of=geo.region_of,
    )
    score = place.score(model)
    everything = list(range(len(edges)))
    return {
        "strip": _strip(routes, layer),
        "crossed": _crossed(routes, seats, layer),
        "strip_all": _strip(routes, everything),
        "crossed_all": _crossed(routes, seats, everything),
        "collisions": score.collisions,
        "refused": score.refused,
        "bends": score.bends,
        "length": score.length,
        "canvas": canvas,
        "zoom": min(1440 / canvas[0], 790 / canvas[1]),
    }


def main() -> int:
    model, layer = _load()
    actors = {c.id for c in model.components if c.kind == "actor"}
    wide = _shift(model, WINDOW, 0.0, actors)
    wide = replace(wide, canvas=(model.canvas[0] + WINDOW, model.canvas[1]))
    wide = replace(
        wide,
        containers=tuple(
            c if c.id != "outside" else next(o for o in model.containers if o.id == "outside")
            for c in wide.containers
        ),
    )
    two, two_sides = _sides(model, four=False)
    four, four_sides = _sides(model, four=True)
    hand, _ = _sides(model, four=True, forced=HAND)
    rows = {
        name: measure(m, layer)
        for name, m in (
            ("base", model),
            ("wide", wide),
            ("two", two),
            ("four", four),
            ("hand", hand),
        )
    }
    print(f"System context: {len(layer)} flows. All: {len(model.flows)} flows.")
    for name, sides in (("two", two_sides), ("four", four_sides)):
        print(
            f"{name}: "
            + ", ".join(f"{s}: {' '.join(c for c, _ in v)}" for s, v in sides.items() if v)
        )
    print(
        "variant  strip crossed | strip crossed collisions refused bends length | canvas      zoom"
    )
    for name, r in rows.items():
        print(
            f"{name:8} {r['strip']:5} {r['crossed']:7} | {r['strip_all']:5} {r['crossed_all']:7} "
            f"{r['collisions']:10} {r['refused']:7} {r['bends']:5} {r['length']:6} | "
            f"{r['canvas'][0]:.0f} x {r['canvas'][1]:.0f} {r['zoom']:.3f}"
        )
    base = rows["base"]
    passed = True
    for name in ("two", "four"):
        r = rows[name]
        checks = (
            r["strip"] <= STRIP,
            r["crossed"] <= CROSSED,
            r["crossed_all"] <= base["crossed_all"]
            and r["collisions"] <= base["collisions"]
            and r["refused"] <= base["refused"],
            r["zoom"] >= ZOOM * base["zoom"],
        )
        print(
            f"{name}: "
            + ", ".join(
                f"acceptance {k + 1} {'PASS' if ok else 'FAIL'}" for k, ok in enumerate(checks)
            )
        )
        passed = passed and all(checks)
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
