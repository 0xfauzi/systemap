"""The atlas page, the setting `[render] page` and the page data of the atlas
(`atlas_page`, `atlas_data`, `config_render`, docs/design/atlas.md).

Acceptance values, written before the first run on 2026-11-18:

1. Without `[render] page`, the page is "atlas" and `render_canvas` is true (changed in
   stage 9, when the atlas page became the default; before stage 9 it was "canvas").
   `canvas = true` also gives "atlas". "canvas" gives the canvas page with `render_canvas`
   true. "linked" and `canvas = false` give the linked pages with `render_canvas` false.
2. An unknown value of `[render] page` is a configuration error that names the three
   values. `canvas = false` with `page = "atlas"` is a configuration error.
3. With `page = "atlas"`, `render` writes the atlas page at the top page and the small page
   of the canvas page for each nested map, with a link that names the atlas page.
   `render --check` and `check` exit 0 after the render.
4. The page has one style element and two script elements, and the policy has the digest
   of each of them. The markup has no style attribute, no inline event handler, and no
   URL with a scheme (no external file).
5. The page data is the canvas data object with the relation sentence `y` of each flow
   that has a sentence. The canvas data of the canvas page has no `y`.
6. The atlas page of the map of this repository has 1.5 times the size of the canvas page
   or less (the size limit of the performance budget). Changed on 2026-11-19 after the
   review of stage 9, before the first run: the atlas page has the history data of the
   committed page file (`history_data.stored`), as the default render writes it, and that
   history data is present.
7. The page has the parts for a screen reader: the label and the help text of the canvas,
   the list of the tree and the live region in `main`, and the tablist of the layers.
8. Written on 2026-11-19 after the review of stage 8, before the first run of its test: the
   keyboard sheet has a row for each key of the States, Focus and History views (the arrow
   keys, Home, End and Esc) that names those views, and a row for Space.
9. Written on 2026-11-19 after the review of stage 9, before the first run of its test: with
   a revision comparison, the headline of the atlas page ends with the disclosure "Not in
   this comparison". It has the text of the limits of the linked page
   (`page_changes.comparison_limits`), for example the filtered paths. Without a comparison,
   the page has no such disclosure and no style for it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
from conftest import write_tree
from test_canvas_page import _made, _read
from test_nest_join import CONFIG, SOURCE

from systemap import (
    atlas_data,
    atlas_focus,
    atlas_history,
    atlas_marks,
    atlas_page,
    atlas_states,
    atlas_tools,
    canvas_data,
    canvas_page,
    config,
    config_render,
    facts_file,
    history_data,
    nest,
    page_changes,
    page_csp,
)
from systemap.cli import main

REPO = Path(__file__).resolve().parent.parent
DATA = re.compile(r'<script type="application/json" id="atlas-data">(.*?)</script>', re.S)


def _config(tmp_path: Path, setting: str) -> config.Config:
    write_tree(tmp_path, {"systemap.toml": CONFIG + setting, **SOURCE})
    return config.load(tmp_path)


@pytest.mark.parametrize(
    ("setting", "page", "canvas"),
    [
        ("", "atlas", True),
        ('[render]\npage = "atlas"\n', "atlas", True),
        ('[render]\npage = "canvas"\n', "canvas", True),
        ('[render]\npage = "linked"\n', "linked", False),
        ("[render]\ncanvas = false\n", "linked", False),
        ("[render]\ncanvas = true\n", "atlas", True),
        ('[render]\ncanvas = true\npage = "canvas"\n', "canvas", True),
        ('[render]\ncanvas = true\npage = "atlas"\n', "atlas", True),
        ('[render]\ncanvas = false\npage = "linked"\n', "linked", False),
    ],
)
def test_the_setting_selects_the_page(
    tmp_path: Path, setting: str, page: str, canvas: bool
) -> None:
    """Acceptance 1."""
    cfg = _config(tmp_path, setting)
    assert cfg.render_page == page
    assert cfg.render_canvas is canvas


@pytest.mark.parametrize(
    ("setting", "error"),
    [
        (
            '[render]\npage = "map"\n',
            'render.page must be one of "atlas", "canvas", "linked", not \'map\'',
        ),
        ("[render]\npage = 1\n", 'render.page must be one of "atlas"'),
        (
            '[render]\ncanvas = false\npage = "atlas"\n',
            'render.canvas = false does not agree with render.page = "atlas"',
        ),
        (
            '[render]\ncanvas = true\npage = "linked"\n',
            'render.canvas = true does not agree with render.page = "linked"',
        ),
    ],
)
def test_a_wrong_page_is_a_configuration_error(tmp_path: Path, setting: str, error: str) -> None:
    """Acceptance 2."""
    with pytest.raises(config.ConfigError, match=re.escape(error)):
        _config(tmp_path, setting)


def test_the_three_values_are_in_the_module() -> None:
    assert config_render.PAGES == ("atlas", "canvas", "linked")


@pytest.fixture(scope="module")
def atlas_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _made(tmp_path_factory.mktemp("atlas"), '[render]\npage = "atlas"\n')


def test_render_writes_the_atlas_page(atlas_root: Path) -> None:
    """Acceptance 3."""
    top = _read(atlas_root, "index.html")
    assert '<script type="application/json" id="atlas-data">' in top
    assert 'id="canvas-data"' not in top
    assert "window.systemapCanvas" in top
    nested = _read(atlas_root, "Gateway/index.html")
    assert '<meta http-equiv="refresh" content="0;url=../index.html#Gateway">' in nested
    assert '<a href="../index.html#Gateway">atlas page</a>' in nested
    assert "<canvas" not in nested
    assert main(["--root", str(atlas_root), "render", "--check"]) == 0
    assert main(["--root", str(atlas_root), "check"]) == 0


def test_the_pages_of_the_module_are_the_written_pages(atlas_root: Path) -> None:
    cfg = config.load(atlas_root)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    for m, text in atlas_page.pages(cfg, tree, facts):
        assert m.page_path(cfg).read_text(encoding="utf-8") == text


def _digest(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def test_the_policy_and_the_markup(atlas_root: Path) -> None:
    """Acceptance 4."""
    top = _read(atlas_root, "index.html")
    scripts = re.findall(r"<script>(.*?)</script>", top, re.S)
    styles = re.findall(r"<style>(.*?)</style>", top, re.S)
    assert len(scripts) == 2 and len(styles) == 1
    directives = dict(part.split(" ", 1) for part in page_csp.of_page(top).split("; "))
    assert sorted(directives["script-src"].split()) == sorted(_digest(s) for s in scripts)
    assert directives["style-src-elem"] == _digest(styles[0])
    assert directives["frame-src"] == "'none'"
    markup = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", top, flags=re.S)
    assert re.search(r"<[^>]*\sstyle=", markup) is None
    assert re.search(r"<[^>]*\son[a-z]+=", markup) is None
    # The namespace name of SVG in the icon of the page is a name, not a file.
    names = top.replace("http://www.w3.org/2000/svg", "")
    assert re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}/", names) is None


def _repo() -> tuple[config.Config, nest.Tree, dict[str, object]]:
    cfg = config.load(REPO)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


def test_the_data_has_the_relation_sentence_of_each_flow() -> None:
    """Acceptance 5."""
    cfg, tree, facts = _repo()
    data = atlas_data.build(cfg, tree, facts)
    plain = canvas_data.build(cfg, tree, facts)
    seen = 0
    for m, got, was in zip(tree.maps, data["maps"], plain["maps"], strict=True):
        for flow, item, old in zip(m.model.flows, got["flows"], was["flows"], strict=True):
            assert "y" not in old
            sentence = m.meaning.relation(flow)
            assert item.get("y", "") == sentence
            assert {k: v for k, v in item.items() if k != "y"} == old
            seen += bool(sentence)
    assert seen > 10


def test_the_page_is_in_the_size_limit_of_the_budget() -> None:
    """Acceptance 6."""
    cfg, tree, facts = _repo()
    theme = canvas_page.tree_theme(cfg, tree)
    canvas = canvas_page.build(theme, canvas_data.build(cfg, tree, facts))
    history = history_data.stored(cfg, tree)
    assert history is not None and history.get("commits")
    atlas = atlas_page.build(theme, atlas_data.build(cfg, tree, facts), history)
    assert 'id="atlas-history"' in atlas
    assert len(atlas.encode()) <= 1.5 * len(canvas.encode())
    found = DATA.search(atlas)
    assert found is not None
    assert json.loads(found.group(1))["maps"][0]["flows"]


def test_the_page_has_the_parts_for_a_screen_reader(atlas_root: Path) -> None:
    """Acceptance 7."""
    top = _read(atlas_root, "index.html")
    canvas = re.search(r"<canvas [^>]*>", top)
    assert canvas is not None
    assert 'role="img"' in canvas.group(0)
    assert 'aria-label="System map: join"' in canvas.group(0)
    assert 'aria-describedby="canvas-help"' in canvas.group(0)
    main_part = top[top.index("<main>") : top.index("</main>")]
    assert '<p id="canvas-help" class="sr-only">' in main_part
    assert '<nav id="atlas-tree" class="tree" aria-label="Map tree"></nav>' in main_part
    assert '<p id="atlas-said" class="sr-only" aria-live="polite"></p>' in main_part
    assert '<h1 class="ask__q" id="atlas-ask-q"></h1>' in main_part
    assert 'role="tablist" aria-label="Layers"' in top


# The names of the keys in the keyboard sheet (`atlas_tools.KEYS`).
_SHEET_NAME = {
    "ArrowLeft": "← ↑ → ↓",
    "ArrowRight": "← ↑ → ↓",
    "ArrowUp": "← ↑ → ↓",
    "ArrowDown": "← ↑ → ↓",
    "Home": "Home",
    "End": "End",
    "Escape": "Esc",
}


@pytest.mark.parametrize(
    ("part", "table"),
    [
        (atlas_states.STATES, "SM_KEYS"),
        (atlas_focus.FOCUS, "FC_KEYS"),
        (atlas_history.HISTORY, "HS_KEYS"),
    ],
)
def test_the_keyboard_sheet_has_the_keys_of_each_view(part: str, table: str) -> None:
    """Acceptance 8."""
    found = re.search(r"var " + table + r" = \{([^}]*)\}", part)
    assert found, table
    keys = re.findall(r"(\w+):", found.group(1))
    rows = {key: text for key, text in atlas_tools.KEYS}
    assert keys and all(_SHEET_NAME[key] in rows for key in keys), (table, keys)
    assert "e.key === ' '" in part and "Space" in rows
    for key in keys:
        assert any(view in rows[_SHEET_NAME[key]] for view in ("States", "Focus", "History"))


def test_the_headline_gives_the_limits_of_a_comparison() -> None:
    """Acceptance 9."""
    cfg, tree, facts = _repo()
    theme = canvas_page.tree_theme(cfg, tree)
    data = atlas_data.build(cfg, tree, facts)
    change = {
        "comparison_requested": True,
        "reach_known": False,
        "filtered_paths": ["pkg/locked.py"],
    }
    found = atlas_marks.limits(change)
    page = atlas_page.build(theme, data, limits=found)
    assert "<summary>Not in this comparison</summary>" in found
    assert found in page and atlas_marks.LIMITS_CSS in page
    assert page_changes.comparison_limits(change) in found
    assert "<code>pkg/locked.py</code>" in found
    assert "Effects on other modules are unknown." in found
    assert atlas_marks.limits({}) == atlas_marks.limits(None) == ""
    plain = atlas_page.build(theme, data)
    assert 'id="atlas-limits"' not in plain and atlas_marks.LIMITS_CSS not in plain
