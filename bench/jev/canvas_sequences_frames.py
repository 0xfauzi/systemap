"""Q2: C2 of the canvas page with a sequence shown (step 4, part sequences).

Acceptance values, written before the first run on 2026-11-07, from the task of the part
sequences of step 4 of docs/design/nested-canvas.md:

1. C2 of B with a sequence. For each case below, the p95 frame interval is at most 35.0 ms
   at 4 times CPU throttling, in each quiet run of B.
2. A/B: for each case, the median of the p95 values of B is at most the median of A plus
   one tick (16.7 ms).
3. The cost does not grow with the card count: in each frame of each run of B, the count of
   seam calls (`viewState().hooks`) is not more than the count of the cards and the flows
   that the frame draws (`over` <= 0).
4. In each run of B, the Sequences view shows the route: the flows of the route
   (`seqState().flows`) are the flows of the sequence (`shown`).

The cases are pan-fit and dive (`canvas_sequences_frames.js`, 180 frames each) of the
self-map (16 sequences, the first sequence of the top map is shown) and of the generated
map of 400 cards with one sequence of 20 steps (`canvas_views.sequenced`), each in the
Whole route (`whole`) and in the Steps mode at step 10 (`steps`). The values at normal CPU
speed are not measured.

A is the canvas page of the base tree BASE: the work tree of the part header-layers that
this part is built on (`git archive` of the tree object of `src`). It has no Sequences
view, so it does the same moves in the Map view. B is the page of the work tree. The two
pages have the same data and theme.

Order of the runs: A1, B1, B2, A2, A3, B3, with the quiet gate of `canvas_tree.py`: before
each run, the script waits until no chrome, chromium, headless_shell, node or pytest process
that is not a descendant of this script has operated for 30 s (900 s or less). It samples
such processes each 2 s during the run. A run with such a process is not quiet, and the
script makes it again, 3 attempts or fewer. The values of a run that is not quiet do not
count for the acceptance.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_sequences_frames.py [BASE]
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
import canvas_tree as tree  # noqa: E402
import canvas_views as views  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "023115be29faedafbc67ab747dc026b0b3b4ecd1"
DRIVER = HERE / "canvas_sequences_frames.js"
ORDER = ("A", "B", "B", "A", "A", "B")
TICK = 16.7
LIMIT = 35.0
CASES = tuple(
    (name, mode, variant)
    for name in ("self-map", "400 cards")
    for mode in ("pan-fit", "dive")
    for variant in ("whole", "steps")
)


def _run(page: Path, mode: str, variant: str) -> dict[str, Any]:
    node = frames.node()
    if node is None:
        raise RuntimeError(frames.missing())
    proc = subprocess.run(
        [node, str(DRIVER), str(page), mode, "4", variant],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def _self_data() -> dict[str, Any]:
    from systemap import canvas_data, config, facts_file, nest  # noqa: PLC0415

    cfg = config.load(ROOT)
    return canvas_data.build(cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root))


def _pages(tmp: Path) -> tuple[dict[str, dict[str, Path]], dict[str, list[int]]]:
    """Write the pages of A and B for each data set, with the same data and theme."""
    from systemap import config, nest  # noqa: PLC0415

    data = {"self-map": _self_data(), "400 cards": views.sequenced(frames.grid_map(400))}
    routes = {
        name: sorted({s["f"] for s in d["maps"][0]["sq"][0]["s"] if s["f"] >= 0})
        for name, d in data.items()
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
    return pages, routes


def _measure(pages: dict[str, Path]) -> dict[str, Any]:
    """Run each case at 4x, with a sample of foreign processes each 2 s."""
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(tree._foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out: dict[str, Any] = {"cases": {}}
    try:
        for name, mode, variant in CASES:
            out["cases"][f"{name}|{mode}|{variant}"] = _run(pages[name], mode, variant)
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    out["loadavg"] = os.getloadavg()[0]
    return out


def _case(quiet: list[dict[str, Any]], key: str, route: list[int]) -> dict[str, Any]:
    """Give the values of one case in the quiet runs: the p95 of A and B, the median
    difference, the largest `over` of B, if B showed the route, and the result."""

    def of(which: str, field: str) -> list[Any]:
        return [r["cases"][key][field] for r in quiet if r["run"][0] == which]

    a, b, over = of("A", "p95"), of("B", "p95"), of("B", "over")
    shown = [v == route for v in of("B", "shown")]
    diff = statistics.median(b) - statistics.median(a) if a and b else None
    good = bool(b) and max(b) <= LIMIT and diff is not None and diff <= TICK
    good &= all(v is not None and v <= 0 for v in over) and all(shown)
    return {"a": a, "b": b, "over": over, "shown": all(shown), "diff": diff, "good": good}


def _verdict(runs: list[dict[str, Any]], routes: dict[str, list[int]]) -> bool:
    quiet = [r for r in runs if r["quiet"]]
    ok = any(r["run"][0] == "B" for r in quiet) and any(r["run"][0] == "A" for r in quiet)
    print("| Data | Scenario | Variant | A p95 | B p95 | Median B - A | B over | Route | Result |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, mode, variant in CASES:
        c = _case(quiet, f"{name}|{mode}|{variant}", routes[name])
        ok &= c["good"]
        diff = "" if c["diff"] is None else f"{c['diff']:+.1f}"
        print(
            f"| {name} | {mode} | {variant} | {', '.join(map(str, c['a']))} | "
            f"{', '.join(map(str, c['b']))} | {diff} | "
            f"{max(c['over'], default=None)} | {c['shown']} | {'pass' if c['good'] else 'fail'} |"
        )
    return ok


def main() -> int:
    if frames.node() is None:
        print("failure: " + frames.missing())
        return 1
    with tempfile.TemporaryDirectory() as name:
        pages, routes = _pages(Path(name))
        runs: list[dict[str, Any]] = []
        count = {"A": 0, "B": 0}
        for which in ORDER:
            count[which] += 1
            runs.append(
                tree.attempts(functools.partial(_measure, pages[which]), f"{which}{count[which]}")
            )
        print("base:", BASE)
        print("quiet runs:", ", ".join(r["run"] for r in runs if r["quiet"]) or "none")
        ok = _verdict(runs, routes)
        print("result:", "pass" if ok else "fail")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
