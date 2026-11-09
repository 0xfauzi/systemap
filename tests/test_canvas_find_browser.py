"""The Find dialog of the canvas page in a browser (`page_canvas_find`).

The test drives the real canvas page in the Chromium of Playwright (tests/canvas_find.js).
The pages are the canvas page of the fixture of tests/test_nest_join.py (the card Gateway
opens a map) and the generated M11 shape (bench/jev/canvas_frames.py: 50 maps on 4
levels). The test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required" (the CI job canvas-browser).

Acceptance values, written before the first run on 2026-11-07:

1. With the camera at the fit of the top map of the M11 shape, the text "C5" gives the card
   C5 of the level-3 map P0/A0/B0 as the first row of the group "Other maps", with the
   hint "in P0/A0/B0". Enter on that row moves the camera in a flight. When the camera
   stops, the box of the card is in the free box of the screen (the screen less the bands
   of the fit), the hash is #P0/A0/B0/C5, the chain ends with P0/A0/B0, the selected card
   is C5 of P0/A0/B0, the dialog is closed, and the last text of the live region gives
   the card and the path of its map. The page has no script error.
2. With reduced motion, the camera move of acceptance 1 occurs at one time: the camera
   directly after Enter is the camera when it stops.
3. The result of a flow in a different map ("token" in the map Gateway of the fixture) puts
   the two cards of the flow in the free box. The hash is #Gateway, and the live region
   gives the flow and its map. The result of a card that opens a map (Gateway) moves the
   camera into that map: the chain is [Gateway] and the hash is #Gateway.
4. A card of a map that has no area (the map Gateway with the size 0 x 0) has no place on
   the canvas: its result does not move the camera and does not change the hash, and the
   live region tells that the map has no area. The page has no script error.
5. While the dialog is open, f, F, +, -, =, the arrow keys, Tab and Enter (with no result)
   in the field do not change the camera, and the dialog stays open. Escape closes only the
   dialog: the camera and the chain do not change, and the keyboard focus goes back to
   the canvas. / opens the dialog, Ctrl+K closes it, and Meta+K opens it. The dialog is
   on the screen only while it is open (added after the first run: in that run, the
   dialog stayed on the screen when it was closed, and no test found it). Added on
   2026-11-07 (U4 in bench/jev/README.md): when a link of the list of the tree opens the
   dialog, and a result changes the view to Changes and back to Map, that link keeps the
   keyboard focus.
6. axe-core AXE_VERSION finds no violation with the dialog open and results, with a result
   selected, and after Enter, at 1440 x 900 and 390 x 844 pixels (a phone with a touch
   screen), in the light and the dark scheme. On the phone, each row of the results and
   the Close button are 44 pixels high or more, and the page has no horizontal scroll.
"""

from __future__ import annotations

import functools
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import AXE_VERSION, _axe
from test_canvas_browser import _bench, _tree_page, browser
from test_canvas_page import _made

DRIVER = Path(__file__).resolve().parent / "canvas_find.js"


def _find(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture(scope="module")
def canvas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("find"), "[render]\ncanvas = true\n")
    return root / "docs" / "map" / "index.html"


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _tree_page(tmp_path_factory, "find-tree")


def _free(found: dict[str, Any], box: list[float]) -> bool:
    """Tell if the screen box is in the free box of the screen."""
    after = found["after"]
    g, w, h = after["layout"]["gutters"], after["W"], after["H"]
    x, y, bw, bh = box
    return (
        x >= g["x"] - 0.5
        and y >= g["top"] - 0.5
        and x + bw <= w - g["x"] + 0.5
        and (y + bh <= h - g["bottom"] + 0.5)
    )


@functools.cache
def _deep(tree: Path, reduce: bool) -> dict[str, Any]:
    flags = ("--reduce",) if reduce else ()
    return _find("--go", str(tree), "C5", "Other maps", "P0/A0/B0", "C5", *flags)


def test_a_card_of_a_level_3_map(tree: Path) -> None:
    """Acceptance 1."""
    found = _deep(tree, False)
    assert found["errors"] == []
    assert found["before"]["chain"] == []
    assert found["target"]["t"] == "C5" and found["target"]["hint"] == "in P0/A0/B0", found
    assert found["now"] != found["after"]["camera"]
    after = found["after"]
    assert _free(found, found["boxes"][0]), (found["boxes"], after["layout"])
    assert after["hash"] == "#P0/A0/B0/C5"
    assert after["chain"][-1] == "P0/A0/B0"
    assert (after["selected"]["id"], after["selected"]["map"]) == ("C5", "P0/A0/B0")
    assert after["open"] is False and after["shown"] is False
    assert after["live"] == "Selected: card C5. Map: M11 shape / P0 / A0 / B0.", found["said"]


