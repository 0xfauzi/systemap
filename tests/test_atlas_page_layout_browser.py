"""The layout of the nested map Page on the atlas page, in a browser (stage 2 of the open faults).

The test drives the atlas page of the map of this repository at 1440 x 900 in the Chromium of
Playwright (tests/atlas_layout.js), with the hash #Page: the fit of the nested map Page. The
test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required". Then it fails.

Acceptance values, written by the coordinator before the work on 2026-11-20, with no change:

P1. On #Page at the fit at 1440 x 900, in each layer, no flow label at rest is cut with an
    ellipsis, and the label of a flow shows at most one time.
P2. On #Page, each line between a neighbour and a part has a length of 1.5 times the
    Manhattan distance between its two ends or less.
P3. At 1440 x 900 the fit of #Page is 90 percent or more, and the box of the map with the
    headline covers 60 percent or more of the width of the map area.

Acceptance value E1, written on 2026-11-20 for the second repair of stage 2 of the open faults,
before the first run of its test. A review saw the line Model -> PageWriter along the top edge
of the frame of Page and the line "name, paths" along its right edge:

E1. On #Page at 1440 x 900, in each layer tab, no part of a line is on an edge of the frame
    of the map: a part with one axis value that is less than 7 map units from the axis
    value of an edge, and that overlaps the range of that edge by more than 2 map units, is
    on the edge. The frame is the box of the container `part` of the page data.

Acceptance value L3, written on 2026-11-20 for the third repair of stage 2 of the open faults,
before the first run of its test. A review saw the full label of the lines of Judgement,
"uncovered entry points, assurance levels, boundary findings", across a vertical part of one
of its lines below the frame, with no visible attachment to one line:

L3. On #Page at 1440 x 900, in each layer tab, a label at rest whose centre is on a vertical
    part of its line has a screen box that is 8 times its height wide or less. The test also
    holds that the box of each label at rest has its centre on its own line.

How the test reads these values (written before the first run of this test):

- P1: a label at rest is an item of `labels` of `systemapCanvas.lines('Page')` in each layer
  tab. A label is cut when its text is not the full artifact of its flow, or when it ends
  with "...". In a nested map, the lines of one neighbour with one artifact in one direction
  are the parts of one flow of the map above: these lines show one label or no label. Each
  other flow shows one label or no label.
- P2: a line is the laned points of the line in the layer tab (`lanes`, map units). Its
  length is the sum of the lengths of its parts, and its two ends are its first point and
  its last point. The test also holds the same limit for the Manhattan distance between the
  centres of the two cards, as a second measure.
- P3: the fit is the number of the zoom control at the fit. The box of the map is the
  screen box of the frame of the map Page at the fit (`systemapCanvas.frame`). The map area
  is the full width of the screen, because no details panel is open at the fit. The
  headline is at the left of the map or above it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_browser import browser

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, nest

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_layout.js"
REPO = ROOT.parent


@pytest.fixture(scope="module")
def page_data() -> dict[str, Any]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    return {"cfg": cfg, "tree": tree, "data": data}


@pytest.fixture(scope="module")
def run(page_data: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    out = tmp_path_factory.mktemp("layout") / "self.html"
    theme = canvas_page.tree_theme(page_data["cfg"], page_data["tree"])
    out.write_text(atlas_page.build(theme, page_data["data"]), encoding="utf-8")
    proc = subprocess.run(
        [browser(), str(DRIVER), str(out), "Page"], capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, proc.stderr
    got = dict(json.loads(proc.stdout))
    assert got["errors"] == [], got["errors"]
    assert got["current"] == "Page"
    return got


def _page(page_data: dict[str, Any]) -> dict[str, Any]:
    return next(m for m in page_data["data"]["maps"] if m["id"] == "Page")


def test_a_label_at_rest_is_full_and_shows_one_time(
    run: dict[str, Any], page_data: dict[str, Any]
) -> None:
    """P1."""
    page = _page(page_data)
    flows = page["flows"]
    kind = {c["id"]: c["k"] for c in page["cards"]}
    shown = 0
    for layer in run["layers"]:
        keys: list[Any] = []
        for label in layer["labels"]:
            f = flows[label["f"]]
            assert label["s"] == f["a"], (layer["id"], label)
            assert not label["s"].endswith("..."), (layer["id"], label)
            if kind[f["s"]] == "actor":
                keys.append((">", f["s"], f["a"]))
            elif kind[f["t"]] == "actor":
                keys.append(("<", f["t"], f["a"]))
            else:
                keys.append(label["f"])
        assert len(keys) == len(set(keys)), (layer["id"], keys)
        shown += len(keys)
    assert shown > 0


def _length(q: list[list[float]]) -> float:
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(q, q[1:], strict=False))


def test_a_neighbour_line_has_no_long_way_round(
    run: dict[str, Any], page_data: dict[str, Any]
) -> None:
    """P2."""
    page = _page(page_data)
    flows = page["flows"]
    cards = {c["id"]: c for c in page["cards"]}
    checked = 0
    for layer in run["layers"]:
        for lane in layer["lanes"]:
            f = flows[lane["f"]]
            if "actor" not in (cards[f["s"]]["k"], cards[f["t"]]["k"]):
                continue
            q = lane["q"]
            ends = abs(q[-1][0] - q[0][0]) + abs(q[-1][1] - q[0][1])
            assert _length(q) <= 1.5 * ends, (layer["id"], f["s"], f["t"], q)
            a, b = (cards[f["s"]]["b"], cards[f["t"]]["b"])
            middle = abs(a[0] + a[2] / 2 - b[0] - b[2] / 2) + abs(a[1] + a[3] / 2 - b[1] - b[3] / 2)
            assert _length(q) <= 1.5 * middle, (layer["id"], f["s"], f["t"], q)
            checked += 1
    assert checked >= 32


def test_the_fit_of_page_is_large(run: dict[str, Any]) -> None:
    """P3."""
    assert run["zoom"] is not None
    assert int(run["zoom"][:-1]) >= 90, run["zoom"]
    x, _y, w, _h = run["frame"]
    assert 0 <= x and x + w <= run["width"]
    assert w >= 0.6 * run["width"], (run["frame"], run["width"])


def _on_edge(q: list[list[float]], frame: list[float]) -> list[tuple[float, ...]]:
    """Give each part of a line that is on an edge of the frame (E1)."""
    fx, fy, fw, fh = frame
    out = []
    for a, b in zip(q, q[1:], strict=False):
        for ax in (0, 1):
            if abs(a[ax] - b[ax]) > 0.01:
                continue
            lo, hi = sorted((a[1 - ax], b[1 - ax]))
            start, size = (fy, fh) if ax == 0 else (fx, fw)
            if min(hi, start + size) - max(lo, start) <= 2:
                continue
            edges = (fx, fx + fw) if ax == 0 else (fy, fy + fh)
            if any(abs(a[ax] - e) < 7 for e in edges):
                out.append((ax, a[ax], lo, hi))
    return out


def test_no_line_is_on_the_edge_of_the_frame(
    run: dict[str, Any], page_data: dict[str, Any]
) -> None:
    """E1."""
    page = _page(page_data)
    frame = next(b["b"] for b in page["boxes"] if b["id"] == "part")
    parts = 0
    for layer in run["layers"]:
        for lane in layer["lanes"]:
            assert not _on_edge(lane["q"], frame), (layer["id"], lane["f"], lane["q"])
            parts += len(lane["q"]) - 1
    assert parts > 0


def _part_at(q: list[list[float]], x: float, y: float) -> str | None:
    """Give "flat" or "upright" for the part of line q through the point, or None."""
    for a, b in zip(q, q[1:], strict=False):
        if abs(a[1] - b[1]) < 0.01 and abs(y - a[1]) < 0.5:
            if min(a[0], b[0]) - 0.5 <= x <= max(a[0], b[0]) + 0.5:
                return "flat"
        if abs(a[0] - b[0]) < 0.01 and abs(x - a[0]) < 0.5:
            if min(a[1], b[1]) - 0.5 <= y <= max(a[1], b[1]) + 0.5:
                return "upright"
    return None


def test_a_long_label_is_not_across_a_vertical_line(run: dict[str, Any]) -> None:
    """L3."""
    for layer in run["layers"]:
        lanes = {lane["f"]: lane["q"] for lane in layer["lanes"]}
        for label in layer["labels"]:
            part = _part_at(lanes[label["f"]], label["mx"], label["my"])
            assert part is not None, (layer["id"], label)
            x0, y0, x1, y1 = label["box"]
            if part == "upright":
                assert x1 - x0 <= 8 * (y1 - y0), (layer["id"], label)
