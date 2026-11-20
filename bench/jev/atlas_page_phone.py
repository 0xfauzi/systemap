"""P6: the layout of the nested map Page at the fit on a wide screen and on a phone.

A review of stage 2 of the open faults found that the layout of N7 (four region columns,
1210 x 648) put the regions CANVAS PAGE and ATLAS PAGE and three neighbours outside the
phone view, and that no narrower or taller layout was measured against the rule "Phone" of
docs/design/atlas.md (a map opens at a zoom of 0.5 at its top left part). This script
measures one layout of Page or more, each from a model file, in the Chromium of
Playwright:

- At 1440 x 900: the zoom at the fit, and the width of the frame of the map on the screen
  as a part of the width of the screen (P3 of tests/test_atlas_page_layout_browser.py).
- At 390 x 844: the zoom at the fit, and for each region and each neighbour card the part
  of its width that is on the screen. The box of a region on the screen comes from the box
  of the frame of the map and the canvas of the model.

Inputs: `current` (map/page.py), `N7` (map/page.py of the commit 8ed658e) and `before`
(map/page.py of the commit 498efab, before stage 2 of the open faults).

Acceptance values, written on 2026-11-20 before the first run of this script. A scratch
probe in the same session had measured the current layout before this text (97 percent,
and 7 percent of the width of six neighbour cards at 390 x 844). Thus these values are not
blind for `current`:

1. At 1440 x 900, the zoom is 90 percent or more and the frame is 60 percent or more of
   the width of the screen (P3).
2. At 390 x 844, each region shows 50 percent or more of its width.
3. At 390 x 844, each neighbour card shows a part of its width more than 0 (the test Z4d of
   tests/test_atlas_inside_browser.py draws the line "on systemap" only on such a card).

The script also counts the neighbour cards that show 50 percent or more of their width.
That count has no acceptance value.

With --orders (added after the first run, on 2026-11-20): the script also measures each
region order of Page that has the smallest area before the side moves, after the side moves
of the rule (`place_order._clear_sides`). For each order it also gives the largest ratio of
the length of a line between a neighbour and a part to the Manhattan distance between its
two ends (P2, with the driver tests/atlas_layout.js). These rows have no acceptance value:
they show which of P2, P3 and the phone values one layout of this rule can meet.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_page_phone.py [--orders] [SCREENSHOT_DIR]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_canvas_browser import browser  # noqa: E402

from systemap import (  # noqa: E402
    atlas_data,
    atlas_page,
    canvas_page,
    config,
    facts_file,
    model_load,
    nest,
)
from systemap.model import Model  # noqa: E402

DRIVER = Path(__file__).resolve().parent / "atlas_page_phone.js"
INPUTS = {"current": None, "N7": "8ed658e", "before": "498efab"}


def _model(rev: str | None, tmp: Path) -> Model:
    path, root = ROOT / "map" / "page.py", ROOT
    if rev is not None:
        text = subprocess.run(
            ["git", "show", f"{rev}:map/page.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        path, root = tmp / f"page_{rev}.py", tmp
        path.write_text(text, encoding="utf-8")
    model = model_load.read(path, "map/page.py", root)["MODEL"]
    assert isinstance(model, Model)
    return model


def _drive(html: Path, w: int, h: int, shot: Path | None) -> dict[str, Any]:
    args = [browser(), str(DRIVER), str(html), "Page", str(w), str(h)]
    proc = subprocess.run(
        args + ([str(shot)] if shot else []), capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, proc.stderr
    got = dict(json.loads(proc.stdout))
    assert got["errors"] == [], got["errors"]
    return got


def _seen(x: float, w: float, width: float) -> float:
    return max(0.0, min(width, x + w) - max(0.0, x)) / w


def measure(model: Model, html: Path, shots: Path | None, name: str) -> list[bool]:
    """Print the values of one layout and give the three acceptance results."""
    wide = _drive(html, 1440, 900, shots and shots / f"{name}_1440.png")
    phone = _drive(html, 390, 844, shots and shots / f"{name}_390.png")
    part = wide["frame"][2] / wide["width"]
    print(f"\n{name}: canvas {model.canvas[0]} x {model.canvas[1]}")
    print(f"  1440 x 900: zoom {wide['zoom']}, frame {part:.3f} of the screen width")
    fx, _fy, fw, _fh = phone["frame"]
    scale = fw / model.canvas[0]
    regions = {r.id: _seen(fx + scale * r.box[0], scale * r.box[2], 390) for r in model.regions}
    actors = {c.id for c in model.components if c.kind == "actor"}
    cards = {c["id"]: _seen(c["b"][0], c["b"][2], 390) for c in phone["cards"] if c["id"] in actors}
    print(f"  390 x 844: zoom {phone['zoom']}")
    print("  regions: " + ", ".join(f"{k} {v:.2f}" for k, v in regions.items()))
    print("  neighbours: " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(cards.items())))
    half = sum(1 for v in cards.values() if v >= 0.5)
    print(f"  neighbours with 50 percent or more on the screen: {half} of {len(cards)}")
    return [
        int(wide["zoom"][:-1]) >= 90 and part >= 0.6,
        all(v >= 0.5 for v in regions.values()),
        all(v > 0 for v in cards.values()),
    ]


def _ratio(html: Path, flows: list[dict[str, Any]], kinds: dict[str, str]) -> float:
    """Give the largest ratio of P2 in the first layer tab."""
    proc = subprocess.run(
        [browser(), str(ROOT / "tests" / "atlas_layout.js"), str(html), "Page"],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    worst = 0.0
    for lane in json.loads(proc.stdout)["layers"][0]["lanes"]:
        f, q = flows[lane["f"]], lane["q"]
        if "actor" not in (kinds[f["s"]], kinds[f["t"]]):
            continue
        ends = abs(q[-1][0] - q[0][0]) + abs(q[-1][1] - q[0][1])
        length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(q, q[1:], strict=False))
        worst = max(worst, length / ends)
    return worst


def _orders(cfg: Any, tree: Any, facts: Any, tmp: Path) -> None:
    from systemap import place, place_order, place_sides  # noqa: PLC0415

    base = _model(None, tmp)
    free = replace(base, components=tuple(replace(c, x=None, y=None) for c in base.components))
    laid = {o: place_order._laid(free, o, True) for o in place_order._orders(free)}
    small = min(place_sides.area(v) for v in laid.values())
    for order, first in laid.items():
        if place_sides.area(first) != small:
            continue
        ids = tuple(r.id for r in order)
        got = place.score(place.apply(free, first))
        done = place_order._clear_sides(free, replace(first, order=ids, score=got), True)
        model = place.apply(free, done)
        maps = tuple(replace(m, model=model) if m.id == "Page" else m for m in tree.maps)
        data = atlas_data.build(cfg, replace(tree, maps=maps), facts)
        html = tmp / "order.html"
        html.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), "utf-8")
        page = next(m for m in data["maps"] if m["id"] == "Page")
        kinds = {c["id"]: c["k"] for c in page["cards"]}
        name = "order " + ",".join(ids)
        found = measure(model, html, None, name)
        print(f"  P2 largest ratio {_ratio(html, page['flows'], kinds):.2f}")
        print("  " + ", ".join(f"{k}: {'PASS' if ok else 'FAIL'}" for k, ok in enumerate(found, 1)))


def main(argv: list[str]) -> int:
    orders = "--orders" in argv
    argv = [a for a in argv if a != "--orders"]
    shots = Path(argv[0]) if argv else None
    cfg = config.load(ROOT)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    with tempfile.TemporaryDirectory() as tmp:
        for name, rev in INPUTS.items():
            model = _model(rev, Path(tmp))
            maps = tuple(replace(m, model=model) if m.id == "Page" else m for m in tree.maps)
            data = atlas_data.build(cfg, replace(tree, maps=maps), facts)
            html = Path(tmp) / f"{name}.html"
            html.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), "utf-8")
            found = measure(model, html, shots, name)
            for k, ok in enumerate(found, 1):
                print(f"  {k}: {'PASS' if ok else 'FAIL'}")
        if orders:
            _orders(cfg, tree, facts, Path(tmp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
