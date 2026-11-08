"""The access checks of the canvas page in a browser (`page_canvas_tree`, `page_canvas_keys`).

The test drives the canvas page in the Chromium of Playwright (tests/canvas_access.js).
The pages are the canvas page of the fixture of tests/test_nest_join.py (the card Gateway
opens a map) and the generated M11 tree (bench/jev/canvas_frames.py). The test skips when
Node, the Playwright package or the axe-core package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required" (the CI job canvas-browser). The CI job installs
axe-core AXE_VERSION. The page does not load axe-core: the driver puts it into the page.

Acceptance values:

1. C4 of docs/design/nested-canvas.md: axe-core AXE_VERSION finds no violation in each run.
   Thus it finds 0 serious and 0 critical issues. The runs are on screens of 1440 x 900
   pixels and 390 x 844 pixels (a phone with a touch screen), in the light and the dark
   scheme, with reduced motion. Each run is at the top map and in a nested map (#Gateway for
   the fixture, #P0/A0 for the M11 tree), with no focus, with the focus on a link of the
   list of the tree, and with the focus on a card after Tab. Each place has a new load of
   the page. In the run with no focus, no card has the keyboard focus and the canvas does
   not have the focus. The page has no script error.
2. A URL hash that names a property of all objects (for example #constructor or
   #Gateway/__proto__) names no map and no card: the canvas opens at the top map, with no
   script error, and the list of the tree has all its links. A change of the hash to such a
   name after the load gives no script error. Changed after the verification of step 5: a
   hash that starts with the ID of a nested map, such as #Gateway/__proto__, opens that
   map, and the live region tells that no map and no card has the link.
3. After Esc from the map Gateway, the live region gives the top map and the focused card
   Gateway, in one text. The live region changes one time after Esc.
4. When a zoom out closes the map of the focused card, the card loses the keyboard focus:
   the page draws no ring. Then Enter selects no card and does not change the live region.
5. Esc on a link of the list of the tree does not put the keyboard focus on a card.
6. A pinch with two fingers zooms by the ratio of the finger distances. The world point at
   the middle of the fingers at the start is at the middle of the fingers at the end, in
   0.5 pixels.
7. When the keyboard focus is on a card of the top map and a wheel zoom goes into the map
   of Gateway, the card loses the keyboard focus: the page draws no ring, and the live
   region gives only the map Gateway. The next Tab focuses the first card of the map
   Gateway.
8. In the generated M11 tree, without reduced motion, Enter on P0 and Tab 400 ms later
   during the flight do not stop the flight. When the camera stops, the map P0 is open and
   its first card has the keyboard focus. The live region gives the words of that card in
   one text only.
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
from pathlib import Path
from typing import Any, NoReturn

import pytest
from test_canvas_browser import _tree_page, browser
from test_canvas_page import _made

AXE_VERSION = "4.14.0"
DRIVER = Path(__file__).resolve().parent / "canvas_access.js"


@functools.cache
def _axe() -> str:
    """Give the axe-core version that Node finds, or '' when Node cannot find it."""
    probe = subprocess.run(
        [browser(), str(DRIVER), "--probe"], capture_output=True, text=True, timeout=120
    )
    return probe.stdout.strip() if probe.returncode == 0 else ""


def no_axe(why: str) -> NoReturn:
    """Stop a test that needs axe-core: it fails when SYSTEMAP_BROWSER_TESTS is "required"
    (the CI job canvas-browser), and it skips in the other cases."""
    if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
        pytest.fail(why)
    pytest.skip(why)


def _access(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture(scope="module")
def canvas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("access"), "[render]\ncanvas = true\n")
    return root / "docs" / "map" / "index.html"


@pytest.mark.parametrize("which", ["fixture", "tree"])
def test_axe_core_finds_no_issue(
    which: str, canvas: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Acceptance 1 (C4)."""
    version = _axe()
    if version != AXE_VERSION:
        no_axe(f"the C4 test needs axe-core {AXE_VERSION} for Node, found {version or 'none'}")
    page, nested = (
        (canvas, "Gateway")
        if which == "fixture"
        else (_tree_page(tmp_path_factory, "axe"), "P0/A0")
    )
    runs = _access("--axe", str(page), nested)["runs"]
    assert len(runs) == 24
    for run in runs:
        assert run["version"] == AXE_VERSION and run["errors"] == [], run
        assert run["violations"] == [], run
    assert {run["hash"] for run in runs} == {"", "#" + nested}
    assert all(run["focus"] for run in runs if run["state"] == "card")
    for run in runs:
        if run["state"] == "no focus":
            assert run["before"]["focus"] is None and run["before"]["active"] != "canvas", run


