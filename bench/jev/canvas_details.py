"""S9: the reader tools and the Details panel of the canvas page (step 5, part B).

Acceptance values, written before the first run on 2026-11-08, from the task of the part
"parity of the tools and Details" of step 5 of docs/design/nested-canvas.md:

1. C1: the canvas data (`canvas_data.text`) of the real M11 tree (50 maps), with the new
   keys of `canvas_details`, is at most 2 MB (2,097,152 bytes) raw.
2. The page of the self-map of this repository grows by at most 40,000 bytes raw: the
   bytes of the page of B less the bytes of the page of A, for the same facts and model.
3. C2 of B. For each scenario below, in the variant `plain` (no selection, no panel) and
   `details` (a card selected with Tab and Enter, and the Details panel open with the D
   key): the p95 frame interval is at most 35.0 ms at 4 times CPU throttling and at most
   17.5 ms at normal CPU speed, in each quiet run of B.
4. A/B: for each scenario, variant and rate, the median of the p95 values of B is at most
   the median of A plus one tick (16.7 ms). A has no panel: it gets the same keys.
5. In each frame of each run of B, the count of seam calls is not more than the count of
   the cards and the flows that the frame draws (`over` <= 0), and the panel has 0 DOM
   changes during the move.

The scenarios are pan-fit, all-open and dive of the M11 shape (`canvas_frames.nested_tree`),
pan-fit and dive of the map of 400 cards, and pan-fit of the map of 1,500 cards
(`canvas_frames.grid_map`), with 180 frames each (`canvas_details.js`).

A is the canvas page of commit BASE (`canvas_page.build` from `git archive` of `src`). B is
the page of the work tree. The two pages have the same data and theme. The data of A is
the data of B without the new keys, so that the drawing has the same input.

Order of the runs: A1, B1, B2, A2, A3, B3, with the quiet gate of `canvas_tree.py`: before
each run, the script waits until no chrome, chromium, headless_shell, node or pytest process
that is not a descendant of this script has operated for 30 s (900 s or less). It samples
such processes each 2 s during the run. A run with such a process is not quiet, and the
script makes it again, 3 attempts or fewer. The values of a run that is not quiet do not
count for the acceptance.

The gate of this script also knows the processes that this script started and that are no
longer its descendants: a Chromium helper process that goes to PID 1 when its browser
closes. Each such process has the value of TOKEN in its environment (`_ours`). The first
run of this script (2026-11-08) did not have this part: its gate counted these helper
processes as foreign, and 8 of 9 attempts were not quiet (S9 in `bench/jev/README.md`).

Second use, written before its first run on 2026-11-08: after the merge of the parts A, B,
C and D of step 5, B is the merged work tree, with the same acceptance values 1 to 5 and
no change of the script. The merged renderer has the parts of A and C also. Thus this run
measures C2 of the merged page (S10 in `bench/jev/README.md`).

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_details.py
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

BASE = "0254afb"
DRIVER = HERE / "canvas_details.js"
TICK = 16.7
RAW_LIMIT = 2_097_152
GROWTH_LIMIT = 40_000
NEW_KEYS = ("mf", "ff", "iv", "ir", "md", "fr", "sr")
CASES = (
    ("M11 shape", "pan-fit"),
    ("M11 shape", "all-open"),
    ("M11 shape", "dive"),
    ("400 cards", "pan-fit"),
    ("400 cards", "dive"),
    ("1,500 cards", "pan-fit"),
)
VARIANTS = ("plain", "details")
WRITE = (
    "import json, sys; from pathlib import Path; from systemap import canvas_page; "
    "Path(sys.argv[3]).write_text(canvas_page.build(json.loads(Path(sys.argv[1]).read_text()),"
    " json.loads(Path(sys.argv[2]).read_text())), encoding='utf-8')"
)


TOKEN = "SYSTEMAP_BENCH_RUN"


def _ours(entry: str) -> bool:
    """Tell if the process of a line of `canvas_tree._foreign` has TOKEN of this run."""
    try:
        environ = Path(f"/proc/{entry.split()[0]}/environ").read_bytes()
    except OSError:
        return False
    return f"{TOKEN}={os.environ[TOKEN]}".encode() in environ.split(b"\0")


def _foreign(found: Any = tree._foreign) -> list[str]:
    """Give the foreign processes of `canvas_tree._foreign` without the processes of this run."""
    return [entry for entry in found() if not _ours(entry)]


def _old(tmp: Path) -> Path:
    """Give the folder with the `src` of BASE."""
    old = tmp / "a"
    old.mkdir()
    archive = subprocess.run(
        ["git", "-C", str(ROOT), "archive", BASE, "src"], capture_output=True, check=True
    )
    subprocess.run(["tar", "-x", "-C", str(old)], input=archive.stdout, check=True)
    return old / "src"


def _old_page(old: Path, theme: Path, data: dict[str, Any], out: Path) -> Path:
    src = out.with_suffix(".json")
    src.write_text(json.dumps(_without(data)), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", WRITE, str(theme), str(src), str(out)],
        env={**os.environ, "PYTHONPATH": str(old)},
        check=True,
        cwd=str(out.parent),
    )
    return out


def _without(data: dict[str, Any]) -> dict[str, Any]:
    """Give the data without the keys of `canvas_details`."""
    maps = [{k: v for k, v in m.items() if k not in NEW_KEYS} for m in data["maps"]]
    return {**data, "maps": maps}


def sizes(tmp: Path, old: Path) -> bool:
    """Print C1 of the M11 tree and the growth of the self-map page (acceptance 1 and 2)."""
    from systemap import canvas_data, canvas_page, config, facts_file, nest  # noqa: PLC0415

    m11 = frames.m11_tree()
    raw = len(canvas_data.text(m11).encode())
    print(
        f"C1 M11 tree: {raw:,} bytes raw ({len(canvas_data.text(_without(m11)).encode()):,} without the new keys)"
    )
    cfg = config.load(ROOT)
    nested = nest.load(cfg)
    data = canvas_data.build(cfg, nested, facts_file.read_facts(cfg.facts_path, cfg.root))
    theme = tmp / "self-theme.json"
    theme.write_text(json.dumps(canvas_page.tree_theme(cfg, nested)), encoding="utf-8")
    b = len(canvas_page.build(canvas_page.tree_theme(cfg, nested), data).encode())
    a = _old_page(old, theme, data, tmp / "self-a.html").stat().st_size
    print(f"self-map page: A {a:,} bytes, B {b:,} bytes, growth {b - a:,} bytes")
    return raw <= RAW_LIMIT and b - a <= GROWTH_LIMIT


def _pages(tmp: Path, old: Path) -> dict[str, dict[str, Path]]:
    from systemap import config, nest  # noqa: PLC0415

    data = {
        "M11 shape": frames.nested_tree(),
        "400 cards": frames.grid_map(400),
        "1,500 cards": frames.grid_map(1500),
    }
    theme = tmp / "theme.json"
    theme.write_text(json.dumps(nest.load(config.load(ROOT)).top.theme), encoding="utf-8")
    pages: dict[str, dict[str, Path]] = {"A": {}, "B": {}}
    for k, (name, value) in enumerate(data.items()):
        pages["A"][name] = _old_page(old, theme, value, tmp / f"A{k}.html")
        pages["B"][name] = frames.write_page(value, tmp / f"B{k}.html")
    return pages


def _run(page: Path, mode: str, rate: int, variant: str) -> dict[str, Any]:
    node = frames.node()
    if node is None:
        raise RuntimeError(frames.missing())
    proc = subprocess.run(
        [node, str(DRIVER), str(page), mode, str(rate), variant],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def _measure(pages: dict[str, Path]) -> dict[str, Any]:
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(_foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out: dict[str, Any] = {"cases": {}}
    try:
        for rate in (4, 1):
            for name, mode in CASES:
                for variant in VARIANTS:
                    key = f"{name}|{mode}|{variant}|{rate}"
                    out["cases"][key] = _run(pages[name], mode, rate, variant)
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    out["loadavg"] = os.getloadavg()[0]
    return out


def _row(quiet: list[dict[str, Any]], name: str, mode: str, variant: str, rate: int) -> bool:
    """Print the row of one case and tell if it passes acceptance 3, 4 and 5."""
    key = f"{name}|{mode}|{variant}|{rate}"

    def of(which: str, field: str) -> list[Any]:
        return [r["cases"][key][field] for r in quiet if r["run"][0] == which]

    a, b, over, writes = of("A", "p95"), of("B", "p95"), of("B", "over"), of("B", "writes")
    diff = statistics.median(b) - statistics.median(a) if a and b else None
    good = bool(b) and max(b) <= frames.LIMITS[rate] and diff is not None and diff <= TICK
    good = good and all(v is not None and v <= 0 for v in over)
    good = good and all(w == 0 for w in writes)
    if variant == "details":
        good = good and all(of("B", "open"))
    shown = "" if diff is None else f"{diff:+.1f}"
    print(
        f"| {name} | {mode} | {variant} | {rate}x | {', '.join(map(str, a))} | "
        f"{', '.join(map(str, b))} | {shown} | {max(over, default=None)} | "
        f"{max(writes, default=None)} | {'pass' if good else 'fail'} |"
    )
    return good


def _verdict(runs: list[dict[str, Any]]) -> bool:
    quiet = [r for r in runs if r["quiet"]]
    ok = any(r["run"][0] == "B" for r in quiet) and any(r["run"][0] == "A" for r in quiet)
    print(
        "| Data | Scenario | Variant | CPU | A p95 | B p95 | Median B - A | B over | B writes | Result |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    for rate in (4, 1):
        for name, mode in CASES:
            for variant in VARIANTS:
                ok &= _row(quiet, name, mode, variant, rate)
    return ok


def main() -> int:
    if frames.node() is None:
        print("failure: " + frames.missing())
        return 1
    os.environ[TOKEN] = str(os.getpid())
    tree._foreign = _foreign
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        old = _old(tmp)
        ok = sizes(tmp, old)
        pages = _pages(tmp, old)
        runs: list[dict[str, Any]] = []
        count = {"A": 0, "B": 0}
        for which in tree.ORDER:
            count[which] += 1
            runs.append(
                tree.attempts(functools.partial(_measure, pages[which]), f"{which}{count[which]}")
            )
        print("quiet runs:", ", ".join(r["run"] for r in runs if r["quiet"]) or "none")
        ok = _verdict(runs) and ok
        print("result:", "pass" if ok else "fail")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
