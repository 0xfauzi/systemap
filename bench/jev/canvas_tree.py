"""L1: the list of the tree on the canvas page (step 3 of docs/design/nested-canvas.md).

Acceptance values, written before the first run on 2026-11-06:

1. Page bytes. The canvas page of the real M11 tree (50 maps) with the list (B) is at
   most 12,000 bytes larger than the page without the list (A). The script also gives
   the change after gzip -6. The canvas data is the same in the two pages.
2. The time to write the list in the page (`systemapCanvas.treeMs`), for the M11 tree at
   normal CPU speed, is at most 100 ms in each load of each quiet run of B. The same time
   with 4 times CPU throttling is also given. It has no acceptance value.
3. C3 of B: the time from the start of the navigation to `systemapCanvas.ready`, M11
   tree, normal CPU speed, is at most 1,500 ms in each load of each quiet run. The script
   gives the change of the median from A to B at 1x and at 4x. That change has no
   acceptance value.

A is the canvas page of commit 1af75d2: `canvas_page.build` from a copy of `src` of that
commit (`git archive`). B is the page of the working tree. The two pages have the same
canvas data (`canvas_frames.m11_tree`) and the same theme.

Order of the runs: A1, B1, B2, A2, A3, B3. Each run has LOADS loads at 1x and LOADS loads
at 4x (`canvas_frames.js load`), each in a new browser. The quiet gate: before each run,
the script waits until no chrome, chromium, headless_shell, node or pytest process that
is not a descendant of this script has operated for 30 s (a poll each 1 s). A zombie
process does not count. During the run, it records such processes each 2 s. A run with
such a process in a sample is not quiet, and the script makes it again, 3 attempts or
fewer. The gate waits 900 s or less. A run that is not quiet after 3 attempts is given
as "not quiet", and its values do not count for the acceptance.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_tree.py
"""

from __future__ import annotations

import gzip
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_frames as frames  # noqa: E402

BASE = "1af75d2"
LOADS = 5
ORDER = ("A", "B", "B", "A", "A", "B")
WATCHED = ("chrome", "chromium", "headless_shell", "node", "pytest")
QUIET_S, GATE_S, ATTEMPTS = 30.0, 900.0, 3
BYTES_LIMIT, TREE_LIMIT = 12_000, 100.0


def _foreign() -> list[str]:
    """Give the watched processes that are not descendants of this script, and not zombies."""
    procs: dict[int, tuple[int, str, str]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
        except OSError:
            continue
        name = stat[stat.index("(") + 1 : stat.rindex(")")]
        state, ppid = stat[stat.rindex(")") + 2 :].split()[:2]
        procs[int(entry.name)] = (int(ppid), name, state)
    mine = os.getpid()

    def ours(pid: int) -> bool:
        while pid > 1 and pid in procs:
            if pid == mine:
                return True
            pid = procs[pid][0]
        return False

    return sorted(
        f"{pid} {name}"
        for pid, (_ppid, name, state) in procs.items()
        if state != "Z" and any(w in name for w in WATCHED) and not ours(pid)
    )


def _gate() -> float:
    """Wait for QUIET_S seconds with no foreign process. Give the wait in seconds."""
    start = time.monotonic()
    quiet_since = start
    while time.monotonic() - quiet_since < QUIET_S:
        if time.monotonic() - start > GATE_S:
            break
        if _foreign():
            quiet_since = time.monotonic()
        time.sleep(1)
    return time.monotonic() - start


def _loads(page: Path) -> dict[str, Any]:
    """Load the page LOADS times at 1x and at 4x, with a sample of the foreign processes
    each 2 s."""
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(_foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out: dict[str, Any] = {}
    try:
        for rate in (1, 4):
            found = [frames.run(page, "load", rate) for _ in range(LOADS)]
            out[f"{rate}x"] = {
                "ready": [round(f["ready"], 1) for f in found],
                "tree": [None if f["treeMs"] is None else round(f["treeMs"], 1) for f in found],
            }
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    out["load"] = os.getloadavg()[0]
    return out


def _pages(tmp: Path) -> dict[str, Path]:
    """Write page A and page B of the M11 tree with the same data and theme."""
    from systemap import config, nest  # noqa: PLC0415

    data = frames.m11_tree()
    (tmp / "data.json").write_text(json.dumps(data), encoding="utf-8")
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
        "t = Path(sys.argv[1]); Path(sys.argv[3]).write_text(canvas_page.build("
        "json.loads((t / 'theme.json').read_text()), json.loads((t / 'data.json').read_text())),"
        " encoding='utf-8')"
    )
    pages = {"A": tmp / "A.html"}
    subprocess.run(
        [sys.executable, "-c", write, str(tmp), "A", str(pages["A"])],
        env={**os.environ, "PYTHONPATH": str(old / "src")},
        check=True,
        cwd=str(tmp),
    )
    pages["B"] = frames.write_page(data, tmp / "B.html")
    return pages


def main() -> int:
    if frames.node() is None:
        print(frames.missing())
        return 1
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        pages = _pages(tmp)
        raw = {k: p.read_bytes() for k, p in pages.items()}
        size = {k: (len(v), len(gzip.compress(v, 6))) for k, v in raw.items()}
        print(
            f"page bytes: A {size['A'][0]:,} raw, {size['A'][1]:,} gzip; "
            f"B {size['B'][0]:,} raw, {size['B'][1]:,} gzip; "
            f"B - A {size['B'][0] - size['A'][0]:,} raw, {size['B'][1] - size['A'][1]:,} gzip"
        )
        ok = size["B"][0] - size["A"][0] <= BYTES_LIMIT
        runs: list[dict[str, Any]] = []
        count = {"A": 0, "B": 0}
        for which in ORDER:
            count[which] += 1
            for attempt in range(1, ATTEMPTS + 1):
                waited = _gate()
                found = _loads(pages[which])
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
        quiet = [r for r in runs if r["quiet"]]
        for rate in ("1x", "4x"):
            med = {
                k: statistics.median(v for r in quiet if r["run"][0] == k for v in r[rate]["ready"])
                for k in ("A", "B")
                if any(r["run"][0] == k for r in quiet)
            }
            trees = [v for r in quiet if r["run"][0] == "B" for v in r[rate]["tree"]]
            print(
                f"{rate}: median ready {med}; B tree ms min {min(trees, default=None)}, "
                f"median {statistics.median(trees) if trees else None}, max {max(trees, default=None)}"
            )
        b1 = [r["1x"] for r in quiet if r["run"][0] == "B"]
        ok &= bool(b1) and all(max(x["tree"]) <= TREE_LIMIT for x in b1)
        ok &= bool(b1) and all(max(x["ready"]) <= frames.LOAD_LIMIT for x in b1)
        print("quiet runs:", ", ".join(r["run"] for r in quiet) or "none")
        print("result:", "pass" if ok else "fail")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
