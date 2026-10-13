"""The page follow-up repairs: symbol claims, group markers, theme CSS values and mark boxes.

Acceptance:

- followup-page-8: a component with a symbol claim lists each entry point that starts that
  symbol. A public function starts the function of its name. This is true for a Python
  fixture and a TypeScript fixture. A symbol claim does not list an entry point that starts
  no symbol: a TypeScript bin starts the code of its full module, and a subcommand target
  is the name of its console script. Thus the claim `<module>:<script name>` does not list
  the subcommand, and the claim `<module>:<bin name>` does not list the bin. A module claim
  lists all entry points of its module, as before.
- followup-layer-id: with a custom layer ID `flow`, `tags`, `zones` or `job`, the sequence
  script puts its marks in the group of the tags and its lines in the group of the flows.
  The group markers use the attribute `data-part`, which no layer ID gives.
- followup-theme-css: a theme CSS value that contains ";", "{" or "}" gives ValueError.
  No default theme value is refused.
- followup-labels-time: while the sequence marks do not change, a pan does not read the
  boxes of the marks again. After a change to a mark, the next relabel call reads them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import Sample, write_tree
from test_page_results import drive
from test_schematic_names import change_layer_sample

from systemap import config, extract, page, page_data
from systemap import theme as theme_mod
from systemap.model import Component, Model

PYTHON_TREE = {
    "systemap.toml": 'language = "python"\n',
    "pyproject.toml": (
        '[project]\nname = "shop"\nversion = "1"\n[project.scripts]\nshop = "shop.cli:main"\n'
    ),
    "src/shop/__init__.py": "def start() -> None:\n    pass\n",
    "src/shop/cli.py": (
        "import argparse\n\n\n"
        "def shop() -> None:\n    pass\n\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_subparsers().add_parser('serve')\n"
    ),
}
TYPESCRIPT_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web","bin":{"web":"src/cli.ts"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/cli.ts": "export function web(): void {}\n",
    "src/index.ts": "export function start(): void {}\n",
}


def _facts(tmp_path: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(tmp_path, tree)
    return extract.build(config.load(tmp_path))


def _points(facts: dict[str, Any], *claims: str) -> list[str]:
    card = Component("Card", "Holds the claims.", implemented_by=claims)
    model = Model((100, 100), (), (), (card,), (), ())
    return list(page_data.sources(model, facts)["Card"]["points"])


def _module_of(facts: dict[str, Any], kind: str) -> str:
    return str(next(p["module"] for p in facts["entry_points"] if p["kind"] == kind))


def test_a_python_symbol_claim_lists_the_entry_points_of_its_symbol(tmp_path: Path) -> None:
    facts = _facts(tmp_path, PYTHON_TREE)
    root = _module_of(facts, "public_function")
    cli = _module_of(facts, "subcommand")
    assert _points(facts, f"{root}:start") == ["start() in shop"]
    assert _points(facts, f"{cli}:main") == ["shop (console script)", "main() in shop.cli"]
    # The subcommand target is the script name `shop`, not the function `shop`.
    assert _points(facts, f"{cli}:shop") == []
    assert "shop serve (subcommand)" in _points(facts, cli)


def test_a_typescript_symbol_claim_lists_the_entry_points_of_its_symbol(tmp_path: Path) -> None:
    facts = _facts(tmp_path, TYPESCRIPT_TREE)
    index = next(p["module"] for p in facts["entry_points"] if p["name"] == "start")
    cli = _module_of(facts, "console_script")
    assert _points(facts, f"{index}:start") == [f"start() in {index}"]
    # The bin `web` starts the full module. The function `web` is a different symbol.
    assert _points(facts, f"{cli}:web") == []
    assert "web (console script)" in _points(facts, cli)


@pytest.mark.parametrize("kind", ["route", "unknown_kind"])
def test_only_a_kind_with_a_known_symbol_matches(kind: str) -> None:
    point = {"kind": kind, "name": "GET /x", "module": "pkg.web", "target": "index"}
    facts = {"components": {"pkg.web": {}}, "entry_points": [point]}
    expected = ["GET /x (route)"] if kind == "route" else []
    assert _points(facts, "pkg.web:index") == expected


# ---- followup-layer-id: a layer ID with the name of a group marker -------------------

GROUPS = r"""
function groups(page){
  const {win, svg} = page;
  svg.page.journey.route(0); runFrames(win);
  const view = svg.querySelector('.view');
  const kids = view.childNodes.filter((n) => n.nodeType === 1);
  const marks = svg.querySelector('.seq-marks'), lines = svg.querySelector('.seq-lines');
  // The group of the tags is a child of the view, after the flow labels, with no class.
  const tags = marks.parentNode;
  return {marks: tags.parentNode === view && !tags.getAttribute('class')
      && !tags.querySelector('.flowlbl') && kids.indexOf(tags) > kids.findIndex(
        (n) => n.querySelector('.flowlbl')),
    lines: lines.parentNode.parentNode === view && lines.parentNode === kids.find(
      (n) => n.querySelector('path.flow'))};
}
"""


@pytest.mark.parametrize("name", ["flow", "tags", "zones", "job"])
def test_a_layer_with_a_group_name_keeps_the_sequence_marks_in_place(
    sample: Sample, tmp_path: Path, name: str
) -> None:
    s, _t = change_layer_sample(sample, name)
    html = page.build(s.cfg, s.model, s.meaning, s.theme, s.facts, {"has_change": False})
    assert f'data-layer="{name}"' in html
    assert drive(html, tmp_path, "groups", GROUPS) == {"marks": True, "lines": True}


# ---- followup-theme-css: a theme value that can change other CSS rules --------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ink", "red;--bg:#000000"),
        ("ink", "red}body{display:none"),
        ("ink", "red{"),
        ("font_ui", '"Inter";x'),
        ("font_ui", '"Inter"}body{display:none'),
    ],
)
def test_a_theme_value_with_a_css_mark_is_refused(key: str, value: str) -> None:
    with pytest.raises(ValueError, match=rf"The theme value {key} contains"):
        theme_mod.resolve({key: value}, [])


def test_the_default_theme_values_and_a_quoted_font_stay_accepted() -> None:
    for scheme in theme_mod.SCHEMES:
        theme_mod.resolve({"scheme": scheme}, [])
    out = theme_mod.resolve({"font_ui": '"Inter", "Segoe UI", sans-serif'}, [])
    assert out["font_ui"] == '"Inter", "Segoe UI", sans-serif'


# ---- followup-labels-time: the label script reads the mark boxes only after a change ---

MARK_READS = r"""
function markreads(page){
  const {doc, win, svg, A} = page, P = svg.page;
  doc.querySelector('[data-mode="trace"]').click(); runFrames(win);
  P.journey.start(0); runFrames(win);
  A.view.restore({k:0.7, tx:0, ty:0}, true); runFrames(win);
  const g = svg.querySelector('.seq-marks');
  let reads = 0;
  g.childNodes.forEach((c) => { const box = c.getBoundingClientRect.bind(c);
    c.getBoundingClientRect = () => { reads += 1; return box(); }; });
  // Two pans with no change to the marks.
  A.view.restore({k:0.7, tx:5, ty:0}, true); runFrames(win);
  A.view.restore({k:0.7, tx:9, ty:0}, true); runFrames(win);
  const still = reads;
  // A change to one mark, and then a pan.
  g.childNodes[0].setAttribute('transform', 'translate(1 0)');
  A.view.restore({k:0.7, tx:12, ty:0}, true); runFrames(win);
  return {marks: g.childNodes.length, still, after: reads - still};
}
"""


def test_a_pan_does_not_read_the_mark_boxes_again(sample: Sample, tmp_path: Path) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    report = drive(html, tmp_path, "markreads", MARK_READS)
    assert report["marks"] > 0
    assert report["still"] == 0
    assert report["after"] == report["marks"]
