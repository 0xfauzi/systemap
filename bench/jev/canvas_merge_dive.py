"""U1: the dive of the map of 400 cards after the merge of the four parts of step 4.

The run V1a of `canvas_views.py` on the merged work tree (U1 in bench/jev/README.md) gave a
p95 of 33.3 ms in 2 of the 3 quiet runs of B for the dive of the map of 400 cards at 4 times
CPU throttling with the layer data. The part header-layers alone gave 16.8 ms in each run.
This script compares the trees of the merge, to find the part that makes the difference.

Acceptance values, written before the first run on 2026-11-07:

1. The C2 rule of docs/design/nested-canvas.md: for the merged tree M, the p95 frame
   interval of each quiet run is at most 35.0 ms.
2. A/B against the part header-layers alone (H): the median of the p95 values of M is at
   most the median of H plus one tick (16.7 ms).
3. The values of the trees between H and M are information only. They do not give a pass
   or a fail.

The trees (`git archive` of each tree object, the `src` folder):

- H: the part header-layers alone.
- C: H and the part changes-rollup, merged on the seam of H.
- S: C and the part sequences.
- F: S and the part search.
- M: the work tree at the start of the run (`git write-tree` of the index).

The data is `canvas_views.layered(canvas_frames.grid_map(400))`, with the same theme for
each page. The scenario is `dive` of `canvas_views.js` with the variant `data` (the layer
data set before the move) and also `-` (no layer), 180 frames at 4 times throttling.

Order of the runs: ROUNDS rounds. Each round has each tree one time, and the order of the
trees turns by one in each round. Before each run, the quiet gate of `canvas_tree.py`
waits until no foreign chrome, chromium, headless_shell, node or pytest process has operated
for 30 s. A run with a foreign process in a sample (each 2 s) is not quiet, and the script
makes it again, 3 attempts or fewer. The values of a run that is not quiet do not count.

Run from the repository root, with the five tree objects given in the order H C S F:
    uv run python bench/jev/canvas_merge_dive.py H C S F
"""

from __future__ import annotations

import functools
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_frames as frames  # noqa: E402
import canvas_tree as gate  # noqa: E402
import canvas_views as views  # noqa: E402

NAMES = ("H", "C", "S", "F", "M")
VARIANTS = ("data", "-")
ROUNDS = 5
TICK = 16.7
LIMIT = 35.0


def _tree_now() -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "write-tree"], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _pages(tmp: Path, trees: dict[str, str]) -> dict[str, Path]:
    """Write the page of each tree, with the same data and theme."""
    from systemap import config, nest  # noqa: PLC0415

    theme = nest.load(config.load(ROOT)).top.theme
    (tmp / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    data = tmp / "data.json"
    data.write_text(json.dumps(views.layered(frames.grid_map(400))), encoding="utf-8")
    write = (
        "import json, sys; from pathlib import Path; from systemap import canvas_page; "
        "Path(sys.argv[3]).write_text(canvas_page.build(json.loads(Path(sys.argv[1]).read_text()),"
        " json.loads(Path(sys.argv[2]).read_text())), encoding='utf-8')"
    )
    pages: dict[str, Path] = {}
    for name, tree in trees.items():
        src = tmp / name
        src.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(ROOT), "archive", tree, "src"], capture_output=True, check=True
        )
        subprocess.run(["tar", "-x", "-C", str(src)], input=archive.stdout, check=True)
        pages[name] = tmp / f"{name}.html"
        subprocess.run(
            [sys.executable, "-c", write, str(tmp / "theme.json"), str(data), str(pages[name])],
            env={**os.environ, "PYTHONPATH": str(src / "src")},
            check=True,
            cwd=str(tmp),
        )
    return pages


def _measure(page: Path) -> dict[str, Any]:
    """Run the dive of each variant, with a sample of foreign processes each 2 s."""
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(gate._foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        out: dict[str, Any] = {v: views._run(page, "dive", 4, v) for v in VARIANTS}
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    return out


def _loaded(page: Path) -> dict[str, Any]:
    """Give the values of one run and the load average after it."""
    return _measure(page) | {"loadavg": os.getloadavg()[0]}


def _row(quiet: list[dict[str, Any]], name: str, v: str) -> float:
    """Print the row of tree `name` and variant v, and give the median of its p95 values."""
    mine = [r[v] for r in quiet if r["run"][0] == name]
    p95 = [x["p95"] for x in mine]
    top = max((x["max"] for x in mine), default=None)
    median = statistics.median(p95) if p95 else float("nan")
    print(f"| {name} | {v} | {len(p95)} | {', '.join(map(str, p95))} | {median} | {top} |")
    return median


def _verdict(runs: list[dict[str, Any]]) -> bool:
    quiet = [r for r in runs if r["quiet"]]
    print("| Tree | Variant | quiet runs | p95 of each quiet run (ms) | median p95 | max |")
    print("|---|---|---|---|---|---|")
    median = {(name, v): _row(quiet, name, v) for name in NAMES for v in VARIANTS}
    m = [r[v]["p95"] for r in quiet if r["run"][0] == "M" for v in VARIANTS]
    ok = bool(m) and max(m) <= LIMIT
    ok &= all(median["M", v] <= median["H", v] + TICK for v in VARIANTS)
    return ok


def main() -> int:
    if frames.node() is None:
        print("failure: " + frames.missing())
        return 1
    if len(sys.argv) != 5:
        print("failure: give the tree objects H C S F")
        return 1
    trees = dict(zip(NAMES, [*sys.argv[1:5], _tree_now()], strict=True))
    print("trees:", json.dumps(trees), flush=True)
    with tempfile.TemporaryDirectory() as name:
        pages = _pages(Path(name), trees)
        runs: list[dict[str, Any]] = []
        for k in range(ROUNDS):
            for name in NAMES[k % len(NAMES) :] + NAMES[: k % len(NAMES)]:
                runs.append(
                    gate.attempts(functools.partial(_loaded, pages[name]), f"{name}{k + 1}")
                )
    ok = _verdict(runs)
    print("result:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
