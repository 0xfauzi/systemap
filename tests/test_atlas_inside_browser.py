"""The signs of a nested map on the atlas page, in a browser (docs/design/atlas.md, stage 11).

The test drives the atlas page of the map of this repository (the nested map Page) and of the
generated M11 tree (bench/jev/canvas_frames.py, three depths: P0, P0/Q0 and P0/Q0/Deep) in the
Chromium of Playwright (tests/atlas_inside.js). The test skips when Node or the Playwright
package is not there, except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The
test of axe-core skips when axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written by the coordinator before the work on 2026-11-19, with no change:

A1. In each nested map, at 1440 x 900 and 390 x 844, light and dark: the bar is fully in the
    viewport at the fit, its text is 14 px or more on the screen, and its text contrast is
    4.5:1 or more.
A2. The back button works with a mouse click, with Enter when it has the focus, and with Esc.
    Each goes to the parent map with the card of the nested map selected.
A3. The top map has no bar, no locator and no inside background.
A4. The enter movement and the leave movement each take 250 ms to 450 ms, measured in the
    browser, and the first frame of the enter movement shows the nested map at the box of its
    card (within 8 px). With prefers-reduced-motion: reduce, each takes 0 ms (one frame).
A5. At the fit, at 1440 x 900 and 390 x 844, the locator covers no card and no label box of
    the nested map.
A6. The background outside the frame of a nested map differs from the top map background in
    each scheme (a different color value, and a measurable difference in a screenshot).
A7. The title of the frame is 18 px or more on the screen at the fit at 1440 x 900.
A8. axe-core gives no violation on a nested map, light and dark.

How the test reads these values (written before the first run of this test):

- "At the fit" is the camera after a load with the hash of the map (`fitBox` of its frame).
- A1: each element of the bar with its own text gives its computed font size and the contrast
  of its color on the first ground under it that is not transparent.
- A2: also a click on the locator (sign 3: a click on it goes out).
- A4: a movement is the time from the call of the movement to its last frame (`moves` of
  `systemapCanvas.inside`). The nested map has the shape of its own frame, and the box of its
  card has the shape of the card. Thus "at the box of its card" is: in the first frame of the
  enter movement, the frame of the nested map is in the box of the card with a margin of 8 px,
  its middle is 8 px or less from the middle of the card, and its width or its height is the
  width or the height of the card, within 8 px.
- A5: the locator also shows (it is not absent) in each nested map at 1440 x 900.
- A6: "a measurable difference in a screenshot" is the mean color of a box of 16 x 16 px of the
  canvas at the bottom middle of the screen: the mean of one channel differs by 3 or more
  between the top map and the nested map.
- A7: the title text of the frame of the current map in the frame log (`drawn`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, nest

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_inside.js"
REPO = ROOT.parent
BENCH = REPO / "bench" / "jev"
M11_PATH = "P0,P0/Q0,P0/Q0/Deep"


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=900
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    out = tmp_path_factory.mktemp("inside") / "self.html"
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def m11_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    browser()
    sys.path.insert(0, str(BENCH))
    import canvas_frames  # noqa: PLC0415  (a script in bench/jev)

    data = canvas_frames.m11_tree()
    out = tmp_path_factory.mktemp("inside") / "m11.html"
    out.write_text(atlas_page.build(nest.load(config.load(REPO)).top.theme, data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def signs(self_page: Path, m11_page: Path) -> list[dict[str, Any]]:
    out = []
    for name, page, maps in (("self", self_page, "Page"), ("m11", m11_page, M11_PATH)):
        out += [{**r, "page": name} for r in _drive("--signs", str(page), maps)["runs"]]
    return out


def _nested(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in runs if r["id"]]


def _over(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def test_the_bar_is_in_view_and_readable(signs: list[dict[str, Any]]) -> None:
    """A1."""
    assert len(_nested(signs)) == 16
    for r in _nested(signs):
        where = (r["scheme"], r["width"], r["id"])
        assert r["current"] == r["id"], where
        x, y, w, h = r["inside"]["bar"]["box"]
        assert x >= 0 and y >= 0 and x + w <= r["width"] and y + h <= r["height"], where
        name = r["id"].split("/")[-1]
        assert f"Inside {name}" in r["inside"]["bar"]["text"], where
        assert "Back to " in r["inside"]["bar"]["text"] and "Esc" in r["inside"]["bar"]["text"]
        assert r["bar"], where
        for t in r["bar"]:
            assert t["size"] >= 14, (where, t)
            assert t["ratio"] >= 4.5, (where, t)
        if "/" in r["id"]:
            for part in ["fifty maps", *r["id"].split("/")]:
                assert part in [t["text"] for t in r["bar"]], (where, part)


def test_the_top_map_has_no_sign(signs: list[dict[str, Any]]) -> None:
    """A3."""
    tops = [r for r in signs if not r["id"]]
    assert len(tops) == 8
    for r in tops:
        assert r["inside"]["bar"] is None and r["inside"]["loc"] is None
        assert r["inside"]["ground"] == r["inside"]["top"]


def test_the_locator_covers_no_card_and_no_label(signs: list[dict[str, Any]]) -> None:
    """A5."""
    for r in _nested(signs):
        where = (r["scheme"], r["width"], r["id"])
        loc = r["inside"]["loc"]
        if r["width"] == 1440:
            assert loc is not None, where
        if loc is None:
            continue
        box = [loc["x"], loc["y"], loc["x"] + loc["w"], loc["y"] + loc["h"]]
        for c in r["cards"]:
            b = c["b"]
            assert not _over(box, [b[0], b[1], b[0] + b[2], b[1] + b[3]]), (where, c["id"])
        for lab in r["labels"]:
            assert not _over(box, lab), (where, lab)


def test_the_ground_of_a_nested_map_differs(signs: list[dict[str, Any]]) -> None:
    """A6."""
    tops = {(r["page"], r["scheme"], r["width"]): r for r in signs if not r["id"]}
    for r in _nested(signs):
        top = tops[(r["page"], r["scheme"], r["width"])]
        assert r["inside"]["ground"] != top["inside"]["ground"], r["id"]
        diff = max(abs(a - b) for a, b in zip(r["ground"], top["ground"], strict=True))
        assert diff >= 3, (r["scheme"], r["width"], r["id"], r["ground"], top["ground"])


def test_the_frame_has_a_large_title(signs: list[dict[str, Any]]) -> None:
    """A7."""
    for r in [r for r in _nested(signs) if r["width"] == 1440]:
        own = [t for t in r["titles"] if t["map"] == r["id"]]
        assert own and own[0]["s"] == r["id"].split("/")[-1], r["id"]
        drawn = [t for t in r["titleTexts"] if t["s"] == own[0]["s"]]
        assert drawn and max(t["size"] for t in drawn) >= 18, (r["id"], drawn)


def test_a_neighbour_names_the_map_above(signs: list[dict[str, Any]]) -> None:
    """Sign 5: a neighbour card has the line "on" and the name of the map above."""
    page = [r for r in _nested(signs) if r["id"] == "Page" and r["width"] == 1440]
    assert page and {u["s"] for u in page[0]["ups"]} == {"on systemap"}
    assert len(page[0]["ups"]) == 10


def _check_moves(steps: list[dict[str, Any]], card: str, parent: str, reduced: bool) -> None:
    for st in steps:
        move = st["moves"][-1]
        ms = move["t1"] - move["t0"]
        if reduced:
            assert ms == 0, st
        else:
            assert 250 <= ms <= 450, (st["step"], ms)
        if st["step"].startswith("leave"):
            assert move["kind"] == "leave"
            assert st["current"] == parent, st
            assert st["sel"] == {"map": parent, "id": card}, st
            assert st["bar"] == bool(parent), st
        else:
            assert move["kind"] == "enter"
            if not reduced:
                _at_card_box(move["first"])


def _at_card_box(first: dict[str, list[float]]) -> None:
    f, c = first["frame"], first["card"]
    assert f[0] >= c[0] - 8 and f[1] >= c[1] - 8, first
    assert f[0] + f[2] <= c[0] + c[2] + 8 and f[1] + f[3] <= c[1] + c[3] + 8, first
    assert abs(f[0] + f[2] / 2 - c[0] - c[2] / 2) <= 8, first
    assert abs(f[1] + f[3] / 2 - c[1] - c[3] / 2) <= 8, first
    assert abs(f[2] - c[2]) <= 8 or abs(f[3] - c[3]) <= 8, first


@pytest.mark.parametrize("mode", ["--move", "--reduced"])
def test_back_esc_and_the_movements_on_page(self_page: Path, mode: str) -> None:
    """A2 and A4 on the nested map Page."""
    out = _drive(mode, str(self_page), "Page")
    assert [s["step"] for s in out["steps"]] == [
        "enter Page",
        "leave esc",
        "leave click",
        "leave enter",
        "leave locator",
    ]
    _check_moves(out["steps"], "Page", "", mode == "--reduced")


@pytest.mark.parametrize("mode", ["--move", "--reduced"])
def test_back_esc_and_the_movements_at_depth_two(m11_page: Path, mode: str) -> None:
    """A2 and A4 at depth 2 of the M11 tree: out of P0/Q0 to P0, with Q0 selected."""
    out = _drive(mode, str(m11_page), "P0,P0/Q0")
    _check_moves(out["steps"], "Q0", "P0", mode == "--reduced")
    assert out["steps"][1]["current"] == "P0/Q0"


def test_axe_finds_no_violation_in_a_nested_map(self_page: Path, m11_page: Path) -> None:
    """A8."""
    for page, map_id in ((self_page, "Page"), (m11_page, "P0/Q0/Deep")):
        out = _drive("--axe", str(page), map_id)
        if out["runs"] is None:
            no_axe("the test needs axe-core on NODE_PATH")
        assert len(out["runs"]) == 4
        for r in out["runs"]:
            assert r["current"] == map_id and r["violations"] == [] and r["errors"] == [], r
