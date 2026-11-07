"""The Changes view of the canvas page in a browser (`page_canvas_changes`).

The test drives the canvas page of the three-level tree of tests/test_canvas_changes.py in
the Chromium of Playwright (tests/canvas_changes.js). The working tree has a model change
and a source change in the map P0/Q0/Deep. Thus D1 has changed source, D0 imports it, and
the cards P0, Q0 and Deep that open the maps on the path are "changed inside". A second
page of the same tree has no revision comparison. The view starts with
`systemapCanvas.setView`, as the view control of the header does. The test skips when Node,
the Playwright package or axe-core is not there, except when SYSTEMAP_BROWSER_TESTS is
"required" (the CI job canvas-browser).

Acceptance values (written before the first run, step 4 of docs/design/nested-canvas.md):

1. In the Changes view at the fit of the top map and of the map P0/Q0/Deep, on a screen of
   1440 x 900 pixels with reduced motion, in the light and the dark scheme: of the pixels
   on the middle fifth of the left side of the ring of each card with the mark "changed"
   or "imports" (a dashed ring has gaps), one or more has the color of the theme token
   --change (a difference of 24 or less in the sum of the three channels). In the Map
   view, each of these pixels has a difference of more than 60. `systemapCanvas.texts()` has the tag CHANGED on P0 and on D1, the tag IMPORTS
   on D0, and "changed inside" on P0, each at 7 px or more and with the alpha 1. The Map
   view has none of these texts. The cards with the mark "none" have the opacity factor
   0.32, the cards with the mark "end" 0.6, and the marked cards and the cards that are
   "changed inside" 1. The page has no script error.
2. The live region and the list of the tree give the change words in the Changes view:
   the live region gives "View: Changes." and "Changed inside: P0." at the top map. The item
   of P0 in the list gives "Change: changed source." and "Changed inside:". After the
   change back to the Map view, the list has no change words. After Esc from P0/Q0/Deep in
   the Changes view, the live region gives the map P0/Q0 and "Changed inside: Deep.". A
   name that is not a view does not change the view.
3. Each change mark fades in and out. Without reduced motion, the alpha of the view
   changes by 0.25 or less between two frames, and it gets to 1 (and back to 0) 160 ms or
   more after the call of `setView`. With reduced motion, the first frame has the target
   alpha. In a zoom of 90 frames from 0.3 to 1.6 times the fit of the top map, the alpha of
   the tag CHANGED and of "changed inside" changes by 0.25 or less between two frames (a
   text that the frame does not draw has the alpha 0), no such text has less than 7 px,
   and each one gets to the alpha 1.
4. axe-core finds no violation in the Changes view, with and without a comparison, on
   screens of 1440 x 900 and 390 x 844 pixels (a phone with a touch screen), light and
   dark, at the top map and in P0/Q0/Deep. The page has no horizontal scroll. Without a
   comparison, the Changes view shows the text of `page_changes.empty`. Its Copy button is
   44 x 44 pixels or more, it has a visible focus outline, and Enter on it changes the
   live region.

Changes at the merge with the header part (step 4): the header gives the words of the view
("View: Changes." in place of "Changes view."). The ring is 3 px outside the card, so the
pixels of acceptance 1 are on that line. In acceptance 3, the steps of the zoom start at the
alpha of its first frame, because a tag can show at the start of the zoom.

The C2 measurement with the Changes view is bench/jev/canvas_changes_frames.py.
"""

from __future__ import annotations

import functools
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import test_canvas_changes as fixture
from test_canvas_access import AXE_VERSION, _axe
from test_canvas_browser import browser

from systemap import canvas_data, canvas_page

DRIVER = Path(__file__).resolve().parent / "canvas_changes.js"
NESTED = "P0/Q0/Deep"
TAGS = ("CHANGED", "TESTS", "IMPORTS", "changed inside")


@functools.cache
def _pages() -> tuple[Path, Path]:
    """Write the canvas page of the tree with a comparison and without one."""
    out = Path(tempfile.mkdtemp(prefix="canvas-changes-"))
    root = out / "repo"
    rev = fixture.committed(root)
    fixture.model_change(root)
    fixture.source_change(root)
    cfg, tree, facts, changes = fixture.changed(root, rev)
    theme = canvas_page.tree_theme(cfg, tree)
    compared, plain = out / "changed.html", out / "plain.html"
    compared.write_text(
        canvas_page.build(theme, canvas_data.build(cfg, tree, facts, changes=changes)),
        encoding="utf-8",
    )
    plain.write_text(
        canvas_page.build(theme, canvas_data.build(cfg, tree, facts)), encoding="utf-8"
    )
    return compared, plain


def drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _rgb(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]


def _apart(pixel: list[int], color: str) -> int:
    return sum(abs(a - b) for a, b in zip(pixel, _rgb(color), strict=True))


