"""The reader tools and the Details panel of the canvas page in a browser
(`page_canvas_details`, the tools of `canvas_header`).

The test drives the canvas page of the self-map of this repository in the Chromium of
Playwright (tests/canvas_details.js). It skips when Node or the Playwright package is not
there, except when SYSTEMAP_BROWSER_TESTS is "required" (the CI job canvas-browser).

Acceptance values, written before the first run on 2026-11-08 (step 5 of
docs/design/nested-canvas.md). The numbers continue the numbers of
tests/test_canvas_details.py.

1. The theme button changes `data-theme` and keeps the scheme in localStorage with the key
   of the linked page (`systemap-theme`). The header then shows the button of the other
   scheme, and that button has the keyboard focus. The canvas reads the theme colors (the
   computed style of the root element) one time for the change, and not one time in a pan
   of 60 frames.
2. The Reduce motion button sets `data-reduce-motion` to "true", keeps it with the key of
   the linked page (`systemap-reduce-motion`), and is pressed. Then the alpha of a new
   selection goes from 0 to 1 in one frame. Before the button, with no system setting, the
   alpha changes by 0.25 or less in each frame, and the fade takes 160 ms or more
   (acceptance 13 of tests/test_canvas_browser.py also stays).
3. The ? key opens the keys sheet with the keys of `page_canvas_details.KEYS`, and the
   focus goes to its Close button. A key under the sheet does not operate. Escape closes
   it, and the focus goes back to the canvas. The F key moves the camera to the fit of the
   current map.
4. The source button gives the 7-character commit. It opens the source records with the
   full commit, the facts file and the model file. Escape closes them, and the focus goes
   back to the button.
5. The D key opens the Details panel with a fade of 160 ms or more and a change of the
   opacity of 0.25 or less in each frame, and the focus goes to its title. With reduced
   motion (the system setting or the page setting), the panel opens and closes in one
   frame. The panel gives the selected card: its name, the flows in and out, the
   sequences, the rules and the source evidence, and the modules of the card. A flow of the
   lists gives the flow, and the Back button gives the card again. The text of the panel
   changes only at a change of the selection: 0 DOM changes in a pan of 90 frames, and a
   change after a new selection. Escape in the panel closes it, does not move the camera
   out, and the focus goes back to the Details button.
   Changed after the second verification of step 5, before the run: the focus goes back to
   the element that had it before the panel opened (here the canvas). A CSS transition
   follows the time, so the test gives the change of the opacity for each frame as a rate:
   1.8 / 160 per ms or less (the start of the ease-out curve has the rate 1.72 / 160).
   The time of each frame is the time of the document timeline, as for the transition.
   Added after the verification of step 5, before the run: the panel of the card Scaffold
   gives its `note` text. With reduced motion (the system setting or the page setting), the
   keys sheet opens with no animation. Without it, the sheet has the animation `keys-in`.
8. C4: axe-core 4.14.0 finds no violation with the panel open (a card and a flow), with
   the keys sheet open, and with the source records open (on a phone, in the Tools menu),
   at 1440 x 900 and 390 x 844 pixels, in the light and the dark scheme.
9. C5: at 390 x 844 pixels with a touch screen, the tools go into the Tools menu, the
   scroll width is 390 pixels and the scroll position is 0. Each target of the header, of
   the menu, of the panel (also with each part of the source records open) and the Close
   button of the keys sheet is 44 x 44 pixels or more, in the screen width. The page has
   no script error.
11. Added after the verification of step 5, before the run: at rest, the lists and the
    fact row of a card are not partly transparent. The camera goes to the card CLI at 48
    zooms, from a card height of 60 px to 600 px. At rest, the alpha of each drawn list
    row, list name and fact row of the card is 0.02 or less, or 0.98 or more. The test
    examines 100 or more texts. Without the rule `rest` of `page_canvas_text`, this test
    found 39 partly transparent texts.
    Changed after the second verification of step 5: 32 zooms, and a wait of 250 ms at
    rest. The longest fade of a text (`colFade`) takes 160 ms. A first run with 24 zooms
    examined 81 texts, which is less than 100.
12. Added after the second verification of step 5, before the run (the items 12 to 16
    have one run of the driver, `--focus`): in the open list of the sequences, the letter
    d moves the focus to the next sequence whose name starts with d. The Details panel
    stays closed, and the list stays open. The ? key in the list does not open the keys
    sheet.
13. The D key two times on a focused card: the panel opens and closes, and the focus goes
    back to the canvas. The card keeps the focus, and the next Tab gives the next card in
    reading order.
14. With the Details panel open at 1440 x 900, Tab through the cards of the top map: no
    focused card is under the panel. At the fit, 1 card or more is under the panel.
15. A right click and a middle click on a card do not select it. A left click selects it.
16. The Tools menu is open at a width of 380 px. At a width of 1600 px the header has no
    menu, and the menu is closed (no `data-open`, `aria-expanded` is "false"). At 380 px
    again the menu stays closed.
17. On the page of the fixture of tests/test_canvas_page.py (a nested map), a button of the
    Details panel has the focus, and a zoom out closes the map of the selected card. Then
    the focus is on the heading of the new text of the panel, not on the body of the page.
"""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import AXE_VERSION, no_axe
from test_canvas_browser import browser
from test_canvas_page import _made

