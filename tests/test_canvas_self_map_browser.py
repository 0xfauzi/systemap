"""The committed self-map page is the canvas page (step 5 of docs/design/nested-canvas.md).

From step 5, `systemap refresh` writes the canvas page into docs/map. The website publishes
this page as the live example. The browser part uses the driver of
tests/test_canvas_access.py and skips as that test does, except when SYSTEMAP_BROWSER_TESTS
is "required" (the CI job canvas-browser).

Acceptance values:

1. docs/map/index.html is the canvas page: it has one element `script#canvas-data` with the
   data of the top map of this repository, and no `window.systemapWorkspace` object of the
   linked page. Its policy has a script digest and no `'unsafe-inline'` script source.
2. C4 on the committed page: axe-core AXE_VERSION finds no violation in each of the 24
   runs of the driver (1440 x 900 and 390 x 844 pixels, light and dark, at the top map and
   at the card CLI, with no focus, with the focus on a link of the list and on a card). No
   run has a script error or a policy error.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_canvas_access import AXE_VERSION, _access, _axe, no_axe
from test_canvas_page import DATA

from systemap import config, nest, page_csp

ROOT = Path(__file__).resolve().parent.parent
SELF_MAP = ROOT / "docs" / "map" / "index.html"


def test_the_committed_self_map_is_the_canvas_page() -> None:
    """Acceptance 1."""
    html = SELF_MAP.read_text(encoding="utf-8")
    found = DATA.findall(html)
    assert len(found) == 1, "one data element"
    data = json.loads(found[0])
    tree = nest.load(config.load(ROOT))
    top = next(m for m in data["maps"] if m["id"] == "")
    assert {c["id"] for c in top["cards"]} == {c.id for c in tree.top.model.components}
    assert "window.systemapWorkspace" not in html
    policy = page_csp.of_page(html)
    scripts = next(p for p in policy.split("; ") if p.startswith("script-src "))
    assert "'sha256-" in scripts and "'unsafe-inline'" not in scripts, scripts


def test_axe_core_finds_no_issue_on_the_self_map() -> None:
    """Acceptance 2 (C4)."""
    version = _axe()
    if version != AXE_VERSION:
        no_axe(f"the C4 test needs axe-core {AXE_VERSION} for Node, found {version or 'none'}")
    runs = _access("--axe", str(SELF_MAP), "CLI")["runs"]
    assert len(runs) == 24
    for run in runs:
        assert run["version"] == AXE_VERSION and run["errors"] == [], run
        assert run["violations"] == [], run
    assert {run["hash"] for run in runs} == {"", "#CLI"}
