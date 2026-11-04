"""The boundary changes of a map tree, the roll-up of the changes, and the pull request row.

The tests give model fixtures to the pure functions. They do not call Git, Jev, or an agent.
"""

from __future__ import annotations

from pathlib import Path

from systemap import boundary_changes, nest, page_rollup, pr_summary
from systemap.delta_model import CHANGED, Item, MapChange
from systemap.model import Component, ImportRule, Meaning, Model

GATE = Component(
    "Gateway", "Takes the requests.", implemented_by=("app.gate", "app.auth"), map="g.py"
)
STORE = Component("Store", "Keeps the rows.", implemented_by=("app.store",), map="s.py")
PLAIN = Component("Log", "Writes the log.", implemented_by=("app.log",))
RULE = ImportRule("gate-imports", "allow_imports", ("Gateway",), ("Store",), "Records the imports.")
OTHER = ImportRule("log-alone", "forbid_import", ("Log",), ("Store",), "The log is apart.")


def model(*components: Component, rules: tuple[ImportRule, ...] = ()) -> Model:
    return Model((0, 0), (), (), components, (), ("data",), (), rules)


def tree(top: Model, *children: tuple[str, str, Model]) -> nest.Tree:
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


INSIDE = model(Component("Routes", "Routes.", implemented_by=("app.gate",)))


def moved() -> tuple[nest.Tree, nest.Tree]:
    """The claim app.auth goes from Gateway to Store. The rule gets a new target."""
    base = tree(
        model(GATE, STORE, PLAIN, rules=(RULE, OTHER)),
        ("Gateway", "", INSIDE),
        ("Store", "", INSIDE),
    )
    gate = Component("Gateway", GATE.does, implemented_by=("app.gate",), map="g.py")
    store = Component("Store", STORE.does, implemented_by=("app.store", "app.auth"), map="s.py")
    rule = ImportRule(
        "gate-imports",
        "allow_imports",
        ("Gateway",),
        ("Store", "Log"),
        "Records the imports at abc1234.",
    )
    head = tree(
        model(gate, store, PLAIN, rules=(rule, OTHER)),
        ("Gateway", "", INSIDE),
        ("Store", "", INSIDE),
    )
    return base, head


def code(text: str) -> str:
    return f"`{text}`"


def test_a_claim_that_goes_between_two_nested_parts_is_one_move() -> None:
    base, head = moved()
    found = boundary_changes.compute(base, head)
    assert found.moves == (
        boundary_changes.Move("", "app.auth", "Gateway", "Store", ("Gateway", "Store")),
    )
    assert [(c.card, c.gained, c.lost) for c in found.claims] == [
        ("Gateway", (), ("app.auth",)),
        ("Store", ("app.auth",), ()),
    ]
    # Only the rule whose source is a card that opens a map is a boundary rule.
    assert found.rules == (
        boundary_changes.RuleChange(
            CHANGED,
            "",
            "gate-imports",
            ("target components", "reason"),
            "Records the imports at abc1234.",
        ),
    )
    assert found.count == 3


def test_the_rows_connect_the_move_with_the_two_nested_map_changes() -> None:
    found = boundary_changes.compute(*moved())
    rows = boundary_changes.rows(found, {"Gateway": 2, "Store": 1}, code)
    assert rows == [
        "`app.auth` moved from `Gateway` to `Store` in the top map. "
        "Map `Gateway`: 2 changes. Map `Store`: 1 change.",
        "changed import rule `gate-imports` (target components, reason) in the top map. "
        "Reason: Records the imports at abc1234.",
    ]


def test_a_claim_change_without_a_move_has_its_own_row() -> None:
    base = tree(model(GATE), ("Gateway", "", INSIDE))
    gate = Component(
        "Gateway", GATE.does, implemented_by=("app.gate", "app.auth", "app.new"), map="g.py"
    )
    found = boundary_changes.compute(base, tree(model(gate), ("Gateway", "", INSIDE)))
    assert boundary_changes.rows(found, {}, code) == [
        "The claims of `Gateway` in the top map changed. Added: `app.new`. Map `Gateway`: 0 changes."
    ]


