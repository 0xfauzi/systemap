"""T0 dive: the spread of the dive value of the budget, and of two other measures of a dive.

Value 3 (`dive`) of bench/jev/atlas_budget.py is the 95th percentile (p95) of the intervals
between animation frames in the scenario `dive` of bench/jev/canvas_frames.py, at 4 times
CPU slowdown. At 60 frames each second, an interval is a whole number of frames (16.7, 33.3,
50.0 ms), thus one frame more in the 95th percentile can change the result from pass to
fail (D1 in bench/jev/README.md).

This script runs the same scenario (the driver bench/jev/t0_dive.js has the same camera
path, 180 frames, 1440 x 900 and the CPU slowdown of the budget) RUNS times on the canvas
page and RUNS times on the atlas page of each input of the budget (`atlas_budget.write_pages`:
self, workspace, M11 tree). Each round runs the canvas page and then the atlas page, so that
a change of the load of the host has the same effect on the two pages. For each run it gives
three measures of the full list of intervals:

- p95: the value of the budget (the same pick as canvas_frames.js),
- mean: the mean interval,
- over 20: the share of the intervals that are more than 20 ms (one frame or more lost).

It also gives the load average of the host before and after each input, and the processes
with the most CPU at the start.

This is a baseline measurement for the targets of stages 3 and 4 of the open faults. It has
no acceptance value. It does not change the budget script or its values.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/t0_dive.py
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import atlas_budget as budget  # noqa: E402  (a neighbour script in bench/jev)
import canvas_frames  # noqa: E402

RUNS = 10
RATE = 4
DRIVER = HERE / "t0_dive.js"


def _gaps(page: Path) -> list[float]:
    found = canvas_frames.node()
    assert found is not None
    proc = subprocess.run(
        [found, str(DRIVER), str(page), str(RATE)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return [float(g) for g in json.loads(proc.stdout)["gaps"]]


def measures(gaps: list[float]) -> tuple[float, float, float]:
    """Give the p95 (the pick of canvas_frames.js), the mean and the share over 20 ms."""
    s = sorted(gaps)
    p95 = round(s[min(len(s) - 1, int(len(s) * 0.95))], 1)
    return p95, statistics.fmean(s), sum(1 for g in s if g > 20) / len(s)


def _load() -> str:
    return " ".join(f"{v:.2f}" for v in os.getloadavg())


def _summary(name: str, rows: list[tuple[float, float, float]]) -> None:
    for k, label in enumerate(("p95 (ms)", "mean (ms)", "share over 20 ms")):
        vals = [r[k] for r in rows]
        print(
            f"  {name} {label}: min {min(vals):.3f}, median {statistics.median(vals):.3f}, "
            f"max {max(vals):.3f}, stdev {statistics.stdev(vals):.3f}"
        )
    p95 = [r[0] for r in rows]
    steps = {v: p95.count(v) for v in sorted(set(p95))}
    print(f"  {name} p95 values and counts: {steps}")


def main() -> int:
    if canvas_frames.node() is None:
        print("failure: " + canvas_frames.missing())
        return 1
    top = subprocess.run(
        ["ps", "-eo", "pcpu,comm", "--sort=-pcpu"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[:6]
    print("processes with the most CPU at the start: " + " | ".join(t.strip() for t in top))
    print(f"CPUs: {os.cpu_count()}")
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("self", "workspace", "M11 tree"):
            canvas, atlas = budget.write_pages(name, Path(tmp))
            print(f"\n{name}: load average before (1, 5, 15 min): {_load()}")
            found: dict[str, list[tuple[float, float, float]]] = {"canvas": [], "atlas": []}
            print("| Round | canvas p95 / mean / over 20 | atlas p95 / mean / over 20 |")
            print("|---|---|---|")
            for r in range(1, RUNS + 1):
                cells = []
                for page, key in ((canvas, "canvas"), (atlas, "atlas")):
                    m = measures(_gaps(page))
                    found[key].append(m)
                    cells.append(f"{m[0]:.1f} / {m[1]:.2f} / {m[2]:.3f}")
                print(f"| {r} | " + " | ".join(cells) + " |", flush=True)
            print(f"{name}: load average after: {_load()}")
            for key, rows in found.items():
                _summary(key, rows)
            passes = sum(
                1
                for c, a in zip(found["canvas"], found["atlas"], strict=True)
                if a[0] <= budget.FRAME_FACTOR * c[0] or a[0] <= budget.FRAME_LIMIT
            )
            print(f"  rounds that meet value 3 of the budget (p95): {passes} of {RUNS}")
            ratio = [a[1] / c[1] for c, a in zip(found["canvas"], found["atlas"], strict=True)]
            print(
                "  mean atlas / mean canvas in each round: " + ", ".join(f"{v:.3f}" for v in ratio)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
