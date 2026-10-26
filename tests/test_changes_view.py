"""The Changes view: the link that opens it, and the map changes that it shows.

A pull request comment links to `<page>#changes`. The page must open the Changes view
for that link, with a revision comparison or without one, and keep the link while the
reader stays in the view.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample, write_tree

from systemap import config, delta_model, nest, page, page_changes
from systemap.cli import main
from systemap.delta_model import Item, MapChange

SCENARIO = r"""
function viewlink(page) {
  const {doc, win} = page;
  const report = {mode: doc.body.dataset.mode, hash: win.location.hash,
    status: (doc.getElementById('linkstatus') || {textContent: ''}).textContent,
    pressed: doc.querySelector('button[data-mode="change"]').getAttribute('aria-pressed')};
  doc.querySelector('button[data-mode="understand"]').click();
  report.afterMap = {mode: doc.body.dataset.mode, hash: win.location.hash};
  doc.querySelector('button[data-mode="change"]').click();
  report.afterChanges = {mode: doc.body.dataset.mode, hash: win.location.hash};
  return report;
}
"""

RULES = r"""
function rules(page) {
  const {doc} = page, A = doc.getElementById('changemap').systemap;
  const panel = doc.getElementById('change-panel'), report = {};
  ['Writer', 'Ledger', 'Reader'].forEach(id => { A.select(id); report[id] = panel.textContent; });
  return report;
}
"""

COMPARISON: dict[str, Any] = {
    "has_change": True,
    "base": "main",
    "head": "feature",
    "direct": {"Reader"},
    "adjacent": set(),
    "modules": {"pkg.reader"},
    "flow_artifacts": set(),
    "per_component": {"Reader": {"modules": ["pkg.reader"], "gained": {}, "surface": {}}},
    "files": 1,
    "reach_known": True,
    "unparsed": [],
}


def drive(
    html: str, tmp_path: Path, hash_: str, name: str = "viewlink", scenario: str = SCENARIO
) -> dict[str, Any]:
    """Run the page scripts under the Node DOM harness with a link fragment."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated navigation JavaScript needs Node")
    out = tmp_path / "map.html"
    out.write_text(html, encoding="utf-8")
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    start = "location: {hash: '',"
    assert driver.count(start) == 1
    driver = driver.replace(start, f"location: {{hash: {json.dumps(hash_)},")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        f"const scenarios = {{keyboard, framing, submap, theme, workspace, {name}}};",
    )
    harness = tmp_path / f"{name}.js"
    harness.write_text(driver + scenario, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(out), "--scenario", name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return dict(json.loads(result.stdout))


@pytest.mark.parametrize("compared", [True, False])
def test_the_changes_link_opens_the_changes_view(
    sample: Sample, tmp_path: Path, compared: bool
) -> None:
    ch = COMPARISON if compared else {"has_change": False}
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, ch)
    report = drive(html, tmp_path, "#changes")
    assert report["mode"] == "change"
    assert report["pressed"] == "true"
    assert report["hash"] == "#changes"
    assert report["status"] == "", "the link is not a missing component"
    # The other views remove the link. Changes puts it back.
    assert report["afterMap"] == {"mode": "understand", "hash": ""}
    assert report["afterChanges"] == {"mode": "change", "hash": "#changes"}


def test_without_the_link_the_page_opens_the_map(sample: Sample, tmp_path: Path) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, COMPARISON
    )
    report = drive(html, tmp_path, "")
    assert report["mode"] == "understand"
    assert report["hash"] == ""


def test_a_selected_component_with_changed_source_gives_its_rules(
    sample: Sample, tmp_path: Path
) -> None:
    """The change must keep the rules of a component with changed source."""
    ch = {**COMPARISON, "direct": {"Reader", "Writer"}}
    ch["per_component"] = {
        **COMPARISON["per_component"],
        "Writer": {"modules": ["pkg.writer"], "gained": {}, "surface": {}},
    }
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, ch)
    report = drive(html, tmp_path, "#changes", "rules", RULES)
    assert "Rules for this component" in report["Writer"]
    assert "1The writer never reads the input itself." in report["Writer"]
    assert "2Every record is written once." in report["Writer"]
    # A component without changed source, or without rules, gives no rules.
    assert "Rules for this component" not in report["Ledger"]
    assert "Rules for this component" not in report["Reader"]


SOURCE_CARD = r"""
function sourcecard(page) {
  const {doc} = page, A = doc.getElementById('changemap').systemap;
  A.select('Reader');
  return {text: doc.getElementById('change-panel').textContent};
}
"""


def test_a_type_name_that_is_an_object_key_gives_the_source_card(
    sample: Sample, tmp_path: Path
) -> None:
    """Audit finding g1page-2. Before the change, the type name `constructor` without a
    category stopped the card script with a TypeError."""
    surface = {
        "added": {"types": ["constructor", "__proto__", "toString", "Plain"]},
        "categories": {"Plain": ["type_alias"], "toString": ["hasOwnProperty"]},
    }
    ch = {**COMPARISON, "per_component": {"Reader": {**COMPARISON["per_component"]["Reader"]}}}
    ch["per_component"]["Reader"]["surface"] = surface
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, ch)
    report = drive(html, tmp_path, "#changes", "sourcecard", SOURCE_CARD)
    assert (
        "Added types: constructor, __proto__, toString (hasOwnProperty), Plain (type alias)."
        in report["text"]
    )


