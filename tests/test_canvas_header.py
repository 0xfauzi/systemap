"""The header of the canvas page and the view part of the renderer (`canvas_header`,
`page_canvas_view`), without a browser.

Acceptance values (the browser checks are in tests/test_canvas_header_browser.py):

1. With `[render] canvas = false` (before step 5: without `[render] canvas`), the output
   is byte-identical to main (d8ac070): the linked pages of the fixture of tests/test_nest_join.py have the SHA-256 digests of the pages
   that d8ac070 writes. A change of the linked pages must change these digests on purpose.
2. The header is one `header` element in front of `main`. It has the views Map, Sequences
   and Changes as buttons with `aria-pressed`, one layer button for each layer of the
   union of the layers of all maps and then All, a select with a label for the same
   layers, and the Find button `find-open`, hidden until the search part wires it.
3. The layers of the top map come first, in the order of `page.tab_layers`. A layer of a
   nested map that the top map does not have comes after them, with the name and the
   question of the first map that has it.
4. Each button of the header has a name: its text. The select has a label. The Find button
   has a title and a text.
5. The text of each view part slot (`canvas_page.SLOTS`) is in the page, and the CSP of the
   page has the digest of each script and style element.
6. The renderer script joins the view part after the scene part, and the drawing calls the
   seam (`viewCard`, `viewFlow`, `viewOver`) and keeps the header band (`HEAD_H`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from test_canvas_page import DATA, _loaded, _made, _read

from systemap import canvas_data, canvas_header, canvas_page, page, page_canvas
from systemap.model import all_layers

# The pages that d8ac070 writes for the fixture without `[render] canvas`.
MAIN_PAGES = {
    "index.html": "d9bee9a146cc26b71d152d1094495ae1c71c9942197e19936c14b8474cf96b58",
    "Gateway/index.html": "5e9140682ede81da4bfef80e99c42d5bc53a550fff41e2cfa13f1180eaa565e0",
}


@pytest.fixture(scope="module")
def linked_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _made(tmp_path_factory.mktemp("linked"), "[render]\ncanvas = false\n")


@pytest.fixture(scope="module")
def canvas_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _made(tmp_path_factory.mktemp("header"), "[render]\ncanvas = true\n")


def _data(root: Path) -> dict[str, Any]:
    found = DATA.search(_read(root, "index.html"))
    assert found is not None
    return dict(json.loads(found.group(1).replace("\\u003c", "<")))


def test_the_linked_pages_stay_as_on_main(linked_root: Path) -> None:
    """Acceptance 1."""
    for rel, digest in MAIN_PAGES.items():
        assert hashlib.sha256((linked_root / "docs" / "map" / rel).read_bytes()).hexdigest() == (
            digest
        ), rel
    cfg, tree, facts = _loaded(linked_root)
    del cfg, facts
    assert len(tree.maps) == len(MAIN_PAGES)


def test_the_header_has_the_views_the_layers_and_find(canvas_root: Path) -> None:
    """Acceptance 2 and 4."""
    top = _read(canvas_root, "index.html")
    head = re.search(r"<body>(<header class=\"cbar\" id=\"canvas-head\">.*?</header>)<main>", top)
    assert head is not None
    text = head.group(1)
    views = re.findall(r'<button type="button" data-view="(\w+)" aria-pressed="(\w+)">(\w+)<', text)
    assert views == [
        ("map", "true", "Map"),
        ("sequences", "false", "Sequences"),
        ("changes", "false", "Changes"),
    ]
    assert '<nav class="cbar__views" aria-label="Views">' in text
    found = canvas_header.layers(_data(canvas_root))
    buttons = re.findall(r'data-layer="([^"]+)" aria-pressed="(\w+)" tabindex="(-?\d)"', text)
    assert buttons == [(lay["id"], "false", "-1") for lay in found] + [("all", "true", "0")]
    for lay in found:
        assert f">{lay['n']}</button>" in text
        assert f'<option value="{lay["id"]}">{lay["n"]}</option>' in text
    assert '<div class="cbar__layers" role="toolbar" aria-label="Layer">' in text
    assert '<label for="canvas-layer">Layer</label><select id="canvas-layer">' in text
    find = re.search(r'<button type="button" class="cbar__find" id="find-open"[^>]*>', text)
    assert find is not None and " hidden" in find.group(0) and 'title="Find"' in find.group(0)
    assert '<span class="cbar__find-label">Find</span>' in text
    assert '<h1 class="cbar__name">join</h1>' in text


def test_the_layers_of_the_top_map_come_first(
    canvas_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 3."""
    data = _data(canvas_root)
    cfg, tree, facts = _loaded(canvas_root)
    del cfg, facts
    top = [lay.id for lay in page.tab_layers(tree.top.model, tree.top.meaning)]
    found = [lay["id"] for lay in canvas_header.layers(data)]
    assert found[: len(top)] == top
    extra = {
        "maps": [
            {"layers": [{"id": "data", "n": "Data", "q": "Q1", "e": []}]},
            {
                "layers": [
                    {"id": "agents", "n": "Agents", "q": "Q2", "e": [0]},
                    {"id": "data", "n": "Other", "q": "Q3", "e": []},
                ]
            },
        ]
    }
    assert canvas_header.layers(extra) == [
        {"id": "data", "n": "Data", "q": "Q1"},
        {"id": "agents", "n": "Agents", "q": "Q2"},
    ]
    # The canvas data gives the layers of each map in the tab order of the linked page.
    # The header keeps that order.
    by_id = {m["id"]: m for m in data["maps"]}
    for m in tree.maps:
        tab = [lay.id for lay in page.tab_layers(m.model, m.meaning)]
        assert [lay["id"] for lay in by_id[m.id]["layers"]] == tab, m.id
    # System context comes first when its layer has flows, also when the model gives it
    # later (`page.tab_layers`).
    given = [lay.id for lay in all_layers(tree.top.model, tree.top.meaning)]
    assert given.index("system") > 0

    # canvas_data uses the rule of `page.tab_layers`, so the two modules read the change.
    def system_flows(model: object, meaning: object, lid: str) -> tuple[list[int], list[str]]:
        return [0] if lid == "system" else [], []

    monkeypatch.setattr(canvas_data, "reading", system_flows)
    monkeypatch.setattr(page, "reading", system_flows)
    assert [lay["id"] for lay in canvas_data._layers(tree.top)[0]] == ["system"] + [
        lid for lid in given if lid != "system"
    ]


