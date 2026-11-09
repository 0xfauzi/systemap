"""The marks of the open ports of the canvas page in a browser (`page_canvas_ports`).

The test drives the canvas page of the `nested` tree of tests/test_canvas_ports.py in the
Chromium of Playwright (tests/canvas_ports.js). Without the flow Routes -> Style, the map
inside Gateway has two open lines about the actor Style: a `boundary flow` line ("No
flow inside") and a `boundary import` line ("Import with no flow"). A second page has
only the `boundary flow` line open, and a third page has the two answers of the policy
kind. The test skips when Node, the Playwright package or axe-core is not there, except
when SYSTEMAP_BROWSER_TESTS is "required" (the CI job canvas-browser).

Acceptance values, written before the first run on 2026-11-08:

1. At the fit of the map Gateway, on a screen of 1440 x 900 pixels with reduced motion, in
   the light and the dark scheme: the data is judged, the actor card Style has the words
   "No flow inside" and "Import with no flow", and its tag "2 open lines" is drawn at 7 px
   or more with the alpha 1. The alpha of its mark is 1. After the camera goes from the
   top map to Gateway, the live region gives "Open boundary lines: 2.", "No flow inside:
   Style." and "Import with no flow: Style.". The item of Style in the list of the tree
   gives "Open boundary lines: No flow inside, Import with no flow.". The item of Gateway
   gives "Opens a map of 5 cards and 3 flows." and the item of Style in the top map gives
   "Opens a map of 4 cards and 3 flows." (step 7, the badge text, as words of the list).
   In the Changes view, no tag text of a port is drawn, the alpha of the mark is 0, and the
   list has no words of a port. Back in the Map view, the tag is drawn again. With only
   the `boundary flow` line open, the tag is "No flow inside". With the answers, no card
   has a mark, no tag is drawn, and the live region has no words of a port. The page has
   no script error.
2. The mark fades. Without reduced motion, the alpha of the mark changes by 0.25 or less
   between two frames after the Changes view starts and after the Map view starts again.
   It gets to 0 and back to 1, 160 ms or more after the call of `setView`. With reduced
   motion, the first frame has the target alpha. In a zoom of 90 frames from the fit of
   the top map to the fit of Gateway, the alpha of the tag text changes by 0.25 or less
   between two frames (a text that the frame does not draw has the alpha 0), no drawn tag
   text has less than 7 px, and the tag gets to the alpha 1.
3. axe-core 4.14.0 finds no violation at the fit of the top map and of Gateway, on screens
   of 1440 x 900 and 390 x 844 pixels (a phone with a touch screen), light and dark. The
   page has no horizontal scroll. On the phone, each target of the canvas is 44 px or more
   in width and in height. The screenshots of these 8 places go into SYSTEMAP_SHOTS when it
   is set.
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import test_canvas_ports as fixture
from test_canvas_access import AXE_VERSION, _axe, no_axe
from test_canvas_browser import browser

from systemap import canvas_data, canvas_page, judgement_json

DRIVER = Path(__file__).resolve().parent / "canvas_ports.js"
NESTED = "Gateway"
BOTH = ["Import with no flow", "No flow inside"]


@functools.cache
def _pages() -> dict[str, Path]:
    """Write the canvas page with two open lines, with one open line, and with none."""
    out = Path(tempfile.mkdtemp(prefix="canvas-ports-"))
    opened = fixture.made(out / "open") / "docs/map/index.html"
    closed = fixture.made(out / "closed", extra=fixture.POLICY) / "docs/map/index.html"
    cfg, tree, facts = fixture.loaded(out / "open")
    still = judgement_json.open_boundary(tree, facts, cfg)
    flow_only = sorted(line for line in still if "boundary flow" in line)
    one = out / "one.html"
    data = canvas_data.build(cfg, tree, facts, open_lines=flow_only)
    one.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return {"open": opened, "one": one, "closed": closed}


def drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _shots() -> tuple[str, ...]:
    where = os.environ.get("SYSTEMAP_SHOTS", "")
    return ("--shots", where) if where else ()


@functools.cache
def _marks(which: str, scheme: str) -> dict[str, Any]:
    flags = ("--light",) if scheme == "light" else ()
    shots = _shots() if which == "open" else ()
    return drive("--marks", str(_pages()[which]), NESTED, *flags, *shots)


def _style(place: dict[str, Any]) -> dict[str, Any]:
    (card,) = [c for c in place["state"]["cards"] if c["id"] == "Style"]
    return dict(card)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_an_open_port_has_its_mark_and_its_words(scheme: str) -> None:
    """Acceptance 1."""
    found = _marks("open", scheme)
    assert found["errors"] == []
    shown = found["map"]
    assert shown["state"]["judged"] is True
    style = _style(shown)
    assert sorted(style["words"]) == BOTH and style["tag"] == "2 open lines"
    assert style["mark"] == pytest.approx(1)
    tags = [t for t in shown["texts"] if t["s"] == "2 open lines"]
    assert tags and all(t["size"] >= 7 and t["alpha"] == pytest.approx(1) for t in tags)
    for words in (
        "Open boundary lines: 2.",
        "No flow inside: Style.",
        "Import with no flow: Style.",
    ):
        assert words in found["said"], words
    assert (
        "Open boundary lines: No flow inside, Import with no flow."
        in shown["list"]["#Gateway/Style"]
    )
    assert "Opens a map of 5 cards and 3 flows." in shown["list"]["#Gateway"]
    assert "Opens a map of 4 cards and 3 flows." in shown["list"]["#Style"]
    changes = found["changes"]
    assert changes["view"] == "changes" and changes["texts"] == []
    assert _style(changes)["mark"] == 0
    assert "Open boundary" not in json.dumps(changes["list"])
    assert [t["s"] for t in found["back"]["texts"]] == ["2 open lines"]


def test_one_open_line_gives_its_text_and_no_open_line_gives_no_mark() -> None:
    """Acceptance 1: the page with one open line and the page with the answers."""
    one = _marks("one", "dark")
    assert one["errors"] == []
    assert _style(one["map"])["tag"] == "No flow inside"
    assert [t["s"] for t in one["map"]["texts"]] == ["No flow inside"]
    closed = _marks("closed", "dark")
    assert closed["errors"] == []
    assert closed["map"]["state"]["judged"] is True
    assert closed["map"]["state"]["cards"] == [] and closed["map"]["texts"] == []
    assert "Open boundary" not in closed["said"]


def _steps(values: list[float], start: float) -> list[float]:
    out, last = [], start
    for v in values:
        out.append(abs(v - last))
        last = v
    return out


def test_the_mark_of_an_open_port_fades() -> None:
    """Acceptance 2."""
    found = drive("--fade", str(_pages()["open"]), NESTED, "Style")
    slow = found["no-preference"]
    for name, start, end in (("away", 1, 0), ("into", 0, 1)):
        d = slow[name]["d"]
        assert d and d[-1] == end and max(_steps(d, start)) <= 0.25, (name, d)
        assert slow[name]["ms"] >= 160, (name, slow[name]["ms"])
    fast = found["reduce"]
    assert fast["away"]["d"][0] == 0 and fast["into"]["d"][0] == 1
    for run in (slow, fast):
        assert run["errors"] == []
        alphas = [frame["alpha"] if frame else 0 for frame in run["zoomed"]]
        sizes = [frame["size"] for frame in run["zoomed"] if frame]
        assert max(_steps(alphas, alphas[0])) <= 0.25, alphas
        assert min(sizes) >= 7 and alphas[-1] == pytest.approx(1)


def test_axe_finds_no_violation_with_open_ports() -> None:
    """Acceptance 3."""
    if _axe() != AXE_VERSION:
        no_axe(f"the access test needs axe-core {AXE_VERSION} for Node")
    runs = drive("--axe", str(_pages()["open"]), NESTED, *_shots())["runs"]
    assert len(runs) == 8
    for run in runs:
        where = (run["screen"], run["scheme"], run["id"])
        phone = run["screen"] == "390x844"
        assert run["version"] == AXE_VERSION
        assert run["violations"] == [], where
        assert run["errors"] == [], where
        assert run["scroll"] == {"width": 390 if phone else 1440, "x": 0}, where
        if run["id"]:
            assert [c["id"] for c in run["state"]["cards"]] == ["Style"], where
        if phone:
            assert all(w >= 44 and h >= 44 for _kind, w, h in run["hits"]), (where, run["hits"])
