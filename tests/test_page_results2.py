"""The page and its scripts: the repairs for the Codex results page-11 to page-15.

Acceptance:

- page-11: a child map of the card `javascript:alert(1);0` has the link
  `javascript%3Aalert%281%29%3B0/index.html`. No link or frame source in the page has a
  URL scheme other than `data` or `about`. A double-click on the card puts the same
  relative path in the frame. A rule number in the model is text, not markup.
- page-12: with an actor `constructor`, the Map view panel, the phone list, the Find
  dialog and the Changes view operate without an error. The panels give the actor and
  its artifacts, and the Find dialog gives no prototype function as a region.
- page-13: in the Changes view, the selection of the component `A"` marks its card and
  gives no selector error. The harness refuses each selector that is not correct CSS.
- page-14: with a layer of more than 20 flows and the region `operate|extra`, the flow
  groups operate without an error, and each group between regions has the boxes of its
  two regions. Two region pairs that give the same text with `|` stay two groups.
- page-15: the sequences of the top map and of the child map each include a different
  entry point. Each page gives `1 of 1` and no missing entry point, for a Python and a
  TypeScript fixture.

The Node harness in tests/page_driver.js operates the page scripts. It is not a browser.
Its selector engine accepts selectors that a browser refuses. Thus the page-13 and page-14
scenarios examine each selector strictly. A test in headless Chrome showed each failure
on the base revision.
"""

from __future__ import annotations

import dataclasses
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from conftest import Sample, write_tree
from test_changes_view import COMPARISON
from test_entry_coverage_scope import (
    INNER,
    PYTHON_NAMES,
    PYTHON_TREE,
    TOP,
    TYPESCRIPT_NAMES,
    TYPESCRIPT_TREE,
)
from test_page_results import drive

from systemap import config, facts_file, nest, page
from systemap import theme as theme_mod
from systemap.cli import main
from systemap.model import Flow, Invariant, Meaning, Model, all_layers

# The harness refuses a selector that a browser refuses: each part must be a tag, an ID,
# a class, an attribute test with a quoted or plain value, `:not`, `:scope`, or a
# combinator.
SELECTOR_PART = "|".join(
    (
        r'\[[A-Za-z_][A-Za-z0-9_-]*(?:=(?:"(?:[^"\\\n]|\\.)*"|'
        r"'(?:[^'\\\n]|\\.)*'|-?[A-Za-z_][A-Za-z0-9_-]*))?\]",
        r"[A-Za-z*][A-Za-z0-9_-]*",
        r"[#.][A-Za-z_-][A-Za-z0-9_-]*",
        r":(?:not|scope)\b",
        r"[(),>]",
    )
)
STRICT = (
    "function strictSelectors() {\n  const part = new RegExp("
    + json.dumps(r"\s*(?:" + SELECTOR_PART + r")\s*")
    + ", 'y');\n"
    + r"""  ['querySelector', 'querySelectorAll'].forEach((name) => {
    const base = Element.prototype[name];
    Element.prototype[name] = function (sel) {
      for (let at = 0; at < sel.length;) {
        part.lastIndex = at;
        const m = part.exec(sel);
        if (!m || !m[0].length) throw new SyntaxError(`'${sel}' is not a valid selector`);
        at = part.lastIndex;
      }
      return base.call(this, sel);
    };
  });
}
"""
)


