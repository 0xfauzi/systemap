"""The gate of the atlas page: is a page that draws with SVG fast enough for a large tree?

Acceptance values, written before the first run on 2026-11-18, from "The gate" in
docs/design/atlas.md:

1. The time to the first complete frame is 1,500 ms or less at 4 times CPU slowdown
   (`Emulation.setCPUThrottlingRate`). The time starts at the start of the navigation. It
   stops in the first task after the first animation frame that follows the build of the
   top map: the elements of the top map and the small pictures of its nested maps are in
   the document, the labels have their places, and the browser has painted one frame.
2. The 95th percentile of the intervals between animation frames, at 4 times CPU slowdown,
   is 35 ms or less for each of these two moves:
   - `pan`: the top map at its fit, with a pan of 200 screen pixels to the left and right
     for 2,000 ms. The position comes from the time since the start.
   - `dive`: a zoom from the top map at its fit into the deepest map below the first card
     that opens a map (three levels down), and back out, in 180 frames, one camera change
     at each frame. The zoom keeps the point of the deep map at the same place on the
     screen, as the move of the study does (`go`), with a smooth start and stop.
   The browser starts a frame at a 60 Hz tick. Thus 35 ms is two ticks plus 5 percent, as
   in bench/jev/canvas_frames.py.
   A second rule applies to the dive only. The measurement host has no GPU and is slow:
   the canvas page itself has a p95 of more than 35 ms for its dive on this host. Thus each
   run also measures the scenario `dive` of bench/jev/canvas_frames.py on the canvas page
   of the same tree, at 4 times CPU slowdown. If the p95 of the dive of the atlas page is
   more than 35 ms, the value passes only if it is not more than 1.1 times the p95 of the
   dive of the canvas page in the same run.
3. The count of SVG elements in the document (the elements in the SVG namespace) is 6,000
   or less at each frame of the dive. The count is taken in a separate pass of the same
   dive, after the camera change of each frame, so that the count does not change the
   frame times of value 2.

The script makes three runs. Each run measures the four values in new browsers. A value
passes only when it passes in each of the three runs. The gate passes only when the three
values pass.

The data is the real canvas data object (`canvas_data.build`) of the M11 tree: 50 maps of
40 cards, three levels below the top map (`m11_tree` of bench/jev/canvas_frames.py).

The test page is the renderer of the design study (docs/design/atlas/study-script.html)
in bench/jev/atlas_frames_page.js, with three changes:

- it reads the canvas data object;
- a nested map can be in a card of a nested map, to any depth. The scale and the position
  of each map come from the card that opens it. Each built map has its own transform from
  the camera, so that a deep zoom keeps the precision of the numbers;
- the elements of a nested map are built only when the camera is near it: its frame is
  BUILD_PX screen pixels wide or more, and it is in the screen or in a margin of
  MARGIN times the screen size around it. They are removed when the frame is less than
  DROP_PX pixels wide or out of that area. A map that is not built shows as a small
  picture of its cards (one path element) in its card.

Each map shows the layer All, with all its flows. The page has the map view only: no
details panel and no other views. It has the embedded font of the product
(`page_font.FACE`), no style attribute and no external file. The start motion of the study
(the lines draw one time) is not in the page. The boundary flows of the ports are not
drawn.

The browser is the Chromium of Playwright, headless, 1440 x 900, device pixel ratio 1.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_frames.py [BUILD_PX DROP_PX MARGIN]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "atlas_frames.js"
TEMPLATE = HERE / "atlas_frames_page.html"
SCRIPT = HERE / "atlas_frames_page.js"
RATE = 4
RUNS = 3
LOAD_LIMIT = 1500.0
FRAME_LIMIT = 35.0
CANVAS_FACTOR = 1.1
COUNT_LIMIT = 6000
BUILD = (240.0, 160.0, 0.5)


def write_page(data: dict[str, Any], out: Path, build: tuple[float, float, float] = BUILD) -> Path:
    """Write the test page of the canvas data `data` with the building rule `build`."""
    from systemap import page_font  # noqa: PLC0415

    body = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    rule = json.dumps({"build": build[0], "drop": build[1], "margin": build[2]})
    script = SCRIPT.read_text(encoding="utf-8").replace("__RULE__", rule)
    page = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__FONT__", page_font.FACE)
        .replace("__DATA__", body)
        .replace("__SCRIPT__", script)
    )
    out.write_text(page, encoding="utf-8")
    return out


def run(page: Path, mode: str, rate: int = RATE) -> dict[str, Any]:
    """Run one mode of the driver in a new browser. Give the result object of the driver."""
    found = shutil.which("node")
    if found is None:
        raise RuntimeError("Node with the Playwright package and Chromium is necessary.")
    proc = subprocess.run(
        [found, str(DRIVER), str(page), mode, str(rate)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def one_run(atlas: Path, canvas: Path) -> dict[str, Any]:
    """Measure the four values one time."""
    import canvas_frames  # noqa: PLC0415  (a neighbour script in bench/jev)

    load = run(atlas, "load")
    pan = run(atlas, "pan")
    dive = run(atlas, "dive")
    count = run(atlas, "count")
    cdive = canvas_frames.run(canvas, "dive", RATE)
    return {"load": load, "pan": pan, "dive": dive, "count": count, "canvas": cdive}


def verdicts(found: dict[str, Any]) -> dict[str, bool]:
    """Give pass or fail for each acceptance value of one run."""
    dive, canvas = found["dive"]["p95"], found["canvas"]["p95"]
    return {
        "load": found["load"]["painted"] <= LOAD_LIMIT,
        "pan": found["pan"]["p95"] <= FRAME_LIMIT,
        "dive": dive <= FRAME_LIMIT or dive <= CANVAS_FACTOR * canvas,
        "count": found["count"]["max"] <= COUNT_LIMIT,
    }


def _word(ok: bool) -> str:
    return "pass" if ok else "fail"


def row(n: int, found: dict[str, Any]) -> str:
    """Give the table row of one run."""
    v = verdicts(found)
    load, pan, dive = found["load"], found["pan"], found["dive"]
    canvas, count = found["canvas"], found["count"]
    return (
        f"| {n} | {load['built']:.0f} | {load['painted']:.0f} ({_word(v['load'])}) | "
        f"{pan['median']:.1f} / {pan['p95']:.1f} / {pan['max']:.1f} ({_word(v['pan'])}) | "
        f"{dive['median']:.1f} / {dive['p95']:.1f} / {dive['max']:.1f} | "
        f"{canvas['median']:.1f} / {canvas['p95']:.1f} / {canvas['max']:.1f} | "
        f"{dive['p95'] / canvas['p95']:.2f} ({_word(v['dive'])}) | "
        f"{count['top']} / {count['max']} ({_word(v['count'])}) | {count['built']} |"
    )


def main(argv: list[str]) -> int:
    import canvas_frames  # noqa: PLC0415  (a neighbour script in bench/jev)

    if shutil.which("node") is None or canvas_frames.node() is None:
        print("failure: " + canvas_frames.missing())
        return 1
    build = (float(argv[0]), float(argv[1]), float(argv[2])) if len(argv) == 3 else BUILD
    print(
        f"building rule: build at {build[0]:.0f} px, drop below {build[1]:.0f} px, "
        f"margin {build[2]} of the screen"
    )
    data = canvas_frames.m11_tree()
    ok = {"load": True, "pan": True, "dive": True, "count": True}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        atlas = write_page(data, out / "atlas.html", build)
        canvas = canvas_frames.write_page(data, out / "canvas.html")
        print(
            "| Run | Built (ms) | First frame (ms) | Pan median / p95 / max (ms) | "
            "Dive median / p95 / max (ms) | Canvas dive median / p95 / max (ms) | "
            "Dive / canvas | SVG elements at the top fit / max | Maps built at most |"
        )
        print("|---|---|---|---|---|---|---|---|---|")
        for n in range(1, RUNS + 1):
            found = one_run(atlas, canvas)
            print(row(n, found), flush=True)
            for key, passed in verdicts(found).items():
                ok[key] &= passed
    for key, passed in ok.items():
        print(f"{key}: {_word(passed)}")
    print("gate: " + _word(all(ok.values())))
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main(sys.argv[1:]))