def test_a_tree_with_the_same_boundaries_has_no_boundary_change() -> None:
    base, _head = moved()
    assert boundary_changes.compute(base, base).count == 0
    assert boundary_changes.rows(boundary_changes.compute(base, base), {}, code) == []


def test_within_keeps_the_changes_of_a_map_and_of_the_maps_below_it() -> None:
    found = boundary_changes.BoundaryChanges(
        claims=(
            boundary_changes.ClaimChange("", "A"),
            boundary_changes.ClaimChange("A", "B"),
            boundary_changes.ClaimChange("A/B", "C"),
            boundary_changes.ClaimChange("AB", "D"),
        )
    )
    assert [c.card for c in found.within("").claims] == ["A", "B", "C", "D"]
    assert [c.card for c in found.within("A").claims] == ["B", "C"]


def change(*items: Item) -> MapChange:
    return MapChange(components=items, base="abc1234")


def test_the_roll_up_counts_each_map_and_flags_a_changed_map_below() -> None:
    base, head = moved()
    deep = tree(head.top.model, ("Gateway", "", INSIDE), ("Gateway/Routes", "Gateway", INSIDE))
    found = page_rollup.records(deep, {"Gateway/Routes": change(Item(CHANGED, "X", ("modules",)))})
    assert found[""] == page_rollup.Rollup("", (), 0, True)
    assert found["Gateway"].below and not found["Gateway"].own
    assert found["Gateway/Routes"] == page_rollup.Rollup(
        "Gateway/Routes", ((CHANGED, "component", 1),), 1, False
    )
    assert page_rollup.counted(found["Gateway/Routes"]) == "1 changed component"
    assert page_rollup.href("", "Gateway/Routes") == "Gateway/Routes/index.html"
    assert page_rollup.href("Gateway", "") == "../index.html"
    assert page_rollup.href("Gateway/Routes", "Store") == "../../Store/index.html"


def test_the_change_panel_gives_the_nested_changes_and_the_boundary_rows() -> None:
    base, head = moved()
    rollups = page_rollup.records(head, {"Store": change(Item(CHANGED, "Routes", ("modules",)))})
    found = page_rollup.Changes(rollups, boundary_changes.compute(base, head))
    html = page_rollup.section(head.maps, "", found)
    assert '<h3 class="chg-cap">CHANGES IN NESTED MAPS</h3>' in html
    assert '<a href="Store/index.html#changes">Store</a>' in html
    assert "1 changed component" in html
    assert '<h3 class="chg-cap">BOUNDARY CHANGES</h3>' in html
    assert "<code>app.auth</code> moved from <code>Gateway</code> to <code>Store</code>" in html
    assert "Map <code>Store</code>: 1 change." in html
    assert "Accept or reject each boundary change in the review." in html
    # A map without maps below it has no such sections.
    assert page_rollup.section(head.maps, "Store", found) == ""
    # A base tree that does not load gives the reason, not an empty list.
    unknown = page_rollup.section(head.maps, "", page_rollup.Changes(rollups, None, "no base"))
    assert "Not known, because no base." in unknown


def test_the_pull_request_summary_has_the_boundary_changes_row() -> None:
    base, head = moved()
    s = pr_summary.Summary(
        pr_summary.contract_changes(base, head),
        pr_summary.map_changes(base, head),
        (),
        (),
        "warn",
        0,
        boundary=boundary_changes.compute(base, head),
        nested=True,
    )
    lines = pr_summary.markdown(s).splitlines()
    at = lines.index(
        "- **Boundary changes:** 2 rows. Accept or reject each boundary change in this review."
    )
    assert lines[at + 1].startswith(
        "  - `app.auth` moved from `Gateway` to `Store` in the top map."
    )
    assert lines[at + 2].endswith("Reason: Records the imports at abc1234.")


def test_the_summary_says_no_boundary_change_only_for_a_nested_tree() -> None:
    base, _head = moved()
    values = (
        pr_summary.contract_changes(base, base),
        pr_summary.map_changes(base, base),
        (),
        (),
        "warn",
        1,
    )
    nested = pr_summary.markdown(pr_summary.Summary(*values, nested=True))
    assert "- **Boundary changes:** no change" in nested
    flat = pr_summary.markdown(pr_summary.Summary(*values))
    assert "Boundary changes" not in flat
