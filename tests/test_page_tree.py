"""The map tree of a page: the Map tree panel, the search across maps, and the roll-up.

The tests use the `nested` fixture (the top map, Gateway, and Style). The Node driver runs
the page scripts. No test calls Jev or an agent."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from test_keyboard import DRIVER, needs_node
from test_nested import edit, git, nested  # noqa: F401 - a fixture

from systemap import config, nest, page, page_tree
from systemap.cli import main


def run(*argv: str) -> int:
    return main(list(argv))


def read(root: Path, rel: str) -> str:
    return (root / "docs/map" / rel).read_text(encoding="utf-8")


def tree_data(html: str) -> dict[str, Any]:
    start = html.index("<script>window.systemapWorkspace=") + len(
        "<script>window.systemapWorkspace="
    )
    found: dict[str, Any] = json.loads(html[start : html.index(";</script>", start)])["tree"]
    return found


def test_a_judgement_line_belongs_to_the_map_of_its_prefix(nested: Path) -> None:  # noqa: F811
    tree = nest.load(config.load(nested))
    lines = [
        "no sentence: Reader -> Gateway has no relation sentence",
        "Gateway: no sentence: App -> Routes has no relation sentence",
        "Gateway: boundary flow: Routes sends to actor Style, and the parent map has no flow",
        "Gateway/Deep: single module: X has one module",
    ]
    assert [page_tree.line_map(line) for line in lines] == [
        "",
        "Gateway",
        "Gateway",
        "Gateway/Deep",
    ]
    assert page_tree.finding_counts(tree, lines) == {"": 1, "Gateway": 2, "Style": 0}
    assert page_tree.finding_counts(tree, None) is None


def test_a_render_without_open_lines_says_not_examined(nested: Path) -> None:  # noqa: F811
    tree = nest.load(config.load(nested))
    ov = page_tree.overview("demo", tree, None)
    html = page_tree.panel(ov, "Style")
    assert '<span class="tree__at" aria-current="page">Style</span>' in html
    assert "2 components, not examined" in html and "0 findings" not in html
    assert page_tree.data(ov, "Style")["maps"][2] == ["Style", "", 2, None, None]


def test_a_tree_with_one_map_has_no_panel_and_no_index(tmp_path: Path) -> None:
    single = nest.Tree(
        (
            nest.Map(
                "",
                tmp_path,
                "map/model.py",
                page.Model((0, 0), (), (), (), (), ()),
                page.Meaning(plain={}),
                {},
            ),
        )
    )
    ov = page_tree.overview("one", single, frozenset())
    assert page_tree.panel(ov, "") == "" and page_tree.data(ov, "") is None


def test_the_search_index_has_the_other_maps_with_the_actors_last(nested: Path) -> None:  # noqa: F811
    assert run("--root", str(nested), "refresh") == 0
    data = tree_data(read(nested, "Gateway/index.html"))
    assert data["at"] == 1 and data["up"] == "../" and data["top"] == "demo"
    assert [row[0] for row in data["maps"]] == ["", "Gateway", "Style"]
    # No row of the current map: the page itself gives its components to the Find dialog.
    assert {row[0] for row in data["index"]} == {0, 2}
    style = [(row[1], data["kinds"][row[2]]) for row in data["index"] if row[0] == 2]
    assert style == [
        ("Cache", "store"),
        ("Compiler", "component"),
        ("Gateway", "actor"),
        ("Writer", "actor"),
    ]
    assert all(len(row[3]) <= page_tree.PLAIN_CHARACTERS for row in data["index"])


@needs_node
def test_find_gives_the_components_of_the_other_maps_after_this_map(nested: Path) -> None:  # noqa: F811
    assert run("--root", str(nested), "refresh") == 0
    args = [
        shutil.which("node") or "node",
        str(DRIVER),
        str(nested / "docs/map/Gateway/index.html"),
    ]
    proc = subprocess.run(
        [*args, "--scenario", "othermaps"], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    queries = report["queries"]
    # A quiet result: no row of a different map without a search text.
    assert queries[""]["other"] == []
    assert queries["Cache"]["other"] == [["Cache", "in Style"]]
    # The results of this map come first. The key is the map and the component.
    assert queries["Gateway"]["groups"][-1] == "Other maps"
    assert queries["Writer"]["other"] == [["Writer", "in demo"], ["Writer", "in Style"]]
    assert report["went"] == "../Style/index.html#Cache"


def _changed_style_and_rule(root: Path) -> None:
    """Commit the base. Then change one card of Style and add a boundary rule to the top."""
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    edit(root, "map/style.py", 'does="Compiles a guide."', 'does="Compiles one guide."')
    edit(root, "map/model.py", "Container, Flow,", "Container, Flow, ImportRule,")
    edit(
        root,
        "map/model.py",
        "flows=FLOWS, flow_kinds=())",
        'flows=FLOWS, flow_kinds=(), import_rules=(ImportRule("gateway-imports", '
        '"allow_imports", ("Gateway",), ("Style",), "Records the imports at the base."),))',
    )


def test_the_changes_go_up_the_tree(nested: Path) -> None:  # noqa: F811
    _changed_style_and_rule(nested)
    assert run("--root", str(nested), "render", "--base", "HEAD") == 0
    top = read(nested, "index.html")
    assert '<h3 class="chg-cap">CHANGES IN NESTED MAPS</h3>' in top
    assert (
        '<a href="Style/index.html#changes">Style</a><span class="chg-mc__what">1 changed component</span>'
        in top
    )
    assert '<h3 class="chg-cap">BOUNDARY CHANGES</h3>' in top
    assert (
        "added import rule <code>gateway-imports</code> in the top map. "
        "Reason: Records the imports at the base." in top
    )
    # The Map tree: the top map and Style changed, Gateway did not.
    data = tree_data(top)
    assert [row[3] for row in data["maps"]] == [True, False, True]
    assert '<span class="tree__n">2 components, changed, ' in top
    # The change map marks the card with a change inside, with text and a second outline.
    change_map = top[top.index('id="changemap"') :]
    assert "opens the map Style with 2 components, changed inside" in change_map
    assert "node__inside-changed" in change_map and "changed inside</text>" in change_map
    assert 'data-id="Gateway"' in change_map
    gateway_card = change_map[change_map.index('data-id="Gateway"') :]
    assert "changed inside" not in gateway_card[: gateway_card.index('class="node ')]
    # A page without maps below it has no roll-up sections.
    assert "CHANGES IN NESTED MAPS" not in read(nested, "Style/index.html")
