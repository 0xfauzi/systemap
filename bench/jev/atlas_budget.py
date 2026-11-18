"""B1: the performance budget of the atlas page against the canvas page (stage 1).

Acceptance values, written before the first run on 2026-11-18, from "The performance
budget" in docs/design/atlas.md. Each value compares the atlas page (`atlas_page.build`)
with the canvas page (`canvas_page.build`) of the same data, measured in the same run on
the same machine, at 4 times CPU slowdown (`Emulation.setCPUThrottlingRate`):

1. `first`: the time to the first complete frame (`systemapCanvas.ready`: the first frame
   is drawn and the input handlers are attached), from the start of the navigation. The
   atlas value is 1.5 times the canvas value or less. The absolute limit of the gate also
   applies: 1,500 ms or less.
2. `pan`: the 95th percentile of the frame intervals of the scenario `pan-fit` of
   bench/jev/canvas_frames.py (180 frames, a pan of 200 screen pixels to the left and the
   right at the fit, about 3 s). The atlas value is 1.25 times the canvas value or less,
   or 35 ms or less.
3. `dive`: the 95th percentile of the frame intervals of the scenario `dive` of
   bench/jev/canvas_frames.py: a zoom from the top fit into the deepest map below the first
   card that opens a map, and back out. A map with no nested map zooms into its middle
   card. The atlas value is 1.25 times the canvas value or less, or 35 ms or less.
4. `point`: the time from a pointer move onto a card to the lit paths on the screen,
   100 ms or less. Stage 1 has no lit paths (they come in stage 2). Thus this value is not
   measured in stage 1, and the script prints "not measured".
5. `size`: the size of the page file in bytes. The atlas value is 1.5 times the canvas
   value or less.

The pan of the budget is "a pan of 2 s". The scenario of the canvas measurement has 180
frames, which is 3 s at 60 frames each second. The script uses that scenario without a
change, so that the two pages have the same input as the earlier records.

Each timed value is the median of RUNS runs. Each run starts a new browser for each page
and each value. A value passes when its median passes. The budget passes when each value
that is measured passes for each input.

The inputs:

- `self`: the map of this repository (`config.load` of the repository root).
- `workspace`: the model of tests/fixture_workspace.py, with the positions of the placer
  (`place.compute` with all cards), as in the design study.
- `M11 tree`: the real canvas data of the generated tree with 50 maps (`m11_tree` of
  bench/jev/canvas_frames.py). It takes about 30 s to build.

The browser is the Chromium of Playwright, headless, 1440 x 900, device pixel ratio 1.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_budget.py
"""

from __future__ import annotations

import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RATE = 4
RUNS = 3
FIRST_FACTOR = 1.5
FIRST_LIMIT = 1500.0
FRAME_FACTOR = 1.25
FRAME_LIMIT = 35.0
SIZE_FACTOR = 1.5


def _self_data() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from systemap import (  # noqa: PLC0415
        atlas_data,
        canvas_data,
        canvas_page,
        config,
        facts_file,
        nest,
    )

    cfg = config.load(ROOT)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    theme = canvas_page.tree_theme(cfg, tree)
    return theme, canvas_data.build(cfg, tree, facts), atlas_data.build(cfg, tree, facts)


def _workspace_data() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sys.path.insert(0, str(ROOT / "tests"))
    import fixture_workspace as fw  # noqa: PLC0415

    from systemap import atlas_data, canvas_data, canvas_page, config, nest, place  # noqa: PLC0415

    laid = place.apply(fw.MODEL, place.compute(fw.MODEL, all_cards=True))
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "systemap.toml").write_text('name = "workspace"\n', encoding="utf-8")
        cfg = config.load(Path(tmp))
    theme = nest.load(config.load(ROOT)).top.theme
    one = nest.Map(
        id="",
        path=Path("map/model.py"),
        rel="map/model.py",
        model=laid,
        meaning=fw.MEANING,
        theme=theme,
    )
    tree = nest.Tree(maps=(one,))
    facts = fw.facts()
    return (
        canvas_page.tree_theme(cfg, tree),
        canvas_data.build(cfg, tree, facts),
        atlas_data.build(cfg, tree, facts),
    )


