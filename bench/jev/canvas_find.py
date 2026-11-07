"""S8: the Find dialog of the canvas page (step 4 of docs/design/nested-canvas.md).

Acceptance values, written before the first run on 2026-11-07:

1. Page bytes. The canvas page of the M11 shape (`canvas_frames.nested_tree`, 50 maps and
   2,000 cards) with the Find dialog (B) is at most 32,000 bytes larger than the page of
   commit d8ac070 (A). The script also gives the change after gzip -6. The canvas data
   element is the same text in the two pages (0 more bytes of data).
2. The time to make the results (`systemapCanvas.find.build`) for the M11 shape at normal
   CPU speed is at most 50 ms in each of the BUILDS calls of each quiet run of B. The script
   also gives the time to make and rank the results for three texts. That time has no
   acceptance value.
3. C2 pan-fit with 4 times CPU throttling: in each quiet run of B, the dialog opens and
   closes before the pan (`pan-after`), and the p95 frame interval is at most 35 ms. The
   median p95 of the quiet runs of B is at most 1 ms more than the median p95 of the quiet
   runs of A (`pan`). Thus the dialog adds no work to a frame.

A is the canvas page of commit d8ac070: `canvas_page.build` from a copy of `src` of that
commit (`git archive`). B is the page of the working tree. The two pages have the same data
and the same theme.

Order of the runs: A1, B1, B2, A2, A3, B3. A run of A is one pan at 4x. A run of B is one
build measure at 1x and one pan at 4x, each in a new browser. The quiet gate is the gate of
`canvas_tree.py`: before each run, the script waits until no chrome, chromium,
headless_shell, node or pytest process that is not a descendant of this script has
operated for 30 s (900 s or less). During the run, it records such processes each 2 s. A
run with such a process is not quiet, and the script makes it again, 3 attempts or fewer.
The values of a run that is not quiet do not count for the acceptance.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_find.py
"""

from __future__ import annotations

import gzip
import json
import os
import re
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

BASE = "d8ac070"
ORDER = ("A", "B", "B", "A", "A", "B")
ATTEMPTS = 3
BYTES_LIMIT, BUILD_LIMIT, P95_LIMIT, SAME_LIMIT = 32_000, 50.0, 35.0, 1.0
DRIVER = HERE / "canvas_find.js"
DATA = re.compile(r'id="canvas-data">(.*?)</script>', re.S)


def _drive(page: Path, mode: str, rate: int) -> dict[str, Any]:
    proc = subprocess.run(
        [str(frames.node()), str(DRIVER), str(page), mode, str(rate)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def _run(which: str, page: Path) -> dict[str, Any]:
    """One run, with a sample of the foreign processes each 2 s."""
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(gate._foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out: dict[str, Any] = {}
    try:
        if which == "B":
            out["build"] = _drive(page, "build", 1)
        out["pan"] = _drive(page, "pan-after" if which == "B" else "pan", 4)
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    out["load"] = os.getloadavg()[0]
    return out


def _pages(tmp: Path) -> dict[str, Path]:
    """Write page A and page B of the M11 shape with the same data and theme."""
    from systemap import config, nest  # noqa: PLC0415

    data = frames.nested_tree()
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
        "t = Path(sys.argv[1]); Path(sys.argv[2]).write_text(canvas_page.build("
        "json.loads((t / 'theme.json').read_text()), json.loads((t / 'data.json').read_text())),"
        " encoding='utf-8')"
    )
    pages = {"A": tmp / "A.html"}
    subprocess.run(
        [sys.executable, "-c", write, str(tmp), str(pages["A"])],
        env={**os.environ, "PYTHONPATH": str(old / "src")},
        check=True,
        cwd=str(tmp),
    )
    pages["B"] = frames.write_page(data, tmp / "B.html")
    return pages


def _bytes(pages: dict[str, Path]) -> bool:
    raw = {k: p.read_bytes() for k, p in pages.items()}
    size = {k: (len(v), len(gzip.compress(v, 6))) for k, v in raw.items()}
    data = {k: DATA.search(v.decode("utf-8")) for k, v in raw.items()}
    same = all(data.values()) and data["A"].group(1) == data["B"].group(1)  # type: ignore[union-attr]
    print(
        f"page bytes: A {size['A'][0]:,} raw, {size['A'][1]:,} gzip; "
        f"B {size['B'][0]:,} raw, {size['B'][1]:,} gzip; "
        f"B - A {size['B'][0] - size['A'][0]:,} raw, {size['B'][1] - size['A'][1]:,} gzip; "
        f"same data: {same}"
    )
    return same and size["B"][0] - size["A"][0] <= BYTES_LIMIT


def _attempts(which: str, page: Path, n: int) -> dict[str, Any]:
    """Make run `which` n, again until it is quiet, in ATTEMPTS attempts or fewer."""
    found: dict[str, Any] = {}
    for attempt in range(1, ATTEMPTS + 1):
        waited = gate._gate()
        found = _run(which, page)
        found |= {"run": f"{which}{n}", "attempt": attempt, "waited": round(waited)}
        found["quiet"] = not found["foreign"]
        print(json.dumps(found), flush=True)
        if found["quiet"]:
            break
    return found


def _verdict(quiet: list[dict[str, Any]]) -> bool:
    """Print the values of the quiet runs and give the result of acceptance 2 to 4."""
    b = [r for r in quiet if r["run"][0] == "B"]
    a = [r for r in quiet if r["run"][0] == "A"]
    builds = [v for r in b for v in r["build"]["build"]]
    print(
        f"build ms (B, 1x): min {min(builds, default=None)}, "
        f"median {statistics.median(builds) if builds else None}, max {max(builds, default=None)}"
    )
    p95 = {k: [r["pan"]["p95"] for r in v] for k, v in (("A", a), ("B", b))}
    print(f"pan-fit p95 at 4x: A {p95['A']}, B {p95['B']}")
    ok = bool(b) and all(max(r["build"]["build"]) <= BUILD_LIMIT for r in b)
    ok &= bool(b) and all(v <= P95_LIMIT for v in p95["B"])
    ok &= (
        bool(a)
        and bool(b)
        and (statistics.median(p95["B"]) <= statistics.median(p95["A"]) + SAME_LIMIT)
    )
    return ok


def main() -> int:
    if frames.node() is None:
        print(frames.missing())
        return 1
    with tempfile.TemporaryDirectory() as name:
        pages = _pages(Path(name))
        ok = _bytes(pages)
        runs: list[dict[str, Any]] = []
        count = {"A": 0, "B": 0}
        for which in ORDER:
            count[which] += 1
            runs.append(_attempts(which, pages[which], count[which]))
        quiet = [r for r in runs if r["quiet"]]
        ok &= _verdict(quiet)
        print("quiet runs:", ", ".join(r["run"] for r in quiet) or "none")
        print("result:", "pass" if ok else "fail")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
