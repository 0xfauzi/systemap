"""The change keys of the canvas data: the change marks and the roll-up (`canvas_changes`).

The tests use the tree of tests/three_levels.py in a Git repository. The base commit has
the first models and source. The working tree then has a change. The change data of each
map comes from `render_pages.page_change`, as `systemap render --base` makes it. No test
calls Jev or an agent. tests/test_canvas_changes_browser.py has the browser tests.

Acceptance values (written before the first run, step 4 of docs/design/nested-canvas.md):

1. For each map of the three-level tree with a base revision, the card marks (`cm`, with
   "none" for a card that is not in `cm`) and the lost flows (`cl`) in the canvas data are
   equal to the marks of the change map of the linked page of that map
   (`schematic_change.change_marks`, in the detail data of the change map).
2. The roll-up, from the step 8 cases of tests/test_page_tree.py and
   tests/test_boundary_changes.py on the branch claude/nested-step-8:
   - A model change only in a map on level 3 gives "changed inside" (`ci`) on the card
     that opens the map on the path to it, in the top map, on level 1 and on level 2, and
     on no other card.
   - The roll-up counts each map and flags a changed map below it.
   - A map with only a changed invariant is a changed map.
   - A base tree that does not load gives no "changed inside" and the reason (`cr.e`), not
     a count of zero.
   - A source change alone gives no roll-up count and no "changed inside". The cards that
     open a map on the path to the changed module have the mark "changed", because their
     claims cover the module.
3. Without change data, no map has a change key. The keys function adds no byte: the text
   is equal to the text with `canvas_changes.keys` replaced by a function that gives no
   key. (The bytes of d8ac070 for the same tree are compared one time in
   bench/jev/canvas_changes_size.py.) With change data, C1 of the M11 tree is measured by
   that script.
4. The canvas page has the element for a page without a comparison only when no map has a
   comparison. The element has the text and the command of `page_changes.empty`.
5. The tag text has a contrast of 4.5 or more in the light and the dark scheme: on_change
   on change (CHANGED), change on map (TESTS), ink_2 on map (IMPORTS) and ink_2 on raised
   (the badge "changed inside"). A ring in the change color on the map color has 3 or more.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import three_levels
from conftest import write_tree
from test_theme import contrast

from systemap import (
    canvas_changes,
    canvas_data,
    canvas_page,
    config,
    facts_file,
    nest,
    page,
    page_changes,
    render_pages,
    theme,
)
from systemap import (
    change as change_mod,
)
from systemap.cli import main
from systemap.delta_model import CHANGED, Item, MapChange
from systemap.model import Component, Meaning, Model

DEEP = "P0/Q0/Deep"
KEYS = ("cm", "cl", "cr", "ci")


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def committed(root: Path) -> str:
    """Write the three-level tree in a new Git repository. Give the base commit."""
    write_tree(root, three_levels.files())
    for command in ("place", "extract"):
        assert main(["--root", str(root), command]) == 0
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return git(root, "rev-parse", "HEAD")


def edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def model_change(root: Path) -> None:
    """Change the `does` text of D1 in the map on level 3 below P0 and Q0."""
    edit(root, f"map/{three_levels._file(DEEP)}", "Gives the detail.", "Gives the full detail.")


def source_change(root: Path) -> None:
    """Add a function to the module of D1 below P0 and Q0."""
    edit(
        root,
        "pkg/p0/q0/deep/d1.py",
        "    return key\n",
        "    return key\n\n\ndef more() -> int:\n    return 1\n",
    )


Loaded = tuple[config.Config, nest.Tree, dict[str, Any], dict[str, dict[str, Any]]]


def changed(root: Path, base: str) -> Loaded:
    """Extract the working tree and give the change data of each map against `base`."""
    assert main(["--root", str(root), "extract"]) == 0
    cfg = config.load(root)
    found = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    source = change_mod.source_change(cfg, base, facts, change_mod.WORKING_TREE)
    of = render_pages.page_change(cfg, facts, base, change_mod.WORKING_TREE, source, {})
    return cfg, found, facts, {m.id: of(m) for m in found.maps}


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    root = tmp_path_factory.mktemp("base") / "repo"
    return root, committed(root)


def copy(base: tuple[Path, str], to: Path) -> tuple[Path, str]:
    root = to / "repo"
    shutil.copytree(base[0], root)
    return root, base[1]


@pytest.fixture(scope="module")
def both(base: tuple[Path, str], tmp_path_factory: pytest.TempPathFactory) -> Loaded:
    """A model change and a source change in the map on level 3 below P0 and Q0."""
    root, rev = copy(base, tmp_path_factory.mktemp("both"))
    model_change(root)
    source_change(root)
    return changed(root, rev)


def maps_of(loaded: Loaded) -> dict[str, dict[str, Any]]:
    cfg, found, facts, changes = loaded
    return {m["id"]: m for m in canvas_data.build(cfg, found, facts, changes=changes)["maps"]}


def test_the_marks_are_the_marks_of_the_change_map(both: Loaded) -> None:
    """Acceptance 1."""
    cfg, found, facts, changes = both
    data = maps_of(both)
    seen = set()
    for m in found.maps:
        _svg, detail = page._change_svg(cfg, m.model, m.meaning, m.theme, facts, changes[m.id])
        meta = json.loads(detail)["_meta"]["change"]
        shown = data[m.id]
        marks = {c["id"]: shown.get("cm", {}).get(c["id"], "none") for c in shown["cards"]}
        assert marks == meta["cards"], m.id
        assert shown.get("cl", []) == meta["lost"], m.id
        seen |= set(marks.values())
    assert {"changed", "imports", "end", "none"} <= seen
    assert data[DEEP]["cl"] and data[DEEP]["cm"]["D1"] == "changed"


def test_a_change_on_level_3_marks_the_cards_on_the_path(
    base: tuple[Path, str], tmp_path: Path
) -> None:
    """Acceptance 2: a model change only in the map on level 3."""
    root, rev = copy(base, tmp_path)
    model_change(root)
    data = maps_of(changed(root, rev))
    inside = {map_id: m["ci"] for map_id, m in data.items() if "ci" in m}
    assert inside == {"": ["P0"], "P0": ["Q0"], "P0/Q0": ["Deep"]}
    assert data[DEEP]["cr"] == {"n": 1, "w": "1 changed component"}
    assert data[""]["cr"] == {"n": 0, "b": 1}
    assert data["P1"]["cr"] == {"n": 0}
    # A model change gives no source change mark.
    assert all("cm" not in m and "cl" not in m for m in data.values())


def test_a_source_change_alone_gives_no_roll_up(base: tuple[Path, str], tmp_path: Path) -> None:
    """Acceptance 2: a source change alone."""
    root, rev = copy(base, tmp_path)
    source_change(root)
    data = maps_of(changed(root, rev))
    assert all(m["cr"] == {"n": 0} and "ci" not in m for m in data.values())
    assert data[""]["cm"]["P0"] == "changed"
    assert data["P0"]["cm"]["Q0"] == "changed"
    assert data["P0/Q0"]["cm"]["Deep"] == "changed"
    assert data[DEEP]["cm"]["D1"] == "changed"


def model(*components: Component) -> Model:
    return Model((0, 0), (), (), components, (), ("data",), ())


def tree(top: Model, *children: tuple[str, str, Model]) -> nest.Tree:
    """Give a tree of models, from tests/test_boundary_changes.py on claude/nested-step-8."""
    path = Path("map/model.py")
    maps = [nest.Map("", path, "map/model.py", top, Meaning(plain={}), {})]
    maps += [
        nest.Map(
            map_id,
            path,
            f"map/{map_id}.py",
            m,
            Meaning(plain={}),
            {},
            parent,
            map_id.split("/")[-1],
        )
        for map_id, parent, m in children
    ]
    return nest.Tree(tuple(maps))


def change(*items: Item) -> MapChange:
    return MapChange(components=items, base="abc1234")


GATE = Component("Gateway", "Takes the requests.", implemented_by=("app.gate",), map="g.py")
INSIDE = model(Component("Routes", "Routes.", implemented_by=("app.gate",)))


def test_the_roll_up_counts_each_map_and_flags_a_changed_map_below() -> None:
    """Acceptance 2: the case of tests/test_boundary_changes.py."""
    deep = tree(model(GATE), ("Gateway", "", INSIDE), ("Gateway/Routes", "Gateway", INSIDE))
    found = canvas_changes.records(
        deep, {"Gateway/Routes": change(Item(CHANGED, "X", ("modules",)))}
    )
    assert found[""] == canvas_changes.Rollup("", (), 0, True)
    assert found["Gateway"].below and not found["Gateway"].own
    assert found["Gateway/Routes"] == canvas_changes.Rollup(
        "Gateway/Routes", ((CHANGED, "component", 1),), 1, False
    )
    assert canvas_changes.counted(found["Gateway/Routes"]) == "1 changed component"


def test_a_map_with_only_a_changed_invariant_is_a_changed_map() -> None:
    """Acceptance 2."""
    head = tree(model(GATE), ("Gateway", "", INSIDE))
    only = MapChange(invariants=(Item(CHANGED, "2", ("text",)),), base="abc1234")
    found = canvas_changes.records(head, {"Gateway": only})
    assert found["Gateway"].own == 1 and found[""].below
    assert canvas_changes.counted(found["Gateway"]) == "1 changed invariant"


def test_a_base_tree_that_does_not_load_is_not_known(both: Loaded) -> None:
    """Acceptance 2: the reason, and no "changed inside"."""
    cfg, found, facts, changes = both
    lost = {
        k: {**v, "map": MapChange(error="Git cannot read the base tree")}
        for k, v in changes.items()
    }
    data = {m["id"]: m for m in canvas_data.build(cfg, found, facts, changes=lost)["maps"]}
    for m in data.values():
        assert m["cr"] == {"e": "Git cannot read the base tree"}
        assert "ci" not in m
    # The source change marks stay.
    assert data[DEEP]["cm"]["D1"] == "changed"
    none = {k: {kk: vv for kk, vv in v.items() if kk != "map"} for k, v in changes.items()}
    rolled = canvas_changes.rollups(found, none)
    assert not rolled.known and rolled.error == canvas_changes.NO_MAP_CHANGES


def test_without_change_data_there_is_no_change_key(
    both: Loaded, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 3."""
    cfg, found, facts, changes = both
    plain = canvas_data.build(cfg, found, facts)
    assert not any(key in m for m in plain["maps"] for key in (*KEYS, "ch"))
    with_data = canvas_data.text(canvas_data.build(cfg, found, facts, changes=changes))
    monkeypatch.setattr(canvas_changes, "keys", lambda *_args: {})
    without = canvas_data.build(cfg, found, facts, changes=changes)
    assert canvas_data.text(plain) == canvas_data.text(canvas_data.build(cfg, found, facts))
    assert not any(key in m for m in without["maps"] for key in KEYS)
    assert len(with_data) > len(canvas_data.text(without))


def test_the_empty_text_is_only_on_a_page_without_a_comparison(both: Loaded) -> None:
    """Acceptance 4."""
    cfg, found, facts, changes = both
    t = canvas_page.tree_theme(cfg, found)
    plain = canvas_page.build(t, canvas_data.build(cfg, found, facts))
    compared = canvas_page.build(t, canvas_data.build(cfg, found, facts, changes=changes))
    assert plain.count('id="canvas-changes-empty"') == 1
    assert "This page has no revision comparison" in plain
    assert f"<code>{page_changes.COMMAND}</code>" in plain
    assert 'aria-label="Copy the command"' in plain
    assert 'id="canvas-changes-empty"' not in compared


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_tag_text_has_contrast(scheme: str) -> None:
    """Acceptance 5."""
    p = theme.LIGHT if scheme == "light" else theme.DARK
    assert contrast(p["on_change"], p["change"]) >= 4.5
    assert contrast(p["change"], p["map"]) >= 4.5
    assert contrast(p["ink_2"], p["map"]) >= 4.5
    assert contrast(p["ink_2"], p["raised"]) >= 4.5
    assert contrast(p["change"], p["map"]) >= 3
