"""The committed self-map page is the atlas page, and the canvas page of the self-map
passes axe-core (step 5 of docs/design/nested-canvas.md, stage 9 of docs/design/atlas.md).

From step 5 to stage 9, `systemap refresh` wrote the canvas page into docs/map. From stage
9, the atlas page is the default, and `systemap refresh` writes the atlas page there. The
website publishes this page as the live example. The browser part uses the driver of
tests/test_canvas_access.py and skips as that test does, except when SYSTEMAP_BROWSER_TESTS
is "required" (the CI job canvas-browser).

Acceptance values (acceptance 1 changed in stage 9: before, it was the canvas page; the
page of acceptance 2 is the canvas page of the self-map in a temporary folder, because the
committed page is not the canvas page now):

1. docs/map/index.html is the atlas page: it has one element `script#atlas-data` with the
   data of the top map of this repository, no element `script#canvas-data`, and no
   `window.systemapWorkspace` object of the linked page. Its policy has a script digest
   and no `'unsafe-inline'` script source.
2. C4 on the canvas page of the self-map (`[render] page = "canvas"`): axe-core AXE_VERSION
   finds no violation in each of the 24 runs of the driver (1440 x 900 and 390 x 844
   pixels, light and dark, at the top map and at the card CLI, with no focus, with the
   focus on a link of the list and on a card). No run has a script error or a policy
   error.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_atlas_page import DATA as ATLAS_DATA
from test_canvas_access import AXE_VERSION, _access, _axe, no_axe
from test_canvas_page import DATA

from systemap import config, facts_file, nest, page_csp, render_pages

ROOT = Path(__file__).resolve().parent.parent
SELF_MAP = ROOT / "docs" / "map" / "index.html"


def test_the_committed_self_map_is_the_atlas_page() -> None:
    """Acceptance 1."""
    html = SELF_MAP.read_text(encoding="utf-8")
    found = ATLAS_DATA.findall(html)
    assert len(found) == 1, "one data element"
    assert not DATA.findall(html), "no data element of the canvas page"
    data = json.loads(found[0])
    tree = nest.load(config.load(ROOT))
    top = next(m for m in data["maps"] if m["id"] == "")
    assert {c["id"] for c in top["cards"]} == {c.id for c in tree.top.model.components}
    assert "window.systemapWorkspace" not in html
    policy = page_csp.of_page(html)
    scripts = next(p for p in policy.split("; ") if p.startswith("script-src "))
    assert "'sha256-" in scripts and "'unsafe-inline'" not in scripts, scripts


@pytest.fixture(scope="module")
def canvas_self_map(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The canvas page of the self-map, with the committed facts."""
    cfg = replace(config.load(ROOT), render_page="canvas")
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    tree = nest.load(cfg)
    top, html = render_pages.pages(cfg, tree, facts)[0]
    assert top is tree.top and DATA.findall(html)
    out = tmp_path_factory.mktemp("canvas-self") / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def test_axe_core_finds_no_issue_on_the_self_map(canvas_self_map: Path) -> None:
    """Acceptance 2 (C4)."""
    version = _axe()
    if version != AXE_VERSION:
        no_axe(f"the C4 test needs axe-core {AXE_VERSION} for Node, found {version or 'none'}")
    runs = _access("--axe", str(canvas_self_map), "CLI")["runs"]
    assert len(runs) == 24
    for run in runs:
        assert run["version"] == AXE_VERSION and run["errors"] == [], run
        assert run["violations"] == [], run
    assert {run["hash"] for run in runs} == {"", "#CLI"}