from systemap import canvas_data, canvas_page, config, facts_file, nest, page_canvas_details

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_details.js"
REPO = ROOT.parent


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@functools.cache
def _rev() -> str:
    cfg = config.load(REPO)
    return str(facts_file.read_facts(cfg.facts_path, cfg.root).get("built_at_commit", ""))


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    out = tmp_path_factory.mktemp("details") / "index.html"
    data = canvas_data.build(cfg, tree, facts)
    out.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


def _steps(frames: list[list[float]], rate: bool = False) -> tuple[float, float, int]:
    """Give the largest change between two frames, the time from the first frame with a
    change to the last frame with a change, and the count of frames with a change. With
    `rate`, the largest change is for each ms."""
    values = [v for _t, v in frames]
    moved = [i for i in range(1, len(values)) if values[i] != values[i - 1]]

    def change(i: int) -> float:
        step = abs(values[i] - values[i - 1])
        return step / max(frames[i][0] - frames[i - 1][0], 1e-3) if rate else step

    most = max((change(i) for i in moved), default=0.0)
    span = frames[moved[-1]][0] - frames[moved[0] - 1][0] if moved else 0.0
    return most, span, len(moved)


@pytest.fixture(scope="module")
def tools(self_page: Path) -> dict[str, Any]:
    return _drive("--tools", str(self_page))


def test_the_theme_button(tools: dict[str, Any]) -> None:
    """Acceptance 1."""
    assert tools["errors"] == []
    theme = tools["theme"]
    assert theme["before"] != theme["after"] and theme["stored"] == theme["after"]
    assert theme["shown"] == [theme["before"]] and theme["focus"] == theme["before"]
    assert theme["reads"] == 1
    assert tools["panReads"] == 0


def test_the_reduce_motion_button(tools: dict[str, Any]) -> None:
    """Acceptance 2."""
    assert tools["motion"] == {"attr": "true", "stored": "true", "pressed": "true"}
    # The record starts before the click: the selection of the card before it fades out
    # in the same frames, and the record gives the alpha of the new selection.
    on = [v for _t, v in tools["fadeOn"]]
    assert on[0] == 0 and on[-1] == 1 and _steps(tools["fadeOn"])[2] == 1, on
    most, span, frames = _steps(tools["fadeOff"])
    assert most <= 0.25 + 1e-9 and frames >= 5 and span >= 160 - 17, (most, span, frames)


def test_the_keys_sheet_and_the_fit(tools: dict[str, Any]) -> None:
    """Acceptance 3."""
    keys = tools["keys"]
    assert keys["open"] and keys["focus"] == "Close"
    assert keys["rows"] == [text for _key, text in page_canvas_details.KEYS]
    assert tools["keysClosed"] == {"open": False, "focus": "canvas"}
    camera, fit = tools["fit"]["camera"], tools["fit"]["fit"]
    assert all(abs(camera[k] - fit[k]) < 1e-6 for k in "xyk"), tools["fit"]


def test_the_source_button(tools: dict[str, Any]) -> None:
    """Acceptance 4."""
    snap, rev = tools["snap"], _rev()
    assert snap["open"] and snap["expanded"] == "true"
    assert snap["text"] == (f"at {rev[:7]}" if rev else "commit not recorded")
    assert (rev or "not recorded") in snap["pop"] and "map/model.py" in snap["pop"]
    assert tools["snapClosed"] == {"open": False, "focus": "snap"}


@pytest.mark.parametrize("motion", ["none", "system", "page"])
def test_the_details_panel(self_page: Path, motion: str) -> None:
    """Acceptance 5."""
    found = _drive("--panel", str(self_page), motion)
    assert found["errors"] == []
    # The opacity of the panel in each frame, 0 while it is hidden. The records start before
    # the key.
    opening, closing = ([[t, max(v, 0.0)] for t, v in found[k]] for k in ("opening", "closing"))
    for record, start, end in ((opening, 0, 1), (closing, 1, 0)):
        assert record[0][1] == start and record[-1][1] == end, record
        most, span, frames = _steps(record, rate=True)
        if motion == "none":
            assert most <= 1.8 / 160 and span >= 160 - 17 and frames >= 5, (most, span)
        else:
            assert frames == 1, record
    assert found["keysAnimation"] == ("keys-in" if motion == "none" else "none")
    scaffold = next(
        c for c in nest.load(config.load(REPO)).top.model.components if c.id == "Scaffold"
    )
    assert scaffold.note and found["note"] == f"Note. {scaffold.note}"
    assert found["openState"]["pressed"] == "true" and found["openState"]["focus"] == "cdet-title"
    card = found["card"]
    assert card["heading"] == found["cardId"]
    assert [h.split(" (")[0] for h in card["h4"]] == [
        "FLOWS IN",
        "FLOWS OUT",
        "SEQUENCES",
        "RULES",
        "SOURCE EVIDENCE",
    ]
    assert card["flows"] > 0 and card["modules"]
    assert found["panMutations"] == 0
    assert found["newMutations"] > 0 and found["second"] == found["secondId"]
    assert found["flow"]["heading"].startswith("Flow: ")
    assert found["flow"]["focus"] == found["flow"]["heading"]
    assert found["back"] == found["secondId"]
    assert found["closed"] == {
        "hidden": True,
        "focus": "canvas",
        "pressed": "false",
        "chain": [],
    }