# ---- the map changes: the model at the comparison base against the page model ---------

CONFIG = """
[package_roots]
"pkg" = "pkg"
"""

BASE_SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read() -> str:\n    return 'text'\n",
    "pkg/writer.py": """
        from pkg.reader import read


        def write() -> str:
            return read()
    """,
    "pkg/store.py": "def keep(text: str) -> None:\n    return None\n",
    "pkg/spare.py": "def spare() -> int:\n    return 0\n",
}

HEAD_SOURCE = {
    # The writer now keeps the text in the store and asks the audit.
    "pkg/writer.py": """
        from pkg.audit import check
        from pkg.reader import read
        from pkg.store import keep


        def write() -> str:
            text = read()
            check(text)
            keep(text)
            return text
    """,
    "pkg/audit.py": "def check(text: str) -> bool:\n    return bool(text)\n",
}

MODEL = """
from systemap import Component, Container, Flow, Invariant, Journey, Meaning, Model, Region, Step

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="{reader_does}", implemented_by=("pkg.reader",), entry="read",
              region="core", x=60, y=90),
    Component(id="Writer", does="Writes the text.", implemented_by=("pkg.writer",),
              entry="write", region="core", x=250, y=90),
    Component(id="Store", does="Keeps the text.", implemented_by=("pkg.store",), kind="store",
              region="core", x=440, y=90),
    {last_component}
)
FLOWS = (
    Flow("Reader", "Writer", "text", "data", source_refs=("pkg.reader:read@{digest}",)),
    Flow("Writer", "Store", "records", "data"),
    {last_flow}
)
INVARIANTS = (
    Invariant(1, "The writer keeps each text.", {governs}),
    {last_invariant}
)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=FLOWS, flow_kinds=(), invariants=INVARIANTS)
MEANING = Meaning(
    plain={{"Reader": "reader", "Writer": "writer", "Store": "store", {last_plain}}},
    relations={{("Reader", "Writer"): "{relation}",
               ("Writer", "Store"): "The writer keeps the records.",
               {last_relation}}},
    journeys=(
        Journey(id="write-text", label="Write the text", starts="Reader", steps=(
            Step(("Reader",), (), ("Reader", "Writer"), "The reader gives the text."),
            Step(("Writer",), (), ("Writer", "Store"), "The writer keeps the text."),
        )),
        {last_journey}
    ),
)
"""

BASE_MODEL = MODEL.format(
    reader_does="Reads.",
    last_component=(
        'Component(id="Spare", does="Spare.", implemented_by=("pkg.spare",), entry="spare", '
        'region="core", x=60, y=200),'
    ),
    digest="1" * 64,
    last_plain='"Spare": "spare"',
    last_flow='Flow("Spare", "Writer", "extra", "data"),',
    governs='("Writer", "Store")',
    last_invariant='Invariant(2, "The spare gives nothing.", ("Spare",)),',
    relation="The reader gives the text.",
    last_relation='("Spare", "Writer"): "The spare gives more.",',
    last_journey=(
        'Journey(id="spare", label="Give more", starts="Spare", steps=(Step(("Spare",), (), '
        '("Spare", "Writer"), "The spare gives more."),)),'
    ),
)

HEAD_MODEL = MODEL.format(
    reader_does="Reads the text.",
    last_component=(
        'Component(id="Audit", does="Examines the text.", implemented_by=("pkg.audit",), '
        'entry="check", region="core", x=60, y=200),'
    ),
    # A new digest for the same source record is a renewed review, not a change.
    digest="2" * 64,
    last_plain='"Audit": "audit"',
    last_flow='Flow("Writer", "Audit", "text <checked>", "control"),',
    # The same components in a different order are not a change.
    governs='("Store", "Writer")',
    last_invariant='Invariant(3, "The audit examines each text.", ("Audit",)),',
    relation="The reader gives the text to the writer.",
    last_relation='("Writer", "Audit"): "The writer asks the audit.",',
    last_journey="",
)


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout.strip()