def test_with_reduced_motion_the_move_occurs_at_one_time(tree: Path) -> None:
    """Acceptance 2."""
    found = _deep(tree, True)
    assert found["errors"] == []
    assert found["now"] == found["after"]["camera"]
    assert found["after"]["hash"] == "#P0/A0/B0/C5"
    assert found["after"]["selected"]["id"] == "C5"


def test_a_flow_and_a_card_that_opens_a_map(canvas: Path) -> None:
    """Acceptance 3."""
    flow = _find("--go", str(canvas), "token", "Other maps", "Gateway", "Routes", "Auth")
    assert flow["errors"] == []
    assert flow["target"]["t"] == "token" and flow["target"]["hint"] == "in Gateway"
    assert all(_free(flow, box) for box in flow["boxes"]), flow["boxes"]
    assert flow["after"]["hash"] == "#Gateway"
    assert flow["after"]["live"] == "Flow from Routes to Auth: token. Map: join / Gateway."
    card = _find("--go", str(canvas), "gateway", "Components", "", "Gateway")
    assert card["errors"] == [] and card["target"]["t"] == "Gateway"
    assert card["after"]["chain"] == ["Gateway"] and card["after"]["hash"] == "#Gateway"
    assert card["after"]["live"] == "Open map: join / Gateway. 4 cards."


def test_a_card_of_a_map_with_no_area(canvas: Path, tmp_path: Path) -> None:
    """Acceptance 4."""
    html = canvas.read_text(encoding="utf-8")
    found = re.search(r'id="canvas-data">(.*?)</script>', html, re.S)
    assert found is not None
    data = json.loads(found.group(1))
    for m in data["maps"]:
        if m["id"] == "Gateway":
            m["size"] = [0, 0]
    page = _bench().write_page(data, tmp_path / "empty.html")
    out = _find("--go", str(page), "routes", "Other maps", "Gateway", "Routes")
    assert out["errors"] == []
    assert out["target"]["t"] == "Routes"
    assert out["after"]["camera"] == out["before"]["camera"]
    assert out["after"]["hash"] == ""
    assert out["after"]["live"] == (
        "The map join / Gateway has no area on the canvas. "
        "Thus the camera cannot go to the card Routes."
    )


def test_no_key_goes_to_the_camera_while_the_dialog_is_open(canvas: Path) -> None:
    """Acceptance 5."""
    out = _find("--keys", str(canvas))
    assert out["errors"] == []
    before = out["before"]
    assert out["opened"]["open"] is True and out["opened"]["active"] == "pal-input"
    typed = out["typed"]
    assert typed["open"] is True and typed["camera"] == before["camera"]
    assert typed["active"] == "pal-input"
    escaped = out["escaped"]
    assert escaped["open"] is False and escaped["active"] == "canvas"
    assert escaped["camera"] == before["camera"] and escaped["chain"] == before["chain"]
    assert out["slash"]["open"] is True
    assert out["toggled"]["open"] is False
    assert out["meta"]["open"] is True
    assert out["closed"]["open"] is False and out["closed"]["camera"] == before["camera"]
    for name in ("before", "opened", "typed", "escaped", "slash", "toggled", "meta", "closed"):
        assert out[name]["shown"] is out[name]["open"], name
    link = out["link"]
    assert link["before"].startswith("0:")
    assert link["views"] == [
        {"active": link["before"], "mode": "changes"},
        {"active": link["before"], "mode": "map"},
    ]


def test_axe_core_finds_no_issue_with_the_dialog(tree: Path) -> None:
    """Acceptance 6."""
    version = _axe()
    if version != AXE_VERSION:
        why = f"the test needs axe-core {AXE_VERSION} for Node, found {version or 'none'}"
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail(why)
        pytest.skip(why)
    runs = _find("--axe", str(tree), "C5")["runs"]
    assert len(runs) == 12
    for run in runs:
        assert run["version"] == AXE_VERSION and run["errors"] == [], run
        assert run["violations"] == [], run
        if run["state"] == "selected":
            assert run["active"] == "pal-o1", run
    for run in runs:
        if run["state"] == "results" and run["screen"] == "390x844":
            size = run["size"]
            assert size["rows"] and min(size["rows"]) >= 44, size
            assert size["close"] >= 44, size
            assert size["scroll"] == size["width"] == 390 and size["x"] == 0, size
