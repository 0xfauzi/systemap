"""V1: C2 and C3 of the canvas page with the header and the layers (step 4, header-layers).

Acceptance values, written before the first run on 2026-11-07, from the task of the part
header-layers of step 4 of docs/design/nested-canvas.md:

1. C2 of B with a layer. For each scenario below, with the layer data set before the move
   (`data`), and for pan-fit also with a layer change to All and back to data during the
   move (`switch`): the p95 frame interval is at most 35.0 ms at 4 times CPU throttling and
   at most 17.5 ms at normal CPU speed, in each quiet run of B.
2. A/B: for each scenario, variant and rate, the median of the p95 values of B is at most
   the median of A plus one tick (16.7 ms).
3. The cost does not grow with the card count: in each frame of each run of B, the count of
   seam calls (`viewState().hooks`) is not more than the count of the cards and the flows
   that the frame draws (`over` <= 0).
4. C3 of B: the time to `systemapCanvas.ready` of the real M11 tree, at normal CPU speed, is
   at most 1,500 ms in each load of each quiet run. The value at 4 times throttling is
   information only.

The scenarios are pan-fit, all-open and dive of the M11 shape (`canvas_frames.nested_tree`),
pan-fit and dive of the map of 400 cards, and pan-fit of the map of 1,500 cards
(`canvas_frames.grid_map`), with 180 frames each (`canvas_views.js`). The generated data
gets two layers (`layered`): the even flows are data, the odd flows are control. Thus the
layer data hides half of the flows and makes cards quiet.

A is the canvas page of commit BASE (`canvas_page.build` from `git archive` of `src`). It
has no view part, thus it does the same moves with no layer. B is the page of the work tree.
The two pages have the same data and theme.

Order of the runs: A1, B1, B2, A2, A3, B3, with the quiet gate of `canvas_tree.py`: before
each run, the script waits until no chrome, chromium, headless_shell, node or pytest process
that is not a descendant of this script has operated for 30 s (900 s or less). It samples
such processes each 2 s during the run. A run with such a process is not quiet, and the
script makes it again, 3 attempts or fewer. The values of a run that is not quiet do not
count for the acceptance.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_views.py
"""

from __future__ import annotations

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
import canvas_tree as tree  # noqa: E402

BASE = "d8ac070"
DRIVER = HERE / "canvas_views.js"
ORDER = ("A", "B", "B", "A", "A", "B")
TICK = 16.7
LOADS = 5
CASES = (
    ("M11 shape", "pan-fit", "data"),
    ("M11 shape", "pan-fit", "switch"),
    ("M11 shape", "all-open", "data"),
    ("M11 shape", "dive", "data"),
    ("400 cards", "pan-fit", "data"),
    ("400 cards", "pan-fit", "switch"),
    ("400 cards", "dive", "data"),
    ("1,500 cards", "pan-fit", "data"),
    ("1,500 cards", "pan-fit", "switch"),
)


def layered(data: dict[str, Any]) -> dict[str, Any]:
    """Give the data with two layers: the even flows are data, the odd flows control.

    tests/test_canvas_header_browser.py uses the same rule (`_layered`)."""
    for m in data["maps"]:
        for i, f in enumerate(m["flows"]):
            f["l"] = "data" if i % 2 == 0 else "control"
        m["layers"] = [
            {"id": lay, "n": lay.title(), "q": f"Which flows are {lay} flows?", "e": e}
            for lay, e in (
                ("data", list(range(0, len(m["flows"]), 2))),
                ("control", list(range(1, len(m["flows"]), 2))),
            )
        ]
    return data


def sequenced(data: dict[str, Any], steps: int = 20) -> dict[str, Any]:
    """Give the data with one sequence of `steps` steps in the top map: the first flows of
    the map in order (the part sequences, `canvas_sequences_frames.py`)."""
    top = data["maps"][0]
    top["sq"] = [
        {
            "id": "walk",
            "n": "Walk the records",
            "s": [
                {
                    "f": k,
                    "a": [f["s"]],
                    "y": f"Step {k + 1}: {f['s']} sends the record to {f['t']}.",
                }
                for k, f in enumerate(top["flows"][:steps])
            ],
        }
    ]
    return data


