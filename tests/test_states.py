"""State machines in the model (`states`), in the check, and in the canvas data
(`canvas_states`). No browser.

Acceptance values, written before the first run on 2026-11-15:

1. `states.problems` gives one line for each of: a state machine two times, an unknown
   component, no states, a state two times, an unknown first state, a transition with an
   unknown state, an unknown flow, and an unknown sequence. A correct machine gives no line.
2. `states.symbol_problems` gives a line for a state symbol that is not a constant of its
   module in the facts, and no line for a constant of the facts.
3. `states.findings` gives a state with no transition in, except a first state, and a
   state with no transition out.
4. `states.layout`: a first state is in column 0. A state with a transition back to the
   state that reaches it is in the column of that state, in the next row. A state that no
   first state reaches is in the column after the last one.
5. The map of this repository has two state machines. The model reader reads them without
   running code, the model has no problem, and each state symbol is in the committed facts.
   The machine "flow-review" has one finding, for the state "earlier". The canvas data has
   the key `sm` with the two machines, and each transition has the index of its flow.
6. A map without state machines has no `sm` key, and its page hides no part: the header
   has the States button, and the script hides it (`VIEWS.states` is not registered).
"""

from __future__ import annotations

from pathlib import Path

from test_canvas_page import _loaded, _made

from systemap import canvas_data, canvas_page, config, facts_file, nest, page_canvas, states
from systemap.model import meaning_problems
from systemap.states import State, StateMachine, Transition

REPO = Path(__file__).resolve().parent.parent

GOOD = StateMachine(
    id="door",
    label="Door",
    of="A",
    start=("shut",),
    states=(State("shut", "pkg.door.SHUT"), State("open", "pkg.door.OPEN")),
    transitions=(
        Transition("shut", "open", "push", flow="A->B", journey="walk"),
        Transition("open", "shut", "pull"),
    ),
)


def _problems(*machines: StateMachine) -> list[str]:
    return states.problems(machines, {"A", "B"}, {"A->B"}, {"walk"})


def test_problems_finds_each_unknown_reference() -> None:
    """Acceptance 1."""
    assert _problems(GOOD) == []
    assert _problems(GOOD, GOOD) == ["state machine door is in the model two times"]
    bad = StateMachine(
        id="bad",
        label="Bad",
        of="Z",
        start=("gone",),
        states=(State("a"), State("a")),
        transitions=(Transition("a", "b", "go", flow="A->Z", journey="run"),),
    )
    assert _problems(bad) == [
        "state machine bad has an unknown component: Z",
        "state machine bad has the state a two times",
        "state machine bad has an unknown first state: gone",
        "state machine bad has a transition with an unknown state: b",
        "state machine bad, transition a to b, has an unknown flow: A->Z",
        "state machine bad, transition a to b, has an unknown sequence: run",
    ]
    empty = StateMachine(id="none", label="None", of="A", states=())
    assert _problems(empty) == ["state machine none has no states"]


def test_symbol_problems_compares_the_symbols_with_the_facts() -> None:
    """Acceptance 2."""
    facts = {"components": {"pkg.door": {"constants": [{"name": "SHUT", "value": '"shut"'}]}}}
    assert states.symbol_problems([GOOD], facts) == [
        "state machine door: the facts have no constant pkg.door.OPEN for the state open"
    ]
    facts["components"]["pkg.door"]["constants"].append({"name": "OPEN", "value": '"open"'})
    assert states.symbol_problems([GOOD], facts) == []


def test_findings_gives_a_state_with_no_way_in_or_out() -> None:
    """Acceptance 3."""
    assert states.findings(GOOD) == []
    odd = StateMachine(
        id="odd",
        label="Odd",
        of="A",
        start=("a",),
        states=(State("a"), State("b"), State("c")),
        transitions=(Transition("a", "b", "go"),),
    )
    assert states.findings(odd) == [
        'The state "b" has no transition out.',
        'The state "c" has no transition in.',
        'The state "c" has no transition out.',
    ]


def _own() -> tuple[config.Config, nest.Tree, dict[str, object]]:
    cfg = config.load(REPO)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


def test_layout_puts_two_states_that_change_into_each_other_in_one_column() -> None:
    """Acceptance 4."""
    assert states.layout(GOOD) == {"shut": (0, 0), "open": (1, 0)}
    _cfg, tree, _facts = _own()
    by_id = {m.id: m for m in tree.top.meaning.machines}
    assert states.layout(by_id["source-review"]) == {
        "missing": (0, 0),
        "current": (1, 0),
        "stale": (1, 1),
    }
    assert states.layout(by_id["flow-review"]) == {
        "missing": (0, 0),
        "current": (1, 0),
        "stale": (1, 1),
        "earlier": (2, 0),
    }


def test_the_map_of_this_repository_has_two_state_machines() -> None:
    """Acceptance 5."""
    cfg, tree, facts = _own()
    top = tree.top
    machines = top.meaning.machines
    assert [m.id for m in machines] == ["source-review", "flow-review"]
    assert meaning_problems(top.model, top.meaning) == []
    assert states.symbol_problems(machines, facts) == []
    assert states.findings(machines[0]) == []
    assert states.findings(machines[1]) == ['The state "earlier" has no transition in.']
    data = canvas_data.build(cfg, tree, facts)
    found = data["maps"][0]["sm"]
    assert [m["id"] for m in found] == ["source-review", "flow-review"]
    flows = data["maps"][0]["flows"]
    for machine in found:
        assert machine["of"] == "Model"
        for t in machine["tr"]:
            assert 0 <= t["f"] < len(flows)
            assert flows[t["f"]]["s"] == "Agent"
    assert found[1]["fd"] == ['The state "earlier" has no transition in.']
    assert "fd" not in found[0]
    assert found[0]["st"][0] == {
        "id": "missing",
        "c": 0,
        "r": 0,
        "sym": "systemap.card_review.MISSING",
        "y": "The component has no source_review value.",
        "first": 1,
    }


def test_a_map_without_state_machines_has_no_key(tmp_path: Path) -> None:
    """Acceptance 6."""
    cfg, tree, facts = _loaded(_made(tmp_path, ""))
    data = canvas_data.build(cfg, tree, facts)
    assert all("sm" not in m for m in data["maps"])
    built = canvas_page.build(canvas_page.tree_theme(cfg, tree), data)
    assert 'data-view="states"' in built
    assert "if (ST_MAPS.length && ST_BAR) {" in page_canvas.SCRIPT
