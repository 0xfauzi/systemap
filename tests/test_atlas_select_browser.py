"""The camera after a selection on the atlas page, in a browser.

A selection of a card must not take the place of the reader away. The test drives the
atlas page of a small map in the Chromium of Playwright at 1440 x 900 (tests/atlas_select.js).
The details are 380 px wide at the right. Thus the free part of the screen ends at
1440 - 16 - 380 = 1044 px. The test skips when Node or the Playwright package is not there,
except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails.

Acceptance values, written on 2026-11-21 before the first run of this test:

C1. The camera is at 1.5 times the zoom of the fit. A mouse click on a card that is fully on
    the screen and not under the area of the details selects the card and moves the camera
    by 0 px: the camera after 1.5 s is equal to the camera before the click. Esc then
    closes the details and the camera moves by 0 px again.
C2. A mouse click on a card with its right edge at 1340 px, under the area of the details,
    moves the camera only as far as necessary: 1340 - 1044 = 296 px to the left (within
    1 px), with the same zoom and no vertical move. After the move the right edge of the card
    is at 1044 px (within 1 px). The card at the other end of its flow was on the screen
    before the click and it is fully in the free part of the screen after the move.
C3. Find still brings a card that is off the screen into view: after the camera puts the card
    2000 px above and to the left of the screen, Ctrl K, the card ID and Enter select the
    card, and after 2.5 s its box is fully in the free part of the screen.

Acceptance values, written on 2026-11-21 before the first run, after an independent review:

C4. The partner rule. In the layer All, the map also has a flow from D to E, the only flow of
    D and of E, and E is at the right of D. The camera puts E with its right edge at 1430 px:
    E is fully on the screen, and D is under the area of the details. A click on D moves the
    camera so that D and E are both fully in the free part of the screen. The smallest move
    for D only would leave E under the details. (Check: with the partner rule removed, this
    test fails.)
    Changed before the first full run: the value used B and C, but B also has the partner A
    at its left, and B, A and C do not fit together in the free part. The nearest partner
    comes first, thus the value examined A, not the rule for C.
C5. A card fully in the free part does not move the camera, also when a card at the other
    end of its flow is under the area of the details: in C1, in the layer All, the right edge
    of D is 10 px at the left of the details, D has a flow to E, and E is at the right of D,
    fully on the screen and under the area of the details.
C6. A resize after a selection at the fit: at the fit of the map, a click on B, a change of
    the window to 1000 px wide and back to 1440 px. Then the camera is the fit of the map
    with the space of the details (within 1 px and 1 percent), and the frame of the map ends
    at the left of the details.
C7. A nested map with the details open: after the page loads with the hash of Gateway and a
    click on its first part, a click on each part that is fully on the screen and not under
    the details selects that part, and the page stays in Gateway. While the details are open,
    the locator, when it shows, covers no part.
    Changed before the first full run: the fixture does not put a part where the locator goes
    while the details are open, thus the value passed with the fault. The test now also moves
    the camera so that the last part that is not selected has its middle at 70 px at the left of the details and
    165 px from the top, and clicks it. That click must also select the part.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_atlas_browser import nested_page  # noqa: F401  (fixture)
from test_atlas_uses_browser import page
from test_canvas_browser import browser

DRIVER = Path(__file__).resolve().parent / "atlas_select.js"
FREE_RIGHT = 1440 - 16 - 380


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    cards = ["A", "B", "C", "D", "E", "F"]
    sources = {f"pkg/{c.lower()}.py": "def run() -> None:\n    pass\n" for c in cards}
    flows = [("A", "B", "request"), ("B", "C", "reply"), ("D", "E", "note")]
    html = page(tmp_path_factory.mktemp("select"), sources, cards, flows)
    return {
        "camera": _drive("camera", html, "D", "B", "F"),
        "partner": _drive("partner", html, "D", "E"),
        "resize": _drive("resize", html, "B"),
    }


def _drive(mode: str, html: Path, *rest: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(html), *rest],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    got = dict(json.loads(proc.stdout))
    assert got["errors"] == [], got["errors"]
    return got


def _inside(b: list[float], right: float = FREE_RIGHT) -> bool:
    return b[0] >= 16 - 1 and b[1] >= 0 and b[0] + b[2] <= right + 1 and b[1] + b[3] <= 900


def test_a_visible_card_does_not_move_the_camera(run: dict[str, Any]) -> None:
    """C1."""
    v = run["camera"]["visible"]
    assert _inside(v["box"])
    assert v["sel"] == {"map": "", "id": "D"}
    assert v["after"] == v["before"]
    assert v["closedSel"] is None and v["closed"] == v["before"]


def test_a_card_under_the_details_moves_only_as_far_as_necessary(run: dict[str, Any]) -> None:
    """C2."""
    u = run["camera"]["under"]
    assert u["sel"] == {"map": "", "id": "B"}
    right = u["box"][0] + u["box"][2]
    assert right == pytest.approx(1340, abs=1)
    before, after = u["before"], u["after"]
    assert after["k"] == pytest.approx(before["k"]) and after["y"] == pytest.approx(before["y"])
    assert (after["x"] - before["x"]) * after["k"] == pytest.approx(right - FREE_RIGHT, abs=1)
    assert u["boxAfter"][0] + u["boxAfter"][2] == pytest.approx(FREE_RIGHT, abs=1)
    a_before = next(c["b"] for c in u["boxes"] if c["id"] == "A")
    a_after = next(c["b"] for c in u["boxesAfter"] if c["id"] == "A")
    assert _inside(a_before, 1440) and _inside(a_after)


def test_find_brings_an_off_screen_card_into_view(run: dict[str, Any]) -> None:
    """C3."""
    f = run["camera"]["far"]
    assert f["before"][0] + f["before"][2] < 0
    assert f["sel"] == {"map": "", "id": "F"}
    assert _inside(f["after"])


def test_the_move_keeps_a_partner_in_view(run: dict[str, Any]) -> None:
    """C4."""
    p = run["partner"]
    assert p["after"]["sel"] == {"map": "", "id": "D"}
    card, other = p["before"]["card"], p["before"]["other"]
    assert card[0] + card[2] > FREE_RIGHT + 1 and _inside(other, 1440)
    assert p["after"]["cam"]["k"] == pytest.approx(p["before"]["cam"]["k"])
    assert _inside(p["after"]["card"]) and _inside(p["after"]["other"])


def test_a_free_card_with_a_partner_under_the_details_does_not_move(run: dict[str, Any]) -> None:
    """C5."""
    v = run["camera"]["visible"]
    e = next(c["b"] for c in v["boxes"] if c["id"] == "E")
    assert _inside(e, 1440) and e[0] + e[2] > FREE_RIGHT
    assert v["after"] == v["before"]


def test_a_resize_after_a_selection_at_the_fit_fits_again(run: dict[str, Any]) -> None:
    """C6."""
    r = run["resize"]
    assert (
        r["selected"]["sel"] == {"map": "", "id": "B"} and r["back"]["sel"] == r["selected"]["sel"]
    )
    cam, fit = r["back"]["cam"], r["back"]["fit"]
    assert cam["k"] == pytest.approx(fit["k"], rel=0.01)
    assert abs(cam["x"] - fit["x"]) * cam["k"] <= 1 and abs(cam["y"] - fit["y"]) * cam["k"] <= 1
    frame = r["back"]["frame"]
    assert frame[0] + frame[2] <= FREE_RIGHT + 16 + 1


def test_a_nested_map_keeps_each_click_on_a_part(nested_page: Path) -> None:  # noqa: F811
    """C7."""
    got = _drive("nested", nested_page, "Gateway")
    assert got["clicks"]
    for c in got["clicks"]:
        assert c["current"] == "Gateway" and c["sel"] == {"map": "Gateway", "id": c["id"]}, c
        loc = c["loc"]
        if loc:
            box = [loc["x"] - 6, loc["y"] - 6, loc["x"] + loc["w"] + 6, loc["y"] + loc["h"] + 6]
            for b in c["boxes"]:
                assert not (
                    box[0] < b[0] + b[2]
                    and box[2] > b[0]
                    and box[1] < b[1] + b[3]
                    and box[3] > b[1]
                ), (c["id"], loc, b)
