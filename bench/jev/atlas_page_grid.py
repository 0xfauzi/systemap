"""P9: each layout of the nested map Page that the side rule can give, with 2, 3 and 4 region columns.

A review of the repair of stage 2 of the open faults found that the claim "no measured
layout of Page meets P2, P3, P4, acceptance 26 and the phone values together" (P8 in
bench/jev/README.md) had a gap: the records gave layouts with two region columns (N8, N9,
the 8 orders of P6) and four region columns (N7), but no layout with three region columns.
This script measures all of them: for each count of region columns in the frame (2, 3 and
4) and for each of the 24 region orders of Page, the fresh layout of the side rule
(`place_order._column` with that count, then `place_sides.around` with the form of the
commands, then the side moves `place_order._clear_sides`). When the side moves change the
layout, the script also measures the layout before the moves (row `no move`).

For each layout the script builds the atlas page of the map of this repository with that
layout of Page, and opens it in the Chromium of Playwright (bench/jev/atlas_page_phone.js at
1440 x 900 and at 390 x 844, tests/atlas_layout.js at 1440 x 900).

Acceptance values, written on 2026-11-20 before the first run of this script. They are the
values of the tests, with no change:

P1. In each layer tab at 1440 x 900, no label at rest is cut, and the lines of one
    neighbour with one artifact in one direction show one label or none
    (tests/test_atlas_page_layout_browser.py).
P2. Each line between a neighbour and a part, in each layer tab, has a length of 1.5 times
    the Manhattan distance between its two ends or less, and 1.5 times the Manhattan
    distance between the centres of its two cards or less (the same test).
P3. At 1440 x 900 the zoom at the fit is 90 percent or more, and the frame of the map is 60
    percent or more of the width of the screen (the same test).
P4. Each neighbour is at the side of the frame nearest to the mean centre of the parts that
    it has flows with (acceptance 22 of tests/test_place_sides.py, the same measure).
A26. The neighbours are at three sides of the frame or more, and no side has all of them
    (acceptance 26 of tests/test_atlas_browser.py, measured on the positions of the model).
Z4d. At 390 x 844, each neighbour card shows a part of its width more than 0 (the test
    `test_the_line_of_a_neighbour_is_readable_at_the_fit` of
    tests/test_atlas_inside_browser.py draws the line "on systemap" only on such a card).

The script gives each value for each row, and the count of rows that meet all six. The
claim of P8 is true for the side rule if that count is 0. This script changes no rule.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_page_grid.py [COLUMNS ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import atlas_page_phone as phone  # noqa: E402  (a neighbour script in bench/jev)

from systemap import (  # noqa: E402
    atlas_data,
    atlas_page,
    canvas_page,
    config,
    facts_file,
    nest,
    place,
    place_order,
    place_sides,
)
from systemap.model import Model  # noqa: E402

ROOT = phone.ROOT
LAYOUT = ROOT / "tests" / "atlas_layout.js"


def layouts(base: Model, columns: int) -> Iterator[tuple[str, place.Placement]]:
    """Give each layout of the rule for one count of region columns, and the layout before
    the side moves when the moves change it."""
    free = replace(base, components=tuple(replace(c, x=None, y=None) for c in base.components))
    for order in place_order._orders(free):
        ids = tuple(r.id for r in order)
        column = place_order._column(free, order, columns)
        plain = place_sides.around(free, column, place_sides.KEPT)
        got = place.score(place.apply(free, plain))
        plain = replace(plain, order=ids, score=got, grid_columns=columns)
        moved = place_order._clear_sides(free, plain, True)
        name = f"{columns} {','.join(ids)}"
        yield f"{name} rule", moved
        if moved.positions != plain.positions:
            yield f"{name} no move", plain


def nearest_fails(model: Model) -> list[str]:
    """Give the neighbours that are not at their nearest side (P4)."""
    found = place_sides.frame_of(model)
    assert found is not None
    fx, fy, fw, fh = next(b.box for b in model.containers if b.id == found[0])
    actors = {c.id for c in model.components if c.kind == "actor"}
    centre = {c.id: (c.box[0] + c.box[2] / 2, c.box[1] + c.box[3] / 2) for c in model.components}
    out = []
    for a in sorted(actors):
        parts = [f.dst if f.src == a else f.src for f in model.flows if a in (f.src, f.dst)]
        parts = [p for p in parts if p not in actors]
        if not parts:
            continue
        mx = sum(centre[p][0] for p in parts) / len(parts)
        my = sum(centre[p][1] for p in parts) / len(parts)
        far = {"left": mx - fx, "right": fx + fw - mx, "top": my - fy, "bottom": fy + fh - my}
        x, y, w, h = model.component(a).box
        side = next(
            s
            for s, yes in (
                ("left", x + w <= fx),
                ("right", x >= fx + fw),
                ("top", y + h <= fy),
                ("bottom", y >= fy + fh),
            )
            if yes
        )
        if far[side] > min(far.values()):
            out.append(a)
    return out


def sides_ok(model: Model) -> bool:
    """Give A26: three sides or more, and no side with all the neighbours."""
    parts = [c.box for c in model.components if c.kind != "actor"]
    x0, y0 = min(b[0] for b in parts), min(b[1] for b in parts)
    x1, y1 = max(b[0] + b[2] for b in parts), max(b[1] + b[3] for b in parts)
    sides = []
    for c in model.components:
        if c.kind != "actor":
            continue
        x, y, w, h = c.box
        sides.append(
            next(
                s
                for s, yes in (
                    ("left", x + w <= x0),
                    ("right", x >= x1),
                    ("top", y + h <= y0),
                    ("bottom", y >= y1),
                )
                if yes
            )
        )
    return len(set(sides)) >= 3 and max(sides.count(s) for s in set(sides)) < len(sides)


def lines_values(html: Path, page: dict[str, Any]) -> tuple[bool, float]:
    """Give P1 and the largest ratio of P2 over the two measures, in all layer tabs."""
    proc = subprocess.run(
        [phone.browser(), str(LAYOUT), str(html), "Page"],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    got = json.loads(proc.stdout)
    assert got["errors"] == [], got["errors"]
    flows, cards = page["flows"], {c["id"]: c for c in page["cards"]}
    full, worst = True, 0.0
    for layer in got["layers"]:
        keys: list[Any] = []
        for label in layer["labels"]:
            f = flows[label["f"]]
            full = full and label["s"] == f["a"] and not label["s"].endswith("...")
            if cards[f["s"]]["k"] == "actor":
                keys.append((">", f["s"], f["a"]))
            elif cards[f["t"]]["k"] == "actor":
                keys.append(("<", f["t"], f["a"]))
            else:
                keys.append(label["f"])
        full = full and len(keys) == len(set(keys))
        for lane in layer["lanes"]:
            f, q = flows[lane["f"]], lane["q"]
            if "actor" not in (cards[f["s"]]["k"], cards[f["t"]]["k"]):
                continue
            length = sum(
                abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(q, q[1:], strict=False)
            )
            ends = abs(q[-1][0] - q[0][0]) + abs(q[-1][1] - q[0][1])
            a, b = cards[f["s"]]["b"], cards[f["t"]]["b"]
            middle = abs(a[0] + a[2] / 2 - b[0] - b[2] / 2) + abs(
                a[1] + a[3] / 2 - b[1] - b[3] / 2
            )
            worst = max(worst, length / max(ends, 1e-9), length / max(middle, 1e-9))
    return full, worst


def measure(name: str, model: Model, html: Path, page: dict[str, Any], score: Any) -> bool:
    """Print one row and give True when the row meets all six values."""
    wide = phone._drive(html, 1440, 900, None)
    small = phone._drive(html, 390, 844, None)
    part = wide["frame"][2] / wide["width"]
    actors = {c.id for c in model.components if c.kind == "actor"}
    seen = {
        c["id"]: phone._seen(c["b"][0], c["b"][2], 390) for c in small["cards"] if c["id"] in actors
    }
    p1, ratio = lines_values(html, page)
    fails = nearest_fails(model)
    values = {
        "P1": p1,
        "P2": ratio <= 1.5,
        "P3": int(wide["zoom"][:-1]) >= 90 and part >= 0.6,
        "P4": not fails,
        "A26": sides_ok(model),
        "Z4d": all(v > 0 for v in seen.values()),
    }
    hidden = sorted(k for k, v in seen.items() if v <= 0)
    print(
        f"{name}: canvas {model.canvas[0]} x {model.canvas[1]}, collisions {score.collisions}, "
        f"refused {score.refused}, zoom {wide['zoom']}, frame {part:.3f}, P2 ratio {ratio:.2f}, "
        f"not nearest {fails or '-'}, outside at 390 {hidden or '-'}; "
        + ", ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in values.items()),
        flush=True,
    )
    return all(values.values())


def main(argv: list[str]) -> int:
    counts = [int(a) for a in argv] or [2, 3, 4]
    cfg = config.load(ROOT)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    theme = canvas_page.tree_theme(cfg, tree)
    base = next(m for m in tree.maps if m.id == "Page").model
    rows = good = 0
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "grid.html"
        for columns in counts:
            for name, laid in layouts(base, columns):
                free = replace(
                    base, components=tuple(replace(c, x=None, y=None) for c in base.components)
                )
                model = place.apply(free, laid)
                maps = tuple(replace(m, model=model) if m.id == "Page" else m for m in tree.maps)
                data = atlas_data.build(cfg, replace(tree, maps=maps), facts)
                html.write_text(atlas_page.build(theme, data), "utf-8")
                page = next(m for m in data["maps"] if m["id"] == "Page")
                rows += 1
                good += measure(name, model, html, page, laid.score)
    print(f"\nRows: {rows}. Rows that meet all six values: {good}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
