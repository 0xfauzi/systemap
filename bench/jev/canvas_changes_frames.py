"""W2: C2 of the nested canvas design with the Changes view on (step 4, `page_canvas_changes`).

Acceptance value, written before the first run on 2026-11-07, from the section
"Performance" of docs/design/nested-canvas.md: with the Changes view on, the p95 frame
interval of each scenario below at 4 times CPU throttling is at most 35.0 ms (two 60 Hz
ticks plus 5 percent) in each quiet run of B. Pass or fail.

The script also gives the p95 of A in the same order of runs. A has no acceptance value. It
shows the state of the host for the comparison.

- A: the canvas page of commit d8ac070 (`canvas_page.build` from a copy of `src` of that
  commit, `git archive`), in the Map view. That page has no Changes view.
- B: the canvas page of the working tree, in the Changes view. The driver calls
  `systemapCanvas.setView('changes')` and starts the scenario 400 ms later, after the fade
  of the view. The driver gives the view at the end of the scenario. A run of B with a
  view that is not "changes" is a failure.

The data is the same for A and B: the generated data of `canvas_frames.py` with generated
change keys (`_changed`). In each map, each fifth card has changed source, each seventh
card has only changed tests, each ninth card imports changed source, the other ends of the
lost flows have the mark "end", and each flow from or to a card with changed source is
lost. Each card that opens a map is "changed inside". Each map has a revision comparison
(`ch`) and a roll-up record.

The scenarios at 4 times CPU throttling (`canvas_frames.js`, 180 frames each): the M11
shape (pan-fit, all-open, dive), 400 cards (pan-fit, dive) and 1,500 cards (pan-fit).

Order of the runs: A1, B1, B2, A2, A3, B3. Each run has each scenario one time, each in a
new browser. The quiet gate of `canvas_tree.py`: before each run, the script waits until no
chrome, chromium, headless_shell, node or pytest process that is not a descendant of this
script has operated for 30 s (900 s or less). During the run, it records such processes
each 2 s. A run with such a process in a sample is not quiet, and the script makes it
again, 3 attempts or fewer. A run that is not quiet after 3 attempts is given as "not
quiet", and its values do not count for the acceptance.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_changes_frames.py
"""

from __future__ import annotations

import json
import os
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
RATE = 4
LIMIT = 35.0
ORDER = ("A", "B", "B", "A", "A", "B")
CASES = (
    ("M11 shape", "pan-fit"),
    ("M11 shape", "all-open"),
    ("M11 shape", "dive"),
    ("400 cards", "pan-fit"),
    ("400 cards", "dive"),
    ("1,500 cards", "pan-fit"),
)


def _marked(m: dict[str, Any]) -> None:
    """Add the generated change keys to one map of the generated data."""
    ids = [c["id"] for c in m["cards"] if c.get("k") != "actor"]
    changed = set(ids[::5])
    tests = set(ids[3::7]) - changed
    imports = set(ids[1::9]) - changed - tests
    lost = [i for i, f in enumerate(m["flows"]) if {f["s"], f["t"]} & changed]
    ends = {end for i in lost for end in (m["flows"][i]["s"], m["flows"][i]["t"])}
    marks = {cid: "end" for cid in ends - changed - tests - imports}
    marks |= {cid: "changed" for cid in changed} | {cid: "tests" for cid in tests}
    marks |= {cid: "imports" for cid in imports}
    m["ch"] = {
        "base": "main",
        "head": "HEAD",
        "base_revision": "",
        "head_revision": "",
        "comparison_base": "",
        "direct": sorted(changed | tests),
        "adjacent": sorted(imports),
        "parts": {},
        "reach_known": True,
        "unparsed": [],
    }
    m["cm"] = {cid: marks[cid] for cid in sorted(marks)}
    if lost:
        m["cl"] = lost
    m["cr"] = {"n": 1, "w": "1 changed component", "b": 1}
    opens = sorted(c["id"] for c in m["cards"] if "o" in c)
    if opens:
        m["ci"] = opens


