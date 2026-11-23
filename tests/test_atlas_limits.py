"""The limits of a revision comparison on the atlas page, through the commands.

The disclosure "Not in this comparison" (`atlas_marks.limits`) gets the change data of the top
map from `render_pages.pages`. These tests make that data with the commands, not by hand:
`systemap render --base` and the render of `systemap live` (`live_render.render_tree`). They use
the three-level tree of tests/test_canvas_changes.py in a Git repository, with a model change
and a source change in the working tree. No test calls Jev or an agent.
tests/test_atlas_limits_browser.py has the browser tests.

Acceptance values, written on 2026-11-19 after the review of stage 9, before the first run of
these tests:

1. `systemap render --base REV` exits 0, and docs/map/index.html has the disclosure of the
   limits one time. Its text is `atlas_marks.limits` of the change data that
   `render_pages.page_change` gives for the top map with the same base and head, and it has
   the merge base of the comparison.
2. `systemap render` with no base writes a page with no disclosure and no style of the
   disclosure.
3. The render of `systemap live` with the base REV gives an index.html with the disclosure of
   the change data of the top map (`change.for_page` of the working tree). The live render
   with no base gives no disclosure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import test_canvas_changes as changes_fixture

from systemap import atlas_marks, change, config, facts_file, nest, render_pages, serve
from systemap.cli import main

LIMITS = '<details class="limits" id="atlas-limits">'


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """The three-level tree with a model change and a source change since the commit REV."""
    root = tmp_path_factory.mktemp("limits") / "repo"
    rev = changes_fixture.committed(root)
    changes_fixture.model_change(root)
    changes_fixture.source_change(root)
    assert main(["--root", str(root), "extract"]) == 0
    return root, rev


def _loaded(root: Path) -> tuple[config.Config, nest.Tree, dict[str, object]]:
    cfg = config.load(root)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


def test_render_base_gives_the_limits_of_the_top_map(repo: tuple[Path, str]) -> None:
    """Acceptance 1 and 2."""
    root, rev = repo
    assert main(["--root", str(root), "render", "--base", rev]) == 0
    html = (root / "docs" / "map" / "index.html").read_text(encoding="utf-8")
    cfg, tree, facts = _loaded(root)
    source = change.source_change(cfg, rev, facts, "HEAD")
    of = render_pages.page_change(cfg, facts, rev, "HEAD", source, {})
    top = of(tree.top)
    expected = atlas_marks.limits(top)
    assert expected and html.count(LIMITS) == 1
    assert expected in html
    assert top["comparison_base"] and "Source differences start at the merge base" in expected
    assert main(["--root", str(root), "render"]) == 0
    plain = (root / "docs" / "map" / "index.html").read_text(encoding="utf-8")
    assert 'id="atlas-limits"' not in plain and atlas_marks.LIMITS_CSS not in plain


def test_the_live_render_gives_the_limits_of_the_top_map(repo: tuple[Path, str]) -> None:
    """Acceptance 3."""
    root, rev = repo
    found = serve.render_tree(root, rev)
    cfg, tree, facts = _loaded(root)
    source = change.source_change(cfg, rev, facts, change.WORKING_TREE)
    top = change.for_page(cfg, tree.top, rev, facts, change.WORKING_TREE, source)
    expected = atlas_marks.limits(top)
    assert expected and found.files["index.html"].count(LIMITS) == 1
    assert expected in found.files["index.html"]
    assert 'id="atlas-limits"' not in serve.render_tree(root, "").files["index.html"]
