"""L2: the flow labels and the lines of other flows, at the fit of the self-map.

L1 gives no label plate that goes into a different plate at 1440 x 900 pixels. But the
picture of the System context layer shows labels that are hard to read at the left of the
map. This script counts three possible causes. It changes no page code.

For each layer and screen size, at the fit, the script gives:

- `labels`: the count of drawn flow labels.
- `crossed`: the count of labels with a line of a different flow of the layer through the
  box of the text. A line goes through a box when a segment of the line has a part in the
  box after the box becomes 1 px smaller on each side.
- `lines`: the count of pairs of a label and such a line.
- `far`: the count of labels with a text box that is more than 4 px from each segment of
  the line of their flow.
- `near`: the count of pairs of labels with a gap of less than 4 px between their text
  boxes, in the two directions.
- `shift`: the largest distance in px between the center of a text box and the center of
  the label box of the page data. A large value shows an error in the method.

Acceptance values, written before the first run on 2026-11-16:

1. In the System context layer, at 1440 x 900 and at 1600 x 900 pixels: `crossed` is 0.
2. In the same layer and screens: `far` is 0 and `near` is 0.
3. `shift` is less than 2 px in each row. If not, the other values are not valid.

The other layers and screens have no acceptance value.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_label_lines.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import canvas_frames as frames  # noqa: E402
import canvas_labels  # noqa: E402

DRIVER = HERE / "canvas_label_lines.js"
SCREENS = ("1440x900", "1600x900")
SHIFT = 2.0


def _measure(page: Path) -> list[dict[str, Any]]:
    node = frames.node()
    if node is None:
        raise SystemExit(frames.missing())
    proc = subprocess.run(
        [node, str(DRIVER), str(page)], capture_output=True, text=True, check=False, timeout=300
    )
    if proc.returncode != 0:
        raise SystemExit(f"The driver stopped with an error:\n{proc.stderr}")
    rows: list[dict[str, Any]] = json.loads(proc.stdout)
    return rows


def main() -> int:
    with tempfile.TemporaryDirectory() as name:
        rows = _measure(canvas_labels._page(Path(name)))
    print("screen     layer    zoom   labels crossed lines  far near  shift")
    passed = True
    for r in rows:
        print(
            f"{r['screen']:10} {r['layer']:8} {r['zoom']:.3f} {r['labels']:7} {r['crossed']:7} "
            f"{r['lines']:5} {r['far']:4} {r['near']:4} {r['shift']:6.1f}"
        )
        valid = r["shift"] < SHIFT
        if not valid:
            print("    acceptance 3: FAIL")
        if r["layer"] == "system" and r["screen"] in SCREENS:
            one, two = r["crossed"] == 0, r["far"] == 0 and r["near"] == 0
            print(f"    acceptance 1: {'PASS' if one else 'FAIL'}, 2: {'PASS' if two else 'FAIL'}")
            for name in r["which"]:
                print(f"      {name}")
            passed = passed and one and two
        passed = passed and valid
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