def test_the_slots_of_the_view_parts(canvas_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance 5."""
    cfg, tree, facts = _loaded(canvas_root)
    data = canvas_data.build(cfg, tree, facts)
    monkeypatch.setitem(
        canvas_page.SLOTS,
        "css",
        (".slot-a{color:red}",),
    )
    monkeypatch.setitem(canvas_page.SLOTS, "head", ('<span id="slot-head">H</span>',))
    monkeypatch.setitem(canvas_page.SLOTS, "after", ('<div id="slot-after">A</div>',))
    text = canvas_page.build(canvas_page.tree_theme(cfg, tree), data)
    assert ".slot-a{color:red}" in text
    head = text[text.index("<header") : text.index("</header>")]
    assert '<span id="slot-head">H</span>' in head
    assert head.index("slot-head") < head.index("find-open")
    assert text.index('<div id="slot-after">A</div>') > text.index("</main>")
    policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', text)
    assert policy is not None
    for tag in ("script", "style"):
        for body in re.findall(rf"<{tag}>(.*?)</{tag}>", text, re.S):
            digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in policy.group(1), tag


def test_the_script_joins_the_view_part() -> None:
    """Acceptance 6."""
    script = page_canvas.SCRIPT
    assert script.index("var VIEW = {mode: 'map'") > script.index("var DATA = JSON.parse")
    assert script.index("var VIEW = {mode: 'map'") < script.index("function drawFlows(")
    for name in ("viewCard(c)", "viewFlow(f)", "viewOver(m, a, ox, oy, alpha)", "ownKeys(e)"):
        assert name in script, name
    assert "HEAD_H + 14" in script and "P_TOP = P_TOP0 + HEAD_H" in script
    assert "'|' + VIEW.epoch + '|'" in script
