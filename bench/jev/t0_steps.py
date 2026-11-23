"""T0 C2: the step labels of the Sequences view that cross the edge of a region or a surface.

The atlas page lets a label of a sequence cross the edge of a surface or of a region tint
when it has no place on one ground (`m._walls0` in `atlas_lines`). This script measures, on
the self map and on the workspace fixture at 1440 x 900, for each map with sequences, each
sequence and each step (and the whole route, step 0 in the output is "whole"):

- the labels that show in the frame of that step, and the labels among them that cross an
  edge (the box of the label is on one of the edge boxes of `walls`);
- for each such label, a search of its full line (bench/jev/t0_steps.js): the count of
  places at each half map unit of each part of the line, on the line and beside it, that
  are on one ground with no card, no name and no other label of the frame (`free`), and
  the count of those places that also have no other line through them (`clean`).

A crossing label with a free place is a label that a full-line search can move to one
ground. A crossing label with no free place needs a different solution, for example a plate.
The script counts both, for each step and for each different label (map, sequence, flow).

This is a baseline measurement for the targets of stages 3 and 4 of the open faults. It has
no acceptance value.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/t0_steps.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import t0_common as common  # noqa: E402

DRIVER = HERE / "t0_steps.js"


def _cells(st: dict[str, Any]) -> str:
    step = "whole" if st["n"] < 0 else str(st["n"] + 1)
    return f"{step}: " + "; ".join(
        f"flow {c['f']} '{c['s']}'{' (step only)' if c['hide'] else ''} "
        f"free {c['free']}, clean {c['clean']} of {c['places']}"
        for c in st["cross"]
    )


def _sequence(mid: str, j: dict[str, Any]) -> None:
    total = sum(len(st["cross"]) for st in j["steps"])
    print(
        f"- map {mid}, sequence {j['k']} '{j['n']}': {len(j['steps']) - 1} "
        f"steps, labels that cross an edge in all frames: {total}"
    )
    for st in j["steps"]:
        if st["cross"]:
            print(f"    {_cells(st)}")


def report(page: str, out: dict[str, Any]) -> None:
    """Print the values of one page."""
    steps = [(m["id"] or "top", j, st) for m in out["maps"] for j in m["seqs"] for st in j["steps"]]
    for m in out["maps"]:
        for j in m["seqs"]:
            _sequence(m["id"] or "top", j)
    _summary(page, steps)


def _summary(page: str, steps: list[tuple[str, dict[str, Any], dict[str, Any]]]) -> None:
    cross = [(mid, j["k"], c) for mid, j, st in steps for c in st["cross"]]
    free = sum(1 for _, _, c in cross if c["free"] > 0)
    clean = sum(1 for _, _, c in cross if c["clean"] > 0)
    unique: dict[tuple[str, int, int], list[bool]] = {}
    for mid, k, c in cross:
        unique.setdefault((mid, k, c["f"]), []).append(c["free"] > 0)
    fixable = sum(1 for v in unique.values() if all(v))
    plate = sum(1 for v in unique.values() if not any(v))
    shown = sum(st["labels"] for _, _, st in steps)
    print(
        f"\n{page} total: {len(steps)} frames, {shown} shown labels, {len(cross)} crossing "
        f"labels; with a free place on the full line {free}, with a clean place {clean}, with "
        f"no free place {len(cross) - free}"
    )
    print(
        f"{page} different crossing labels (map, sequence, flow): {len(unique)}; a free place "
        f"in each frame {fixable}; no free place in any frame {plate}; mixed "
        f"{len(unique) - fixable - plate}"
    )


def main() -> int:
    inputs = {"self": common.self_data(), "workspace": common.workspace_data()}
    with tempfile.TemporaryDirectory() as tmp:
        for page, (theme, data) in inputs.items():
            print(f"\n## {page}")
            html = common.write(Path(tmp) / f"{page}.html", theme, data)
            report(page, common.drive(DRIVER, str(html)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
