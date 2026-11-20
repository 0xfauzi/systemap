"""D1: the cause of the dive time of the M11 tree on the atlas page (B28, run 2).

B28 failed in run 2: the dive p95 of the M11 tree was 50.0 ms on the atlas page against 33.4
ms on the canvas page (bench/jev/README.md). The first run of B26 failed on the same value,
before the change `offEdges` of `atlas_lines`. The record of B28 says that a measurement of
the dive with and without `offEdges` on the same host is necessary.

This script measures the dive of the M11 tree (the scenario `dive` of
bench/jev/canvas_frames.py at 4 times CPU slowdown, as in bench/jev/atlas_budget.py) on
three pages of the same data: the canvas page, the atlas page, and the atlas page with no
call of `offEdges` (the page built from the script with the call removed). It runs RUNS rounds. Each round
runs the three pages one time each, in turns, so that a change of the load of the host has
the same effect on each page. It gives the p95 of each run.

Acceptance values, written on 2026-11-20 before the first run of this script, with no other
heavy command on the host:

D1a. `offEdges` is a cause of the dive time only if the atlas page with the call has a
     larger median p95 than the page without it, and 2 or more runs more at 50 ms or more.
D1b. The dive of the atlas page with the call meets the value of the budget (1.25 times the
     canvas value or less, or 35 ms or less) in 80 percent of the rounds or more. A round
     compares the two runs of that round. If D1b fails, the dive of the M11 tree is a fault
     of the atlas page and not only the noise of one run.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_dive_cause.py
"""

from __future__ import annotations

import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import atlas_budget as budget  # noqa: E402  (a neighbour script in bench/jev)
import canvas_frames  # noqa: E402

from systemap import atlas_page  # noqa: E402

RUNS = 10
CALL = "offEdges(m, list);"


def main() -> int:
    if canvas_frames.node() is None:
        print("failure: " + canvas_frames.missing())
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        canvas, atlas = budget.write_pages("M11 tree", Path(tmp))
        if atlas_page._SCRIPT.count(CALL) != 1:
            print("failure: the script does not have exactly one call of offEdges")
            return 1
        # The content policy of the page has the hash of the script, thus the page is built
        # again with the changed script, not changed after the build.
        kept = atlas_page._SCRIPT
        atlas_page._SCRIPT = kept.replace(CALL, "")
        try:
            bare_dir = Path(tmp) / "bare"
            bare_dir.mkdir()
            _c, bare = budget.write_pages("M11 tree", bare_dir)
        finally:
            atlas_page._SCRIPT = kept
        pages = {"canvas": canvas, "atlas": atlas, "atlas without offEdges": bare}
        got: dict[str, list[float]] = {k: [] for k in pages}
        for n in range(RUNS):
            for name, page in pages.items():
                got[name].append(float(canvas_frames.run(page, "dive", budget.RATE)["p95"]))
            print(f"round {n + 1}: " + ", ".join(f"{k} {v[-1]:.1f}" for k, v in got.items()))
    for name, values in got.items():
        slow = sum(v >= 50 for v in values)
        print(f"{name}: median {statistics.median(values):.1f} ms, {slow} runs at 50 ms or more")
    with_call, without = got["atlas"], got["atlas without offEdges"]
    cause = (
        statistics.median(with_call) > statistics.median(without)
        and sum(v >= 50 for v in with_call) >= sum(v >= 50 for v in without) + 2
    )
    rounds = sum(
        a <= budget.FRAME_FACTOR * c or a <= budget.FRAME_LIMIT
        for c, a in zip(got["canvas"], with_call, strict=True)
    )
    print(f"D1a. offEdges is a cause: {'yes' if cause else 'no'}")
    print(f"D1b. rounds that meet the budget value: {rounds} of {RUNS}: ", end="")
    print("PASS" if rounds >= 0.8 * RUNS else "FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