def _m11_data() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    import canvas_frames  # noqa: PLC0415  (a neighbour script in bench/jev)

    from systemap import config, nest  # noqa: PLC0415

    data = canvas_frames.m11_tree()
    return nest.load(config.load(ROOT)).top.theme, data, data


def write_pages(name: str, out: Path) -> tuple[Path, Path]:
    """Write the canvas page and the atlas page of the input `name`."""
    from systemap import atlas_page, canvas_page  # noqa: PLC0415

    theme, cdata, adata = {"self": _self_data, "workspace": _workspace_data, "M11 tree": _m11_data}[
        name
    ]()
    slug = name.replace(" ", "-").lower()
    canvas, atlas = out / f"{slug}-canvas.html", out / f"{slug}-atlas.html"
    canvas.write_text(canvas_page.build(theme, cdata), encoding="utf-8")
    atlas.write_text(atlas_page.build(theme, adata), encoding="utf-8")
    return canvas, atlas


def _median(page: Path, mode: str) -> float:
    import canvas_frames  # noqa: PLC0415

    key = "ready" if mode == "load" else "p95"
    return statistics.median(float(canvas_frames.run(page, mode, RATE)[key]) for _ in range(RUNS))


def measure(canvas: Path, atlas: Path) -> dict[str, tuple[float, float]]:
    """Give the canvas value and the atlas value of each timed measure and of the size."""
    out = {
        mode: (_median(canvas, mode), _median(atlas, mode)) for mode in ("load", "pan-fit", "dive")
    }
    out["size"] = (float(canvas.stat().st_size), float(atlas.stat().st_size))
    return out


def verdicts(found: dict[str, tuple[float, float]]) -> dict[str, bool]:
    """Give pass or fail for each measured value of one input."""
    first, pan, dive, size = found["load"], found["pan-fit"], found["dive"], found["size"]

    def frames(v: tuple[float, float]) -> bool:
        return v[1] <= FRAME_FACTOR * v[0] or v[1] <= FRAME_LIMIT

    return {
        "first": first[1] <= FIRST_FACTOR * first[0] and first[1] <= FIRST_LIMIT,
        "pan": frames(pan),
        "dive": frames(dive),
        "size": size[1] <= SIZE_FACTOR * size[0],
    }


def _word(ok: bool) -> str:
    return "pass" if ok else "fail"


def row(name: str, found: dict[str, tuple[float, float]]) -> str:
    """Give the table row of one input."""
    v = verdicts(found)
    cells = []
    for key, label in (("load", "first"), ("pan-fit", "pan"), ("dive", "dive")):
        c, a = found[key]
        cells.append(
            f"{c:.0f} / {a:.0f} ({_word(v[label])})"
            if key == "load"
            else f"{c:.1f} / {a:.1f} ({_word(v[label])})"
        )
    c, a = found["size"]
    cells.append(f"{c:,.0f} / {a:,.0f} = {a / c:.2f} ({_word(v['size'])})")
    return f"| {name} | " + " | ".join(cells) + " | not measured |"


def main() -> int:
    sys.path.insert(0, str(HERE))
    import canvas_frames  # noqa: PLC0415

    if canvas_frames.node() is None:
        print("failure: " + canvas_frames.missing())
        return 1
    ok = True
    print(
        "| Input | First frame canvas / atlas (ms) | Pan p95 canvas / atlas (ms) | "
        "Dive p95 canvas / atlas (ms) | Page size canvas / atlas (bytes) | Point to lit paths |"
    )
    print("|---|---|---|---|---|---|")
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("self", "workspace", "M11 tree"):
            canvas, atlas = write_pages(name, Path(tmp))
            found = measure(canvas, atlas)
            print(row(name, found), flush=True)
            ok &= all(verdicts(found).values())
    print("budget: " + _word(ok) + " (point to lit paths: not measured in stage 1)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