def rename(obj: Any, old: str, new: str) -> Any:
    """Give a copy of a model value with each string `old` replaced by `new`."""
    if isinstance(obj, str):
        return new if obj == old else obj
    if isinstance(obj, tuple):
        return tuple(rename(x, old, new) for x in obj)
    if isinstance(obj, dict):
        return {rename(k, old, new): rename(v, old, new) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        fields = {f.name: rename(getattr(obj, f.name), old, new) for f in dataclasses.fields(obj)}
        return dataclasses.replace(obj, **{k: v for k, v in fields.items() if v is not None})
    return obj


def renamed(sample: Sample, old: str, new: str) -> tuple[Model, Meaning]:
    return rename(sample.model, old, new), rename(sample.meaning, old, new)


def build(
    sample: Sample,
    model: Model,
    meaning: Meaning,
    ch: dict[str, Any] | None = None,
    nesting: page.Nesting | None = None,
) -> str:
    t = theme_mod.resolve({}, all_layers(model, meaning))
    return page.build(
        sample.cfg, model, meaning, t, sample.facts, ch or {"has_change": False}, nesting
    )


# ---- page-11: model values in URLs and in markup -------------------------------------

CARD = "javascript:alert(1);0"
QUOTED = "javascript%3Aalert%281%29%3B0/index.html"


class _Urls(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.urls += [v or "" for k, v in attrs if k in ("href", "src")]


def _child_tree(sample: Sample, model: Model, meaning: Meaning) -> nest.Tree:
    top = nest.Map("", Path("map/model.py"), "map/model.py", model, meaning, sample.theme)
    child = nest.Map(
        CARD, Path("map/c.py"), "map/c.py", model, meaning, sample.theme, parent="", card=CARD
    )
    return nest.Tree((top, child))


SUBMAP = r"""
function childframe(page) {
  const {doc, win, svg} = page;
  const node = svg.querySelectorAll('.node').find((n) => n.dataset.id === childCard());
  dispatch(node, new EventImpl('dblclick', {bubbles: true}));
  runFrames(win);
  return {hidden: doc.getElementById('submap').hidden,
    src: doc.getElementById('submapframe').getAttribute('src')};
}
"""


def test_a_child_map_link_is_a_quoted_relative_path(sample: Sample, tmp_path: Path) -> None:
    model, meaning = renamed(sample, "Reader", CARD)
    model = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(c, map="c.py") if c.id == CARD else c for c in model.components
        ),
    )
    tree = _child_tree(sample, model, meaning)
    nesting = page.nesting_of(sample.cfg, tree, tree.top)
    assert nesting.opens[CARD]["href"] == QUOTED
    html = build(sample, model, meaning, nesting=nesting)
    parser = _Urls()
    parser.feed(html)
    assert QUOTED in parser.urls
    assert all(urlsplit(u).scheme in ("", "data", "about") for u in parser.urls), parser.urls
    scenario = f"function childCard() {{ return {json.dumps(CARD)}; }}\n" + SUBMAP
    report = drive(html, tmp_path, "childframe", scenario)
    assert report == {"hidden": False, "src": QUOTED}


FRAGMENT = r"""
function fragment(page) {
  const {win, A} = page;
  A.select('50% B');
  const link = win.location.hash;
  const again = page.reload(link);
  return {link, selected: again.A.state.focus};
}
"""


def test_the_link_of_a_selected_component_is_encoded(sample: Sample, tmp_path: Path) -> None:
    """A component ID with a percent sign gives an encoded fragment that selects it again."""
    model, meaning = renamed(sample, "Reader", "50% B")
    report = drive(build(sample, model, meaning), tmp_path, "fragment", FRAGMENT)
    assert report == {"link": "#50%25%20B", "selected": "50% B"}


RULE = '1"><img src=x onerror=alert(1)>'

RULES = r"""
function rulemarks(page) {
  const {doc, svg} = page;
  const report = {};
  doc.querySelector('button[data-mode="change"]').click();
  doc.getElementById('changemap').systemap.select('Writer');
  report.change = doc.getElementById('change-panel').textContent;
  svg.page.setMode('trace');
  svg.page.journey.start(0);
  svg.page.journey.step(svg.systemap.journeys[0].steps.length - 1);
  report.step = doc.getElementById('step-evidence').textContent;
  doc.getElementById('find-open').click();
  const input = doc.getElementById('pal-input');
  input.value = 'rule';
  dispatch(input, new EventImpl('input', {bubbles: true}));
  report.find = doc.getElementById('pal-list').textContent;
  report.images = doc.querySelectorAll('img').length;
  return report;
}
"""


