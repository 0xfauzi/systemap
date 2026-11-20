"""B1 to B3: the performance budget of the atlas page against the canvas page.

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
   100 ms or less. The canvas page has no equal measure. Stage 1 had no lit paths, and
   the stage 1 records give "not measured". From stage 2 (written on 2026-11-18 before
   the first run of this measure): bench/jev/atlas_point.js moves the pointer onto 8
   cards of the top map that have flows in the first layer. The time of one move is from
   the time stamp of the pointermove event to the first animation frame after the frame
   that drew the lit paths. The value of a run is the largest time of its moves. The
   value of the input is the median of RUNS runs, and it passes at 100 ms or less.
5. `size`: the size of the page file in bytes. The atlas value is 1.5 times the canvas
   value or less.

The pan of the budget is "a pan of 2 s". The scenario of the canvas measurement has 180
frames, which is 3 s at 60 frames each second. The script uses that scenario without a
change, so that the two pages have the same input as the earlier records.

Each timed value is the median of RUNS runs. Each run starts a new browser for each page
and each value. A value passes when its median passes. The budget passes when each value
that is measured passes for each input.

The inputs:

- `self`: the map of this repository (`config.load` of the repository root). From stage 6
  (written on 2026-11-19 before the first run with it): the atlas page of `self` has the
  history data of the commits of this clone (`history_data.of_tree`), as `render` writes
  it with `[render] page = "atlas"`. The other inputs have no history.
- `workspace`: the model of tests/fixture_workspace.py, with the positions of the placer
  (`place.compute` with all cards), as in the design study.
- `M11 tree`: the real canvas data of the generated tree with 50 maps (`m11_tree` of
  bench/jev/canvas_frames.py). It takes about 30 s to build.

The browser is the Chromium of Playwright, headless, 1440 x 900, device pixel ratio 1.

From the repair of stage 6 (written on 2026-11-19 before the run of B15): the full output
of each run that a record of `bench/jev/README.md` gives is kept beside this script in
`bench/jev/atlas_budget_<record>.txt`, so that a reader can compare the record with the
output. The acceptance values do not change.

From stage 10 (written on 2026-11-19 before the run of B19): the map of this repository has
the nested map Page. Thus the `dive` of `self` zooms into Page, not into the middle card of
the top map. The acceptance values do not change.

From stage 11 (written on 2026-11-19 before the run of B21): the atlas page has the signs of a
nested map (`atlas_inside`): the bar, the zoom movement, the locator, the title of the frame,
the ground of a nested map and the line of a neighbour. The `dive` of each input now draws the
ground of a nested map and the title of its frame. The run has no other heavy process on the
machine. The acceptance values do not change: each value passes for self, workspace and the
M11 tree (A9 of stage 11).

From the third repair of stage 10 (written on 2026-11-19 before the run of B20): the nested
map Page has its neighbours at the sides of its frame (N5), and the actor container of a
nested map is a label on the atlas page. The acceptance values do not change.

From the final repair (written on 2026-11-20 before the run of B23): a label at rest also
keeps off the edges of the surfaces and of the region tints, and the halo of a label has the
color of the ground under it (`groundOf` in `atlas_lines`). The ring of a card on the canvas
page is on the pixel grid of the screen (`ringRect` in page_canvas_view). The acceptance
values do not change: each value must pass for self, workspace and the M11 tree.

From the repair of the zoomed-in view (written on 2026-11-20 before the run of B24): the
line of a neighbour has a new size and font (`upTag` in `atlas_draw`), the last frame of a
move out draws the nested map at the box of its card (`morphDone` in `atlas_inside`), and the
bar and the inside ground show in each view of a nested map. The acceptance values do not
change: each value must pass for self, workspace and the M11 tree.

From stage 2 of the open faults (written on 2026-11-20 before the run of B25): the nested map
Page has a new layout (four region columns, N7), a label at rest shows the full artifact,
and the lines of one neighbour with one artifact show one label (`labelKey` in
`atlas_lines`). The acceptance values do not change: each value must pass for self,
workspace and the M11 tree.

From the repair of stage 2 of the open faults (written on 2026-11-20 before the run of
B26): the nested map Page has a new layout (two region columns, 928 x 772, N8), and the
test hook `linesState` gives the width of each label and the counts of `seatWhy`. The
acceptance values do not change: each value must pass for self, workspace and the M11
tree.

Before the run of B27 (written on 2026-11-20): the nested map Page has the layout of N9
(928 x 860). The acceptance values do not change.

Before the runs of B28 (written on 2026-11-20, after the second review of stage 2 of the
open faults): the atlas page moves a part of a line that is near the edge of a surface
(`offEdges` in `atlas_lines`). The acceptance values do not change. A review found that B26
and B27 each ran again after a failed run until a run passed. Thus the rule of B28, written
before its first run: the script runs three times, with no other heavy command on the host,
and B28 passes only if each of the three runs passes each value. A failed run is not run
again, and the three results are all recorded.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_budget.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
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


def _self_history() -> dict[str, Any] | None:
    """The history data of this clone for the atlas page of `self`."""
    import dataclasses  # noqa: PLC0415

    from systemap import config, facts_file, history_data, nest  # noqa: PLC0415

    cfg = dataclasses.replace(config.load(ROOT), render_page="atlas")
    tree = nest.load(cfg)
    data, lines = history_data.of_tree(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    if lines:
        raise RuntimeError("\n".join(lines))
    return data


def _no_history() -> dict[str, Any] | None:
    return None


# The history data of each input that has one.
_HISTORY = {"self": _self_history}


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
    atlas.write_text(
        atlas_page.build(theme, adata, _HISTORY.get(name, _no_history)()),
        encoding="utf-8",
    )
    return canvas, atlas


POINT_LIMIT = 100.0


def _point(page: Path) -> float:
    """Give the median of RUNS runs of the largest point time of a run (acceptance 4)."""
    import canvas_frames  # noqa: PLC0415

    found = canvas_frames.node()
    if found is None:
        raise RuntimeError(canvas_frames.missing())
    values = []
    for _ in range(RUNS):
        proc = subprocess.run(
            [found, str(HERE / "atlas_point.js"), str(page), str(RATE)],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        values.append(float(json.loads(proc.stdout)["max"]))
    return statistics.median(values)


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
    out["point"] = (0.0, _point(atlas))
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
        "point": found["point"][1] <= POINT_LIMIT,
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
    point = found["point"][1]
    return f"| {name} | " + " | ".join(cells) + f" | {point:.0f} ({_word(v['point'])}) |"


def main() -> int:
    sys.path.insert(0, str(HERE))
    import canvas_frames  # noqa: PLC0415

    if canvas_frames.node() is None:
        print("failure: " + canvas_frames.missing())
        return 1
    ok = True
    print(
        "| Input | First frame canvas / atlas (ms) | Pan p95 canvas / atlas (ms) | "
        "Dive p95 canvas / atlas (ms) | Page size canvas / atlas (bytes) | Point to lit paths, atlas (ms) |"
    )
    print("|---|---|---|---|---|---|")
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("self", "workspace", "M11 tree"):
            canvas, atlas = write_pages(name, Path(tmp))
            found = measure(canvas, atlas)
            print(row(name, found), flush=True)
            ok &= all(verdicts(found).values())
    print("budget: " + _word(ok))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
