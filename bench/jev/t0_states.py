"""T0 C4: the fill of the board of the States view at 1440 x 900, and the label distance.

The board of a state machine has a scale of SM_MAX (1.25) or less (`smDraw` in
`atlas_states`): the scale is the smallest of SM_MAX, the fit of the width and the fit of the
height of the free part of the screen. This script measures, for each state machine of the
self map and of the test fixtures that have one, at 1440 x 900 (bench/jev/t0_states.js):

- the scale and the share of the width and of the height of the free part that the board
  fills, at the caps 1.25 (today), 1.4, 1.6 and 2.0, and with no cap (the scale is then the
  smaller of the two fits);
- the value that binds: the cap, the width fit or the height fit;
- for each transition, the distance of its label box to its line and of the label centre
  to its line, in CSS px. The script gives the largest of each machine.

The machines: the two machines of the self map, and the machines of
tests/test_atlas_states_browser.py ("Life of a job" from `states.layout`, "A row", "Many
lines", and the machines of the nested fixture, "Life of a token" and "Life of a request").
All are put in the top map of the self map in the page data, as `probe_page` of that test
does with the first three.

This is a baseline measurement for the targets of stages 3 and 4 of the open faults. It has
no acceptance value.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/t0_states.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import t0_common as common  # noqa: E402

DRIVER = HERE / "t0_states.js"
CAPS = ("1.25", "1.4", "1.6", "2.0", "inf")


def _machines() -> list[dict[str, Any]]:
    import test_atlas_states_browser as t  # noqa: PLC0415

    return [t._job(), t.ROW_MACHINE, t.LINES_MACHINE, t.TOP_MACHINE, t.INNER_MACHINE]


def _row(r: dict[str, Any]) -> str:
    cap = r["cap"] if r["cap"] is not None else float("inf")
    low = min(cap, r["kW"], r["kH"])
    binds = "cap" if low == cap else "width" if r["kW"] <= r["kH"] else "height"
    box = max((x["box"] for x in r["labels"]), default=0.0)
    centre = max((x["centre"] for x in r["labels"]), default=0.0)
    return (
        f"| {'none' if cap == float('inf') else cap} | {r['scale']:.3f} | {binds} | "
        f"{r['kW']:.3f} | {r['kH']:.3f} | {r['w'] / r['aw']:.2f} | "
        f"{r['h'] / r['ah']:.2f} | {box:.1f} | {centre:.1f} |"
    )


def report(out: dict[str, Any]) -> None:
    """Print one table for each machine."""
    for m in out["machines"]:
        print(f"\n### {m['k']}: {m['n']}")
        print(
            "| Cap | Scale | Binds | Width fit | Height fit | Fill of width | Fill of height | "
            "Largest label box to line (px) | Largest label centre to line (px) |"
        )
        print("|---|---|---|---|---|---|---|---|---|")
        for r in m["runs"]:
            print(_row(r))


def main() -> int:
    theme, data = common.self_data()
    data["maps"][0]["sm"] = list(data["maps"][0]["sm"]) + _machines()
    with tempfile.TemporaryDirectory() as tmp:
        html = common.write(Path(tmp) / "states.html", theme, data)
        report(common.drive(DRIVER, str(html), ",".join(CAPS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