def _texts(found: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for t in found["texts"]:
        out.setdefault(t["s"], []).append(t)
    return out


@functools.cache
def _marks(scheme: str) -> dict[str, Any]:
    flags = ("--light",) if scheme == "light" else ()
    return drive("--marks", str(_pages()[0]), NESTED, *flags)


def _check_place(
    map_id: str, place: dict[str, Any], cards: dict[str, Any], inside: list[str]
) -> None:
    """Check the marks of one place in the Changes view, and that the Map view has none."""
    assert place["errors"] == [] and place["ok"] is True
    during, before = place["during"], place["before"]
    shown = {c["id"]: c for c in during["state"]["cards"]}
    for cid, (mark, alpha) in cards.items():
        assert shown[cid]["mark"] == mark, (map_id, cid)
        assert shown[cid]["alpha"] == pytest.approx(alpha), (map_id, cid)
    assert sorted(c for c, v in shown.items() if v["inside"]) == inside
    for cid in (c for c, (mark, _alpha) in cards.items() if mark in ("changed", "imports")):
        _check_ring(map_id, cid, during, before)
    _check_words(map_id, _texts(during))
    assert not _texts(before) and not _texts(place["after"])
    assert place["after"]["state"]["t"] == 0


def _check_ring(map_id: str, cid: str, during: dict[str, Any], before: dict[str, Any]) -> None:
    """The ring of card `cid` has the change color in the Changes view and not before."""
    near = min(_apart(p, during["change"]) for p in during["rings"][cid])
    far = min(_apart(p, during["change"]) for p in before["rings"][cid])
    assert near <= 24, (map_id, cid)
    assert far > 60, (map_id, cid)


def _check_words(map_id: str, texts: dict[str, list[dict[str, Any]]]) -> None:
    """The tags of the place show at 7 px or more with the alpha 1."""
    words = ["CHANGED", "changed inside"] if map_id == "" else ["CHANGED", "IMPORTS"]
    for word in words:
        assert texts[word], (map_id, word)
        assert all(t["size"] >= 7 and t["alpha"] == pytest.approx(1) for t in texts[word])


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_marks_in_the_changes_view(scheme: str) -> None:
    """Acceptance 1."""
    found = _marks(scheme)
    expected = {
        "": ({"P0": ("changed", 1.0), "Base": ("end", 0.6), "P1": ("none", 0.32)}, ["P0"]),
        NESTED: ({"D1": ("changed", 1.0), "D0": ("imports", 1.0), "R0": ("none", 0.32)}, []),
    }
    for map_id, (cards, inside) in expected.items():
        _check_place(map_id, found["places"][map_id], cards, inside)


def test_the_live_region_and_the_list_give_the_change_words() -> None:
    """Acceptance 2."""
    found = _marks("dark")
    top = found["places"][""]
    assert "View: Changes." in top["during"]["said"]
    assert "Changed inside: P0." in top["during"]["said"]
    assert "Change: changed source." in top["during"]["list"]["#P0"]
    assert "Changed inside:" in top["during"]["list"]["#P0"]
    assert "Changed inside: P0." in top["during"]["top"]
    assert "Change:" not in json.dumps(top["after"]["list"])
    assert "Changed inside" not in top["after"]["top"]
    assert found["escaped"]["chain"] == ["P0", "P0/Q0"]
    assert "Open map: three levels / P0 / Q0." in found["escaped"]["said"]
    assert "Changed inside: Deep." in found["escaped"]["said"]
    assert found["escaped"]["errors"] == []
    assert found["bad"] is False


def _steps(values: list[float], start: float) -> list[float]:
    out, last = [], start
    for v in values:
        out.append(abs(v - last))
        last = v
    return out


def test_each_change_mark_fades() -> None:
    """Acceptance 3."""
    found = drive("--fade", str(_pages()[0]))
    slow = found["no-preference"]
    for name, start, end in (("into", 0, 1), ("back", 1, 0)):
        t = slow[name]["t"]
        assert t[-1] == end and max(_steps(t, start)) <= 0.25, (name, t)
        assert slow[name]["ms"] >= 160, (name, slow[name]["ms"])
    fast = found["reduce"]
    assert fast["into"]["t"][0] == 1 and fast["back"]["t"][0] == 0
    for run in (slow, fast):
        assert run["errors"] == []
        for word in ("CHANGED", "changed inside"):
            alphas = [frame.get(word, {"alpha": 0})["alpha"] for frame in run["zoomed"]]
            sizes = [frame[word]["size"] for frame in run["zoomed"] if word in frame]
            assert max(_steps(alphas, alphas[0])) <= 0.25, (word, alphas)
            assert min(sizes) >= 7 and max(alphas) == pytest.approx(1), word


@pytest.mark.parametrize("which", ["compared", "plain"])
def test_axe_finds_no_violation_in_the_changes_view(which: str) -> None:
    """Acceptance 4."""
    if _axe() != AXE_VERSION:
        browser()
        pytest.skip(f"the access test needs axe-core {AXE_VERSION} for Node")
    page = _pages()[0 if which == "compared" else 1]
    runs = drive("--axe", str(page), NESTED)["runs"]
    assert len(runs) == 8
    for run in runs:
        where = (run["screen"], run["scheme"], run["id"])
        assert run["version"] == AXE_VERSION
        assert run["violations"] == [], where
        assert run["errors"] == [], where
        assert run["scroll"] == {"width": 1440 if run["screen"] == "1440x900" else 390, "x": 0}
        if which == "compared":
            assert run["panel"] is None, where
            continue
        assert min(run["panel"]["button"]) >= 44, where
        assert run["focus"]["top"] and run["focus"]["outline"].startswith("solid"), where
        assert "command" in run["focus"]["said"], where
