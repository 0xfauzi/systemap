"""D1: the canvas page as the default output (step 5 of docs/design/nested-canvas.md).

Acceptance values, written before the first run on 2026-11-08:

1. C3 of B: the time from the start of the navigation to `systemapCanvas.ready`, M11
   tree (50 maps), normal CPU speed, is at most 1,500 ms in each load of each quiet run.
   The script gives the median of A and of B at 1x and at 4x. The change of the median
   has no acceptance value. Step 5 changes no drawing code. It changes the start of the
   page: the URL hash `#changes` (`linkedMap` in `page_canvas_tree`) and the policy
   (frame-src 'none').
2. The small page of each nested map of the M11 tree (49 pages, `canvas_redirect.page`)
   has 2,048 bytes or less.
3. Page bytes: the script gives the bytes of the canvas page A and B, raw and after
   gzip -6. They have no acceptance value. The canvas data is the same in the two pages.

A is the canvas page of commit 0254afb (`canvas_page.build` from a copy of `src` of that
commit, `git archive`). B is the page of the working tree. The two pages have the same
canvas data (`canvas_frames.m11_tree`) and the same theme.

Order of the runs, the loads and the quiet gate: as in `canvas_tree.py` (A1, B1, B2, A2,
A3, B3; LOADS loads at 1x and at 4x, each in a new browser; a run with a foreign chrome,
chromium, headless_shell, node or pytest process is made again, 3 attempts or fewer, and
a run that is not quiet does not count for the acceptance).

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_default.py
"""

from __future__ import annotations

import gzip
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import canvas_frames as frames  # noqa: E402
import canvas_tree as tree_bench  # noqa: E402

BASE = "0254afb"
SMALL_LIMIT = 2048


def _small_pages() -> list[int]:
    """Give the bytes of the small page of each nested map of the M11 tree."""
    from systemap import canvas_redirect, nest  # noqa: PLC0415

    ids = [m["id"] for m in frames.m11_tree()["maps"] if m["id"]]
    pages = [
        canvas_redirect.page(
            nest.Map(id=i, path=Path("x"), rel="x", model=None, meaning=None, theme={})  # type: ignore[arg-type]
        )
        for i in ids
    ]
    return [len(p.encode("utf-8")) for p in pages]


def _run(page: Path, label: str) -> dict[str, Any]:
    return tree_bench.attempts(lambda: tree_bench._loads(page), label)


def _all_runs() -> list[dict[str, Any]]:
    """Give the runs of A and B in the order of `canvas_tree.ORDER`."""
    tree_bench.BASE = BASE
    with tempfile.TemporaryDirectory() as name:
        pages = tree_bench._pages(Path(name))
        for k, p in pages.items():
            raw = p.read_bytes()
            print(f"page {k}: {len(raw):,} raw, {len(gzip.compress(raw, 6)):,} gzip")
        runs: list[dict[str, Any]] = []
        count = {"A": 0, "B": 0}
        for which in tree_bench.ORDER:
            count[which] += 1
            runs.append(_run(pages[which], f"{which}{count[which]}"))
    return runs


def _ready(quiet: list[dict[str, Any]], which: str, rate: str) -> list[float]:
    """Give all load times of the quiet runs of A or B at one rate."""
    return [v for r in quiet if r["run"][0] == which for v in r[rate]["ready"]]


def main() -> int:
    if frames.node() is None:
        print(frames.missing())
        return 1
    small = _small_pages()
    print(f"small pages: {len(small)}, largest {max(small)} bytes")
    ok = max(small) <= SMALL_LIMIT
    quiet = [r for r in _all_runs() if r["quiet"]]
    for rate in ("1x", "4x"):
        med = {k: statistics.median(v) for k in ("A", "B") if (v := _ready(quiet, k, rate))}
        print(f"{rate}: median ready {med}")
    b1 = _ready(quiet, "B", "1x")
    ok &= bool(b1) and max(b1) <= frames.LOAD_LIMIT
    print("B 1x largest ready:", max(b1, default=None))
    print("quiet runs:", ", ".join(r["run"] for r in quiet) or "none")
    print("result:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