def _changed(data: dict[str, Any]) -> dict[str, Any]:
    for m in data["maps"]:
        _marked(m)
    return data


def _pages(tmp: Path) -> dict[str, dict[str, Path]]:
    """Write page A and page B of each data set with the same data and theme."""
    from systemap import config, nest  # noqa: PLC0415

    sets = {
        "M11 shape": _changed(frames.nested_tree()),
        "400 cards": _changed(frames.grid_map(400)),
        "1,500 cards": _changed(frames.grid_map(1500)),
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
        "t = json.loads(Path(sys.argv[1]).read_text()); "
        "Path(sys.argv[3]).write_text(canvas_page.build(t, json.loads(Path(sys.argv[2])"
        ".read_text())), encoding='utf-8')"
    )
    pages: dict[str, dict[str, Path]] = {"A": {}, "B": {}}
    for n, (name, data) in enumerate(sets.items()):
        source = tmp / f"data{n}.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        pages["A"][name] = tmp / f"A{n}.html"
        subprocess.run(
            [
                sys.executable,
                "-c",
                write,
                str(tmp / "theme.json"),
                str(source),
                str(pages["A"][name]),
            ],
            env={**os.environ, "PYTHONPATH": str(old / "src")},
            check=True,
            cwd=str(tmp),
        )
        pages["B"][name] = frames.write_page(data, tmp / f"B{n}.html")
    return pages


def _scenario(page: Path, mode: str, view: str) -> dict[str, Any]:
    found = frames.node()
    if found is None:
        raise RuntimeError(frames.missing())
    args = [found, str(frames.DRIVER), str(page), mode, str(RATE), str(frames.FRAMES)]
    proc = subprocess.run(
        [*args, view] if view else args, capture_output=True, text=True, timeout=600, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def _run(pages: dict[str, Path], which: str) -> dict[str, Any]:
    """Run each scenario one time, with a sample of the foreign processes each 2 s."""
    seen: list[str] = []
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.extend(gate._foreign())

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out: dict[str, Any] = {}
    try:
        for name, mode in CASES:
            found = _scenario(pages[name], mode, "changes" if which == "B" else "")
            out[f"{name} {mode}"] = {
                "p95": found["p95"],
                "median": found["median"],
                "max": found["max"],
                "view": found.get("view", "map"),
            }
    finally:
        done.set()
        watcher.join()
    out["foreign"] = sorted(set(seen))
    out["load"] = os.getloadavg()[0]
    return out


def _attempts(page: Path, which: str, n: int) -> dict[str, Any]:
    """Make run `which` n, again until it is quiet, in gate.ATTEMPTS attempts or fewer."""
    found: dict[str, Any] = {}
    for attempt in range(1, gate.ATTEMPTS + 1):
        waited = gate._gate()
        found = _run(page, which)
        found |= {"run": f"{which}{n}", "attempt": attempt, "waited": round(waited)}
        found["quiet"] = not found["foreign"]
        print(json.dumps(found), flush=True)
        if found["quiet"]:
            break
    return found


def _table(runs: list[dict[str, Any]]) -> None:
    print(
        "| Data | Scenario | "
        + " | ".join(r["run"] + ("" if r["quiet"] else " (not quiet)") for r in runs)
        + " |"
    )
    print("|---|---|" + "---|" * len(runs))
    for name, mode in CASES:
        key = f"{name} {mode}"
        print(f"| {name} | {mode} | " + " | ".join(f"{r[key]['p95']:.1f}" for r in runs) + " |")


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
            runs.append(_attempts(pages[which], which, count[which]))
    quiet = [r for r in runs if r["quiet"]]
    _table(runs)
    b_quiet = [r for r in quiet if r["run"][0] == "B"]
    ok = bool(b_quiet) and all(
        r[f"{name} {mode}"]["p95"] <= LIMIT and r[f"{name} {mode}"]["view"] == "changes"
        for r in b_quiet
        for name, mode in CASES
    )
    print("quiet runs:", ", ".join(r["run"] for r in quiet) or "none")
    print("result:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
