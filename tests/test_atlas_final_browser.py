"""The faults of the final review of the atlas page, in a browser (docs/design/atlas.md).

The test drives the atlas page of the map of this repository, with its nested map Page, in
the Chromium of Playwright (tests/atlas_final.js). The test skips when Node or the
Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is "required". Then it
fails.

Acceptance values, written on 2026-11-20 before the first run of these tests:

1. A mouse double-click on the middle of the card Page of the top map at 1440 x 900 goes
   into the map Page, with reduced motion and without it: the current map is "Page", the
   hash is "#Page", and the double-click selects no text of the page. No run has a script
   error.
2. After a selection with Find and Enter (the card Placer), and after a mouse click on the
   card Check, the card is selected and the help note at the bottom left has the class
   "gone" (it does not show).
3. The reading line is one line of text. With the details of Page open and the pointer on
   its first flow row: the reading line shows, and its height is less than two times the
   line height of its text plus its padding (20 px) and its border (2 px). It is in the
   part of the screen at the left of the details, 16 px or more from them. Its middle is
   at the middle of that part, to 2 px. It does not cover the zoom control. The key does
   not show while the reading line shows.
4. In the diagram of each sequence of the top map at its first step, each label of a row
   has a plate under it: a plate box holds the box of the label (1 px of tolerance). The
   plate has the opacity 1 and the fill of the ground. Thus no lifeline shows through a
   label, also through the label of a faint later step.
5. In the nested map Page at 1440 x 900 at the fit, each label at rest is fully inside or
   fully outside each container with a surface and each region tint (0.5 px of
   tolerance), and the map shows one label at rest or more. The numbers of the regions are
   in reading order: by rows from the top (a region starts a row when its top is below the
   middle of the row), and from the left in a row, the numbers are 1, 2, 3 and so on.
6. On a phone of 390 x 844 px, the headline of the Map view gives the counts: the counts
   show, and they end with "flows". The page has no horizontal scroll.
7. The key of the top map starts with "Color when you point:" and gives the kinds with the
   words of the study: "Data" and "Control", not "Data flow".
8. The details of Placer give the assurance level and the freshness under its name in the
   words of the study ("Claims examined against the source, current" for the level
   "examined" and the freshness "current"). A long description that is cut has a line
   clamp of 4 lines, so that the browser shows an ellipsis at the cut.
"""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_atlas_browser import self_page  # noqa: F401  (fixture)
from test_canvas_browser import browser

DRIVER = Path(__file__).resolve().parent / "atlas_final.js"
CLAIMS = {
    "established": "Claims established from the source facts",
    "examined": "Claims examined against the source",
    "unknown": "Claims not examined",
}


@functools.cache
def _run(page: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), page], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture(scope="module")
def run(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:  # noqa: F811
    return _run(str(self_page[0]))


def test_a_double_click_goes_into_page_with_and_without_reduced_motion(
    run: dict[str, Any],
) -> None:
    """Acceptance 1."""
    for name in ("reduced", "normal"):
        one = run["dbl"][name]
        assert one["errors"] == [], name
        assert one["current"] == "Page" and one["hash"] == "#Page", (name, one)
        assert one["selected"] == "", (name, one)


def test_a_selection_hides_the_help_note(run: dict[str, Any]) -> None:
    """Acceptance 2."""
    find, click = run["note"]["find"], run["note"]["click"]
    assert find["errors"] == [] and click["errors"] == []
    assert find["sel"] == {"map": "", "id": "Placer"}
    assert click["sel"] == {"map": "", "id": "Check"}
    assert "gone" in find["cls"].split() and "gone" in click["cls"].split()


def test_the_reading_line_is_one_line_beside_the_details(run: dict[str, Any]) -> None:
    """Acceptance 3."""
    s = run["say"]
    assert s["errors"] == [] and s["on"] and s["text"]
    box, side, zoom = s["say"], s["side"], s["zoom"]
    assert box["height"] < 2 * s["line"] + 22, s
    assert box["right"] <= side["left"] - 16, s
    assert abs((box["left"] + box["right"]) / 2 - side["left"] / 2) <= 2, s
    assert box["left"] >= zoom["right"] or box["bottom"] <= zoom["top"], s
    assert s["key"] == "hidden"


def _holds(outer: dict[str, float], inner: dict[str, float], tol: float) -> bool:
    return (
        outer["left"] <= inner["left"] + tol
        and outer["top"] <= inner["top"] + tol
        and outer["right"] >= inner["right"] - tol
        and outer["bottom"] >= inner["bottom"] - tol
    )


def test_each_label_of_the_diagram_has_a_plate(run: dict[str, Any]) -> None:
    """Acceptance 4."""
    b = run["board"]
    assert b["errors"] == [] and b["runs"]
    later = 0
    for one in b["runs"]:
        assert one["labels"] and one["lives"]
        for label in one["labels"]:
            plates = [p for p in one["plates"] if _holds(p["box"], label["box"], 1)]
            assert plates, label
            assert all(p["opacity"] == "1" for p in plates), label
            later += label["later"]
    assert later > 0


def _side(a: list[float], b: list[float], tol: float) -> bool:
    """Box a (x0, y0, x1, y1) is fully inside or fully outside box b (x, y, w, h)."""
    x0, y0, x1, y1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    inside = a[0] >= x0 - tol and a[1] >= y0 - tol and a[2] <= x1 + tol and a[3] <= y1 + tol
    outside = a[2] <= x0 + tol or a[0] >= x1 - tol or a[3] <= y0 + tol or a[1] >= y1 - tol
    return inside or outside


def _reading(regions: list[list[float]]) -> list[int]:
    order = sorted(range(len(regions)), key=lambda i: regions[i][1])
    rows: list[list[int]] = []
    mid = -1e9
    for i in order:
        r = regions[i]
        if not rows or r[1] > mid:
            rows.append([])
            mid = r[1] + r[3] / 2
        rows[-1].append(i)
    return [i for row in rows for i in sorted(row, key=lambda i: regions[i][0])]


def test_the_labels_and_the_regions_of_page(run: dict[str, Any]) -> None:
    """Acceptance 5."""
    p = run["page"]
    assert p["errors"] == [] and p["current"] == "Page"
    assert p["labels"]
    for label in p["labels"]:
        for b in p["boxes"] + p["regions"]:
            assert _side(label["box"], b, 0.5), (label, b)
    regions = p["regions"]
    assert len(regions) >= 2
    for n, i in enumerate(_reading(regions), start=1):
        r = regions[i]
        near = min(p["digits"], key=lambda d: abs(d["box"][0] - r[0]) + abs(d["box"][1] - r[1]))
        assert near["s"] == str(n), (n, r, near)


def test_a_phone_headline_gives_the_counts(run: dict[str, Any]) -> None:
    """Acceptance 6."""
    ph = run["phone"]
    assert ph["errors"] == []
    assert ph["display"] != "none" and ph["shown"], ph
    assert ph["text"].endswith(" flows"), ph
    assert ph["scroll"] <= 390


def test_the_key_and_the_details_use_the_words_of_the_study(
    run: dict[str, Any],
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
) -> None:
    """Acceptances 7 and 8."""
    h = run["head"]
    assert h["errors"] == []
    assert h["key"].startswith("Color when you point:")
    assert "Data" in h["key"] and "Control" in h["key"] and "Data flow" not in h["key"]
    placer = next(c for c in self_page[1]["maps"][0]["cards"] if c["id"] == "Placer")
    level, fresh = placer["as"]
    assert h["state"] == f"{CLAIMS[level]}, {fresh}"
    if h["clip"]:
        assert h["clamp"] == "4"