class _Images(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.images += tag == "img"


def test_a_rule_number_is_text(sample: Sample, tmp_path: Path) -> None:
    text = "The writer never reads the input itself."
    rule = Invariant(RULE, text, governs=("Writer",))  # type: ignore[arg-type]
    model = dataclasses.replace(sample.model, invariants=(rule,))
    ch = {
        **COMPARISON,
        "direct": {"Writer"},
        "per_component": {"Writer": {"modules": ["pkg.writer"], "gained": {}, "surface": {}}},
    }
    html = build(sample, model, sample.meaning, ch)
    parser = _Images()
    parser.feed(html)
    assert parser.images == 0
    report = drive(html, tmp_path, "rulemarks", RULES)
    assert report["images"] == 0
    assert RULE + text in report["change"]
    assert RULE + text in report["step"]
    assert RULE in report["find"]


# ---- page-12: an actor with the ID constructor ---------------------------------------

ACTOR = (
    STRICT
    + r"""
function actorpanels(page) {
  const {doc, svg} = page;
  strictSelectors();
  const report = {};
  svg.page.setLayer('system');
  if (svg.page.renderRead) svg.page.renderRead();
  report.map = doc.getElementById('inspector-empty').textContent;
  doc.getElementById('find-open').click();
  const input = doc.getElementById('pal-input');
  input.value = 'constructor';
  dispatch(input, new EventImpl('input', {bubbles: true}));
  report.find = doc.getElementById('pal-list').textContent;
  return report;
}
function actorphone(page) {
  const {doc, svg} = page;
  strictSelectors();
  svg.page.setLayer('system');
  return {phone: doc.getElementById('phone-list').textContent};
}
"""
)

CHANGED_ACTOR = r"""
function actorchange(page) {
  const {doc} = page;
  doc.querySelector('button[data-mode="change"]').click();
  doc.getElementById('changemap').systemap.select('constructor');
  return {panel: doc.getElementById('change-panel').textContent};
}
"""


def test_an_actor_named_constructor_is_in_each_panel(sample: Sample, tmp_path: Path) -> None:
    model, meaning = renamed(sample, "User", "constructor")
    html = build(sample, model, meaning)
    report = drive(html, tmp_path, "actorpanels", ACTOR)
    assert "constructor" in report["map"] and "Sends input." in report["map"]
    assert "constructor" in report["find"]
    assert "function" not in report["find"] and "native code" not in report["find"]
    phone = drive(html, tmp_path, "actorphone", ACTOR, "--phone", "--viewport", "390x844")
    assert "constructor" in phone["phone"] and "Sends input." in phone["phone"]


def test_the_changes_panel_selects_an_actor_named_constructor(
    sample: Sample, tmp_path: Path
) -> None:
    model, meaning = renamed(sample, "User", "constructor")
    html = build(sample, model, meaning, COMPARISON)
    report = drive(html, tmp_path, "actorchange", CHANGED_ACTOR)
    assert "The comparison has no source changes for this component." in report["panel"]


# ---- page-13: a component ID with a quotation mark in the Changes view ---------------

QUOTE = (
    STRICT
    + r"""
function quotecard(page) {
  const {doc} = page;
  strictSelectors();
  doc.querySelector('button[data-mode="change"]').click();
  doc.getElementById('changemap').systemap.select('A"');
  const cards = doc.querySelectorAll('[data-change-card]');
  return {current: cards.filter((c) => c.getAttribute('aria-current') === 'true')
    .map((c) => c.dataset.changeCard), picked: !!doc.getElementById('chg-pick')};
}
"""
)


def test_a_component_with_a_quotation_mark_selects_its_change_card(
    sample: Sample, tmp_path: Path
) -> None:
    model, meaning = renamed(sample, "Reader", 'A"')
    ch = {
        **COMPARISON,
        "direct": {'A"'},
        "per_component": {'A"': {"modules": ["pkg.reader"], "gained": {}, "surface": {}}},
    }
    report = drive(build(sample, model, meaning, ch), tmp_path, "quotecard", QUOTE)
    assert report == {"current": ['A"'], "picked": False}


# ---- page-14: a region ID with the mark | --------------------------------------------

GROUPS = (
    STRICT
    + r"""
function pipegroups(page) {
  const {A, svg} = page;
  strictSelectors();
  svg.page.setLayer('record');
  svg.page.setLayer('all');
  const groups = svg.page.groups.groups('all');
  return {lines: groups.filter((g) => !g.inside).map((g) => ({a: g.a.id, b: g.b.id,
    boxes: !!(g.a.box && g.b.box), n: g.edges.length})),
    drawn: svg.querySelectorAll('.fg-group').length};
}
"""
)


def _many_flows(model: Model) -> Model:
    extra = tuple(Flow("Reader", "Writer", f"part {k}", "data") for k in range(18))
    return dataclasses.replace(model, flows=model.flows + extra)


def test_a_region_with_the_separator_mark_keeps_its_flow_groups(
    sample: Sample, tmp_path: Path
) -> None:
    model, meaning = renamed(sample, "work", "operate|extra")
    report = drive(build(sample, _many_flows(model), meaning), tmp_path, "pipegroups", GROUPS)
    ends = {(g["a"], g["b"]) for g in report["lines"]}
    assert ("operate|extra", "keep") in ends or ("keep", "operate|extra") in ends
    assert all(g["boxes"] for g in report["lines"])
    assert report["drawn"] == len(report["lines"]) >= 2


def test_two_region_pairs_with_the_same_joined_text_stay_two_groups(
    sample: Sample, tmp_path: Path
) -> None:
    """The regions `a|b` and `c` give the text `a|b|c`. The regions `a` and `b|c` give the
    same text."""
    model, meaning = renamed(sample, "work", "a|b")
    model = rename(model, "keep", "c")
    regions = model.regions + (
        dataclasses.replace(model.regions[0], id="a", label="A", box=(240, 340, 180, 40)),
        dataclasses.replace(model.regions[0], id="b|c", label="BC", box=(440, 340, 180, 40)),
    )
    left = dataclasses.replace(model.components[1], id="Left", region="a", y=350, x=260)
    right = dataclasses.replace(model.components[1], id="Right", region="b|c", y=350, x=460)
    flows = model.flows + tuple(Flow("Left", "Right", f"item {k}", "data") for k in range(3))
    model = dataclasses.replace(
        _many_flows(model),
        canvas=(900, 420),
        regions=regions,
        components=model.components + (left, right),
    )
    model = dataclasses.replace(model, flows=model.flows + flows[len(sample.model.flows) :])
    meaning = dataclasses.replace(meaning, plain={**meaning.plain, "Left": "l", "Right": "r"})
    report = drive(build(sample, model, meaning), tmp_path, "pipegroups", GROUPS)
    ends = {frozenset((g["a"], g["b"])) for g in report["lines"]}
    assert frozenset(("a|b", "c")) in ends
    assert frozenset(("a", "b|c")) in ends


# ---- page-15: entry point coverage of nested maps ------------------------------------


def _coverage(html: str) -> dict[str, Any]:
    found = re.search(r"window\.systemapWorkspace=(.*?);</script>", html)
    assert found is not None
    return dict(json.loads(found.group(1))["sequences"]["coverage"])


@pytest.mark.parametrize(
    ("tree", "names"),
    [(PYTHON_TREE, PYTHON_NAMES), (TYPESCRIPT_TREE, TYPESCRIPT_NAMES)],
    ids=["python", "typescript"],
)
def test_each_page_counts_the_entry_points_of_its_map(
    tmp_path: Path, tree: dict[str, str], names: dict[str, str]
) -> None:
    top = TOP.format(cli=names["cli"], inner=names["inner"], start=names["top"])
    inner = INNER.format(tool=names["tool"], start=names["nested"])
    write_tree(tmp_path, {**tree, "map/model.py": top, "map/inner.py": inner})
    assert main(["--root", str(tmp_path), "place"]) == 0
    assert main(["--root", str(tmp_path), "extract"]) == 0
    cfg = config.load(tmp_path)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    maps = nest.load(cfg)
    for m in maps.maps:
        nesting = page.nesting_of(cfg, maps, m, facts)
        html = page.build(
            cfg, m.model, m.meaning, m.theme, facts, {"has_change": False}, nesting=nesting
        )
        coverage = _coverage(html)
        assert {k: coverage[k] for k in ("total", "covered", "missing")} == {
            "total": 1,
            "covered": 1,
            "missing": [],
        }, m.id