def _run(page: Path, mode: str, rate: int, variant: str = "") -> dict[str, Any]:
    node = frames.node()
    if node is None:
        raise RuntimeError(frames.missing())
    proc = subprocess.run(
        [node, str(DRIVER), str(page), mode, str(rate), variant or "-"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def _pages(tmp: Path) -> dict[str, dict[str, Path]]:
    """Write the pages of A and B for each data set, with the same data and theme."""
    from systemap import config, nest  # noqa: PLC0415

    data = {
        "M11 shape": layered(frames.nested_tree()),
        "400 cards": layered(frames.grid_map(400)),
        "1,500 cards": layered(frames.grid_map(1500)),
        "M11 tree": frames.m11_tree(),
    }
    theme = nest.load(config.load(ROOT)).top.theme
    (tmp / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    old = tmp / "a"
    old.mkdir()
    archive = subprocess.run(
        ["git", "-C", str(ROOT), "archive", BASE, "src"], capture_output=True, check=True
    )
    subprocess.run(["tar", "-x", "-C", str(old)], input=archive.stdout, check=True)
    write = (
        "import json, sys; from pathlib import Path; from systemap import canvas_page; "
        "Path(sys.argv[3]).write_text(canvas_page.build(json.loads(Path(sys.argv[1]).read_text()),"
        " json.loads(Path(sys.argv[2]).read_text())), encoding='utf-8')"
    )
    pages: dict[str, dict[str, Path]] = {"A": {}, "B": {}}
    for k, (name, value) in enumerate(data.items()):
        src = tmp / f"data{k}.json"
        src.write_text(json.dumps(value), encoding="utf-8")
        pages["A"][name] = tmp / f"A{k}.html"
        subprocess.run(
            [sys.executable, "-c", write, str(tmp / "theme.json"), str(src), str(pages["A"][name])],
            env={**os.environ, "PYTHONPATH": str(old / "src")},
            check=True,
            cwd=str(tmp),
        )
        pages["B"][name] = frames.write_page(value, tmp / f"B{k}.html")
    return pages


def _measure(pages: dict[str, Path]) -> dict[str, Any]:
    """Run each case at 4x and 1x and the loads, with a sample of foreign processes each 2 s."""
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(tree._foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out: dict[str, Any] = {"cases": {}, "load": {}}
    try:
        for rate in (4, 1):
            for name, mode, variant in CASES:
                out["cases"][f"{name}|{mode}|{variant}|{rate}"] = _run(
                    pages[name], mode, rate, variant
                )
            out["load"][str(rate)] = [
                _run(pages["M11 tree"], "load", rate)["ready"] for _ in range(LOADS)
            ]
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    out["loadavg"] = os.getloadavg()[0]
    return out


def _case(quiet: list[dict[str, Any]], key: str, limit: float) -> dict[str, Any]:
    """Give the values of one case in the quiet runs: the p95 of A and B, the median
    difference, the largest `over` of B, and the result."""

    def of(which: str, field: str) -> list[Any]:
        return [r["cases"][key][field] for r in quiet if r["run"][0] == which]

    a, b, over = of("A", "p95"), of("B", "p95"), of("B", "over")
    diff = statistics.median(b) - statistics.median(a) if a and b else None
    good = bool(b) and max(b) <= limit and diff is not None and diff <= TICK
    good &= all(v is not None and v <= 0 for v in over)
    return {"a": a, "b": b, "over": over, "diff": diff, "good": good}


def _loads(quiet: list[dict[str, Any]]) -> bool:
    """Print C3 of the quiet runs and give the result of acceptance 4."""
    for rate in ("1", "4"):
        for which in ("A", "B"):
            values = [v for r in quiet if r["run"][0] == which for v in r["load"][rate]]
            print(
                f"C3 {rate}x {which}: median {statistics.median(values) if values else None}"
                f" ms, max {max(values, default=None)} ms"
            )
    b1 = [v for r in quiet if r["run"][0] == "B" for v in r["load"]["1"]]
    return bool(b1) and max(b1) <= frames.LOAD_LIMIT


def _verdict(runs: list[dict[str, Any]]) -> bool:
    quiet = [r for r in runs if r["quiet"]]
    ok = any(r["run"][0] == "B" for r in quiet) and any(r["run"][0] == "A" for r in quiet)
    print("| Data | Scenario | Variant | CPU | A p95 | B p95 | Median B - A | B over | Result |")
    print("|---|---|---|---|---|---|---|---|---|")
    for rate in (4, 1):
        for name, mode, variant in CASES:
            c = _case(quiet, f"{name}|{mode}|{variant}|{rate}", frames.LIMITS[rate])
            ok &= c["good"]
            diff = "" if c["diff"] is None else f"{c['diff']:+.1f}"
            print(
                f"| {name} | {mode} | {variant} | {rate}x | {', '.join(map(str, c['a']))} | "
                f"{', '.join(map(str, c['b']))} | {diff} | "
                f"{max(c['over'], default=None)} | "
                f"{'pass' if c['good'] else 'fail'} |"
            )
    ok &= _loads(quiet)
    return ok


def main() -> int:
    if frames.node() is None:
        print("failure: " + frames.missing())
        return 1
    with tempfile.TemporaryDirectory() as name:
        pages = _pages(Path(name))
        runs: list[dict[str, Any]] = []
        count = {"A": 0, "B": 0}
        for which in ORDER:
            count[which] += 1
            for attempt in range(1, tree.ATTEMPTS + 1):
                waited = tree._gate()
                found = _measure(pages[which])
                found |= {
                    "run": f"{which}{count[which]}",
                    "attempt": attempt,
                    "waited": round(waited),
                }
                found["quiet"] = not found["foreign"]
                print(json.dumps(found), flush=True)
                if found["quiet"]:
                    break
            runs.append(found)
        print("quiet runs:", ", ".join(r["run"] for r in runs if r["quiet"]) or "none")
        ok = _verdict(runs)
        print("result:", "pass" if ok else "fail")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