def test_the_lists_of_a_card_at_rest_are_not_partly_transparent(self_page: Path) -> None:
    """Acceptance 11."""
    found = _drive("--rest", str(self_page), "CLI")
    assert found["errors"] == []
    assert found["checked"] >= 100 and found["partial"] == [], found


def test_the_tools_and_the_panel_are_accessible(self_page: Path) -> None:
    """Acceptance 8 (C4)."""
    runs = _drive("--access", str(self_page))["runs"]
    assert len(runs) == 16
    examined = True
    for run in runs:
        assert run["errors"] == [], run
        if run["axe"] is None:
            examined = False
            continue
        assert run["axe"]["version"] == AXE_VERSION and run["axe"]["violations"] == [], run
    if not examined:
        no_axe(f"the access test needs axe-core {AXE_VERSION} for Node")


def test_the_tools_and_the_panel_on_a_phone(self_page: Path) -> None:
    """Acceptance 9 (C5)."""
    found = _drive("--phone", str(self_page))
    assert found["errors"] == []
    assert found["menuFlag"]
    assert found["scroll"] == {"width": 390, "x": 0, "inner": 390}
    names = [t["name"] for t in found["menu"]]
    assert {"snap", "reduce-motion", "keys-open", "details-toggle"} <= set(names)
    assert len(found["panelOpen"]) >= len(found["panel"])
    for group in ("head", "menu", "panel", "panelOpen", "keys"):
        assert found[group], group
        for t in found[group]:
            assert t["w"] >= 44 and t["h"] >= 44, (group, t)
            assert t["x"] >= 0 and t["x"] + t["w"] <= 390, (group, t)


@pytest.fixture(scope="module")
def focused(self_page: Path) -> dict[str, Any]:
    found = _drive("--focus", str(self_page))
    assert found["errors"] == []
    return found


def test_a_letter_in_the_list_of_the_sequences_moves_in_the_list(focused: dict[str, Any]) -> None:
    """Acceptance 12."""
    letter = focused["letter"]
    assert letter["letter"] == "d" and letter["text"].lower().startswith("d"), letter
    assert letter["list"] and not letter["panel"]
    assert focused["question"]["list"] and not focused["question"]["sheet"]


def test_the_d_key_two_times_keeps_the_place_on_the_canvas(focused: dict[str, Any]) -> None:
    """Acceptance 13."""
    twice = focused["twice"]
    assert twice["focus"] == "canvas" and not twice["panel"]
    assert twice["card"] == twice["first"]
    order = twice["order"]
    assert twice["next"]["id"] == order[order.index(twice["first"]["id"]) + 1]


def test_the_panel_does_not_cover_the_focused_card(focused: dict[str, Any]) -> None:
    """Acceptance 14."""
    cover = focused["cover"]
    assert cover["before"] and cover["tabbed"] >= len(cover["before"])
    assert cover["hidden"] == [], cover


def test_only_the_main_button_selects_a_card(focused: dict[str, Any]) -> None:
    """Acceptance 15."""
    clicks = focused["clicks"]
    assert clicks["right"] is None and clicks["middle"] is None
    assert clicks["left"] == clicks["id"]


def test_a_change_of_the_header_closes_the_tools_menu(focused: dict[str, Any]) -> None:
    """Acceptance 16."""
    narrow, wide, again = focused["menu"]
    assert narrow == {"menu": True, "open": True, "expanded": "true"}
    assert wide == {"menu": False, "open": False, "expanded": "false"}
    assert again == {"menu": True, "open": False, "expanded": "false"}


def test_a_new_text_of_the_panel_keeps_the_focus_in_the_panel(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Acceptance 17."""
    root = _made(tmp_path_factory.mktemp("rewrite"), "")
    found = _drive("--rewrite", str(root / "docs" / "map" / "index.html"))
    assert found["errors"] == [] and found["card"]
    after = found["after"]
    assert after["chain"] == [] and after["selected"] is None
    assert after["inPanel"] and after["tag"] == "H3", after
