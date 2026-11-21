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
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_atlas_uses_browser import page
from test_canvas_browser import browser

DRIVER = Path(__file__).resolve().parent / "atlas_select.js"
FREE_RIGHT = 1440 - 16 - 380


@pytest.fixture
def run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    cards = ["A", "B", "C", "D", "E", "F"]
    sources = {f"pkg/{c.lower()}.py": "def run() -> None:\n    pass\n" for c in cards}
    html = page(tmp_path, sources, cards, [("A", "B", "request")])
    capsys.readouterr()
    proc = subprocess.run(
        [browser(), str(DRIVER), str(html), "D", "B", "F"],
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
    v = run["visible"]
    assert _inside(v["box"])
    assert v["sel"] == {"map": "", "id": "D"}
    assert v["after"] == v["before"]
    assert v["closedSel"] is None and v["closed"] == v["before"]


def test_a_card_under_the_details_moves_only_as_far_as_necessary(run: dict[str, Any]) -> None:
    """C2."""
    u = run["under"]
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
    f = run["far"]
    assert f["before"][0] + f["before"][2] < 0
    assert f["sel"] == {"map": "", "id": "F"}
    assert _inside(f["after"])