@pytest.fixture(scope="module")
def held(canvas: Path) -> dict[str, Any]:
    return _access("--held", str(canvas), "Gateway")


def test_a_hash_with_an_object_property_names_no_map(held: dict[str, Any]) -> None:
    """Acceptance 2."""
    assert len(held["hashes"]) == 5
    for hash_, found in held["hashes"].items():
        assert found["errors"] == [], hash_
        if "links" in found:
            inside = ["Gateway"] if "/" in hash_ else []
            assert found["api"] and found["links"] == 13 and found["chain"] == inside, hash_
            assert found["said"].startswith(f"No map and no card has the link {hash_}."), hash_


def test_the_live_region_after_esc_and_the_closed_focus(held: dict[str, Any]) -> None:
    """Acceptance 3, 4 and 5."""
    assert held["errors"] == []
    escaped = held["escaped"]
    assert escaped["chain"] == [] and escaped["focus"] == {"map": "", "id": "Gateway"}
    assert escaped["live"] == (
        "Open map: join. 4 cards. Card Gateway, 3 of 4. This card opens a map."
    )
    assert held["escapedSaid"] == [escaped["live"]]
    assert held["inner"]["focus"]["map"] == "Gateway"
    closed, after = held["closed"], held["closedEnter"]
    assert closed["chain"] == [] and closed["focus"] is None and closed["ring"] is None
    assert after["selected"] is None and after["focus"] is None
    assert after["live"] == closed["live"]
    linked = held["linkEscaped"]
    assert linked["active"] == "A" and linked["focus"] is None and linked["chain"] == []


def test_a_zoom_into_a_different_card_removes_the_focus(held: dict[str, Any]) -> None:
    """Acceptance 7."""
    assert held["other"]["map"] == "" and held["other"]["id"] != "Gateway"
    zoomed = held["zoomedIn"]
    assert zoomed["chain"] == ["Gateway"]
    assert zoomed["focus"] is None and zoomed["ring"] is None, zoomed
    assert zoomed["live"] == "Open map: join / Gateway. 4 cards.", zoomed
    after = held["zoomedTab"]
    assert after["focus"] == {"map": "Gateway", "id": held["innerOrder"][0]}, after


def test_tab_in_the_flight_of_enter_keeps_the_flight(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Acceptance 8."""
    found = _access("--dive", str(_tree_page(tmp_path_factory, "dive")), "P0")
    assert found["errors"] == []
    state, first = found["state"], found["order"][0]
    assert state["chain"] == ["P0"], state
    assert state["focus"] == {"map": "P0", "id": first}, state
    words = f"Card {first}, 1 of {len(found['order'])}."
    assert sum(words in said for said in found["said"]) == 1, found["said"]
    assert state["live"].endswith(words + " This card opens a map."), state


def test_a_pinch_keeps_the_point_between_the_fingers(held: dict[str, Any]) -> None:
    """Acceptance 6."""
    out, back = held["pinch"]
    assert out["ratio"] == pytest.approx(3, rel=1e-3)
    assert back["ratio"] == pytest.approx(1 / 3, rel=1e-3)
    assert out["drift"] <= 0.5 and back["drift"] <= 0.5, held["pinch"]
