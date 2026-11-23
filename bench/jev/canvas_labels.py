"""L1: the flow labels of the canvas page at the fit of the self-map.

Before this work, the font size of a flow label is 10.5 px multiplied by the zoom, and a
label does not show below 8 px. At 1440 x 900 pixels, the fit of the self-map has the zoom
0.751. Thus the labels do not show at the fit. The change gives the labels a smallest font
size at the zooms near the fit (`labelSize` in `page_canvas_draw`).

Acceptance values, written before the first run on 2026-11-15:

1. At 1440 x 900 pixels, at the fit of the self-map of this repository, in each of the
   layers System context, Data flow, Control flow and Map review: each flow of the layer
   that has a label box has a drawn label with an alpha of 0.99 or more and a font size
   of 9 px or more.
2. In each of these four layers, at 1440 x 900, the count of label plates that go into a
   card and the count of pairs of label plates that go into each other, at the fit, is
   not more than the same count at the zoom 1. A box goes into a different box when the
   two boxes overlap by more than 2 px in width and in height.
3. The script gives the same values for the layer All at 1440 x 900, and for each layer at
   1366 x 768 and at 1280 x 720 pixels. These values have no acceptance value.
   Added after the first run on 2026-11-15: the script also gives the count of all drawn
   labels, and the smallest alpha and the smallest font size of these labels.

A label plate is the box that `plates` of `page_canvas_draw` gives: the width of the text
and 6 px, and 1.5 times the font size. The script calculates it from the text box that
`systemapCanvas.texts()` gives for each text with the font weight 500. Only a flow label
has that weight. The page runs with reduced motion, so no value is in a fade.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_labels.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_frames as frames  # noqa: E402

DRIVER = HERE / "canvas_labels.js"
ACCEPTED = ("system", "data", "control", "judge")
SIZE = 9.0
ALPHA = 0.99  # the value of acceptance 1


def _page(tmp: Path) -> Path:
    """Write the canvas page of the self-map of the working tree into `tmp`."""
    from systemap import config, facts_file, nest, render_pages  # noqa: PLC0415

    cfg = config.load(ROOT)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not facts:
        raise SystemExit("The committed facts are necessary. Run: systemap refresh")
    _top, html = render_pages.pages(cfg, nest.load(cfg), facts)[0]
    out = tmp / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


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


def _ok(row: dict[str, Any], base: dict[str, Any]) -> bool:
    return (
        row["full"] == row["boxed"]
        and (row["min_size"] or 0) >= SIZE
        and row["in_card"] <= base["in_card"]
        and row["in_plate"] <= base["in_plate"]
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as name:
        rows = _measure(_page(Path(name)))
    at_one = {(r["screen"], r["layer"]): r for r in rows if r["at"] == "zoom 1"}
    print(
        "screen     layer    at      zoom   boxed full  min px  in card  in plate  drawn  alpha  px"
    )
    passed = True
    for r in rows:
        print(
            f"{r['screen']:10} {r['layer']:8} {r['at']:7} {r['zoom']:.3f} {r['boxed']:6} "
            f"{r['full']:4} {r['min_size'] or 0:7.1f} {r['in_card']:8} {r['in_plate']:9}"
            f"{r['drawn']:7} {r['alpha']:6.2f} {r['size']:4.1f}"
        )
        if r["screen"] == "1440x900" and r["at"] == "fit" and r["layer"] in ACCEPTED:
            good = _ok(r, at_one[(r["screen"], r["layer"])])
            passed = passed and good
            print(f"    acceptance 1 and 2 for {r['layer']}: {'PASS' if good else 'FAIL'}")
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
