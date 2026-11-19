"""The disclosure "Not in this comparison" of the atlas page in a browser.

The test drives the page that `systemap render --base` writes for the three-level tree of
tests/test_canvas_changes.py (tests/test_atlas_limits.py), in the Chromium of Playwright
(tests/atlas_limits.js). The test skips when Node or the Playwright package is not there,
except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips
when axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written on 2026-11-19 after the review of stage 9, before the first run of
these tests. Each value is for 1440 x 900 and 390 x 844, in the light and the dark scheme:

1. The order of the keyboard focus agrees with the order on the screen. From the start of the
   page, Tab gets to the summary of the disclosure before it gets to the canvas, because the
   disclosure is in the headline above the map.
2. Enter on the summary opens the disclosure. The open disclosure shows the text of the
   limits, with "Source differences start at the merge base". The summary and the open text
   are fully in the width of the window, below the layer tabs and below the question of the
   headline, and the page has no horizontal scroll.
3. In the Focus view, the disclosure does not show. Back in the Map view, it shows again.
4. axe-core finds no violation (of any impact) with the disclosure open. No run has a script
   error.
"""

from __future__ import annotations

import functools
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import test_canvas_changes as changes_fixture
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap.cli import main

DRIVER = Path(__file__).resolve().parent / "atlas_limits.js"


@functools.cache
def _driven() -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="atlas-limits-")) / "repo"
    rev = changes_fixture.committed(root)
    changes_fixture.model_change(root)
    changes_fixture.source_change(root)
    assert main(["--root", str(root), "extract"]) == 0
    assert main(["--root", str(root), "render", "--base", rev]) == 0
    page = root / "docs" / "map" / "index.html"
    proc = subprocess.run(
        [browser(), str(DRIVER), str(page)], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _inside(run: dict[str, Any], box: dict[str, float]) -> bool:
    return bool(box["left"] >= 0 and box["right"] <= run["width"])


def test_the_disclosure_works_with_the_keyboard_and_only_in_the_map_view() -> None:
    """Acceptance 1, 2 and 3."""
    runs = _driven()["runs"]
    assert len(runs) == 4
    for run in runs:
        assert run["errors"] == [], run
        order = run["order"]
        assert order[-1] == "limits" and "canvas" not in order, order
        assert run["open"] and "Source differences start at the merge base" in run["text"], run
        summary, body = run["summary"], run["body"]
        assert _inside(run, summary) and _inside(run, body), run
        assert summary["top"] >= run["tabs"]["bottom"] and body["top"] >= run["tabs"]["bottom"]
        assert summary["top"] >= run["question"]["bottom"], run
        assert run["scroll"] <= 0, run
        assert run["hasFocus"] and run["inFocus"] is None and run["back"] is not None, run


def test_axe_finds_no_violation_with_the_disclosure_open() -> None:
    """Acceptance 4."""
    out = _driven()
    if not out["axe"]:
        no_axe("the axe-core test needs axe-core on NODE_PATH")
    for run in out["runs"]:
        assert run["axe"] == [], run


@pytest.fixture(autouse=True)
def _needs_browser() -> None:
    browser()
