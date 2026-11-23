"""L1: why a flow of the nested map Page has no label at rest on the atlas page.

P1 of stage 2 of the open faults (tests/test_atlas_page_layout_browser.py): a label at rest
shows the full artifact, or it does not show. This script gives the measured reason for each
line of Page with no label at rest at the fit at 1440 x 900, in each layer tab. It uses the
driver of the test (tests/atlas_layout.js) and the test hook `seatWhy` of atlas_input.

For each line with no label at rest, the script gives:

- `w`: the width of the box of the full label, in map units (`seat` in atlas_lines).
- `need`: the length of a horizontal part that the box of the label must have, w + 18.
- `flat`: the length of the longest horizontal part of the line.
- the counts of `seatWhy` on the parts that are long enough: the places with a card, a
  name or an edge in the box (`wall`), with a different label (`taken`), with a different
  line (`crossed`), on a corner of the line (`own`), and free places. A free place shows
  only that a different order of the labels can give a place.

The lines of one neighbour with one artifact show one label at most (`labelKey`). Thus a
line of such a group has no label when a different line of the group has the label.

This script is a measurement with no acceptance value: it gives the reasons for a result
of P1. The acceptance values of P1 are in the test.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/atlas_page_labels.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_canvas_browser import browser  # noqa: E402

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, nest  # noqa: E402


def _flat(q: list[list[float]]) -> float:
    return max(
        (abs(b[0] - a[0]) for a, b in zip(q, q[1:], strict=False) if abs(a[1] - b[1]) < 0.01),
        default=0.0,
    )


def main() -> int:
    cfg = config.load(ROOT)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    page = next(m for m in data["maps"] if m["id"] == "Page")
    flows = page["flows"]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "self.html"
        out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
        proc = subprocess.run(
            [browser(), str(ROOT / "tests" / "atlas_layout.js"), str(out), "Page"],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
    got = json.loads(proc.stdout)
    print(f"zoom {got['zoom']}")
    for layer in got["layers"]:
        shown = {label["f"] for label in layer["labels"]}
        print(f"\n{layer['id']}: {layer['n']} lines, dense {layer['dense']}, {len(shown)} labels")
        if layer["dense"]:
            continue
        print("| flow | artifact | w | need | flat | wall | taken | crossed | own | free |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for lane in layer["lanes"]:
            if lane["f"] in shown or lane["w"] is None:
                continue
            f, why = flows[lane["f"]], lane["why"]
            print(
                f"| {f['s']} -> {f['t']} | {f['a']} | {lane['w']:.0f} | {lane['w'] + 18:.0f} | "
                f"{_flat(lane['q']):.0f} | {why['wall']} | {why['taken']} | {why['crossed']} | "
                f"{why['own']} | {why['free']} |"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