def commit(root: Path, files: dict[str, str], message: str) -> None:
    write_tree(root, files)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two commits: the change adds, removes, and changes map items."""
    git(tmp_path, "init", "-q")
    commit(tmp_path, {**BASE_SOURCE, "systemap.toml": CONFIG, "map/model.py": BASE_MODEL}, "base")
    (tmp_path / "pkg/spare.py").unlink()
    commit(tmp_path, {**HEAD_SOURCE, "map/model.py": HEAD_MODEL}, "head")
    return tmp_path


def changes(root: Path) -> MapChange:
    cfg = config.load(root)
    top = nest.load(cfg).top
    return delta_model.for_page(cfg, "", top.model, top.meaning, git(root, "rev-parse", "HEAD~1"))


def test_the_map_changes_give_each_added_removed_and_changed_item(repo: Path) -> None:
    found = changes(repo)
    assert found.error == "" and found.base == git(repo, "rev-parse", "HEAD~1")
    assert found.components == (
        Item("changed", "Reader", ("description",)),
        Item("added", "Audit"),
        Item("removed", "Spare"),
    )
    assert found.flows == (
        Item("changed", "text", ("sentence",), ("Reader", "Writer"), 0),
        Item("added", "text <checked>", (), ("Writer", "Audit"), 2),
        Item("removed", "extra", ends=("Spare", "Writer")),
    )
    assert found.sequences == (Item("removed", "Give more"),)
    assert found.invariants == (
        Item("removed", "2", text="The spare gives nothing."),
        Item("added", "3", text="The audit examines each text."),
    )
    assert found.count == 9


def test_a_base_model_that_does_not_load_gives_the_reason(repo: Path) -> None:
    commit(repo, {"map/model.py": "MODEL = (\n"}, "broken model")
    commit(repo, {"map/model.py": HEAD_MODEL}, "fixed")
    found = changes(repo)
    short = git(repo, "rev-parse", "--short=7", "HEAD~1")
    assert found.count == 0
    assert found.error.startswith(f"the model at {short} does not load: ")
    git(repo, "rm", "-q", "map/model.py")
    git(repo, "commit", "-q", "-m", "no model")
    commit(repo, {"map/model.py": HEAD_MODEL}, "model again")
    short = git(repo, "rev-parse", "--short=7", "HEAD~1")
    assert changes(repo).error == f"map/model.py is not in the commit {short}"


def test_a_map_that_is_not_in_the_base_tree_is_all_added(repo: Path) -> None:
    cfg = config.load(repo)
    top = nest.load(cfg).top
    base = git(repo, "rev-parse", "HEAD~1")
    found = delta_model.for_page(cfg, "Writer", top.model, top.meaning, base)
    assert [item.how for item in found.components] == ["added"] * 4
    assert delta_model.for_page(cfg, "", top.model, top.meaning, "").error


def panel_of(found: MapChange) -> str:
    ch: dict[str, Any] = {**COMPARISON, "comparison_base": "a" * 40, "map": found}
    return page_changes.panel(ch)


def test_the_panel_lists_the_map_changes_and_each_row_selects_its_item(repo: Path) -> None:
    html = panel_of(changes(repo))
    section = html[html.index('id="chg-map"') : html.index('id="chg-flows"')]
    assert '<h3 class="chg-cap">MAP CHANGES</h3><span class="chg-sec__n">9</span>' in section
    heads = [h4.split("<")[0] for h4 in section.split('<h4 class="chg-h4">')[1:]]
    assert heads == ["Components", "Flows", "Sequences", "Rules"]
    # A row for an item on this page selects it: the component, the flow or the sequence.
    assert '<button type="button" class="chg-seq chg-mc chg-mc--c" data-change-go="Reader">' in (
        section
    )
    assert '<b>Reader</b><span class="chg-mc__what">description</span>' in section
    assert 'data-change-edge="2"><span class="chg-mc__name"><b>text &lt;checked&gt;</b>' in section
    # A removed item is not on this page: its row has no action and a dashed border.
    assert (
        '<div class="chg-seq chg-mc chg-mc--c chg-mc--gone chg-mc--still"><span '
        'class="chg-mc__name"><b>Spare</b></span><span class="chg-seq__steps">removed</span></div>'
    ) in section
    assert '<b>Rule 2</b><span class="chg-mc__what">The spare gives nothing.</span>' in section
    assert "The list compares the model at <code>" in section
    limits = html[html.index("NOT IN THIS COMPARISON") :]
    assert "Map changes compare the model at <code>" in limits
    assert "It cannot show a component, flow or sequence" not in limits


def test_the_panel_says_when_the_model_did_not_change_or_did_not_load() -> None:
    same = panel_of(MapChange(base="b" * 40))
    assert "The model of this page is the same as the model at <code>bbbbbbb</code>." in same
    broken = panel_of(MapChange(base="b" * 40, error="the model at bbbbbbb does not load: x"))
    assert 'id="chg-map"' not in broken
    assert (
        "It cannot show a component, flow or sequence that the change added or removed, "
        "because the model at bbbbbbb does not load: x.</p>"
    ) in broken


def test_a_group_shows_ten_rows_and_the_quantity_of_the_others() -> None:
    many = tuple(Item("added", f"C{n}") for n in range(13))
    html = panel_of(MapChange(components=many, base="b" * 40))
    assert html.count('data-change-go="C') == 10
    assert '<p class="chg-foot">3 more components.</p>' in html


def test_render_with_a_base_shows_the_map_changes(repo: Path) -> None:
    """The page that `systemap render --base` writes has the map changes."""
    assert main(["--root", str(repo), "extract"]) == 0
    assert main(["--root", str(repo), "render", "--base", "HEAD~1"]) == 0
    html = (repo / "docs/map/index.html").read_text(encoding="utf-8")
    assert '<h3 class="chg-cap">MAP CHANGES</h3><span class="chg-sec__n">9</span>' in html
    assert 'data-change-go="Audit"' in html
