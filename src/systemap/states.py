"""State machines of a map: the states of one item, and the cause of each transition.

This is a prototype of a new view (docs/design/views.md). A state machine belongs to one
component of the map. An agent or a person writes it in the model, as a flow or a sequence.
Source facts do not give the states of an item: a probe of this repository found no
syntax pattern that identifies them. Thus the model gives each state with the source symbol
that defines it, and the check compares that symbol with the facts.

- `State`: an identifier, the source symbol (`module.NAME`, a constant in the facts), and a
  sentence.
- `Transition`: the two states, a short label, the cause in a sentence, and the items of
  the map that show the same change: a flow (its identifier, `Flow.key`) and a sequence
  (its identifier). The two are optional. `source` names the source symbol that decides
  the transition.
- `StateMachine`: an identifier, a label, the component (`of`), the states, the
  transitions, and the first states (`start`).

`problems` finds references that the model does not have. `symbol_problems` finds a state
symbol that the facts do not have. `findings` gives a state with no transition in or no
transition out. These lines are not judgement findings yet: they have no finding kind, no
explanation and no recorded answers. `layout` gives each state a position in columns.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class State:
    """One state of an item, with the source symbol that defines it."""

    id: str
    symbol: str = ""
    say: str = ""


@dataclass(frozen=True)
class Transition:
    """A change from the state `src` to the state `dst`, with its cause.

    flow is the identifier of the flow of the map that causes the transition, if one does.
    journey is the identifier of a sequence that shows it. source names the source symbol
    that decides the new state."""

    src: str
    dst: str
    label: str
    cause: str = ""
    flow: str = ""
    journey: str = ""
    source: str = ""


@dataclass(frozen=True)
class StateMachine:
    """The states and the transitions of one item that a component of the map holds."""

    id: str
    label: str
    of: str
    states: tuple[State, ...]
    transitions: tuple[Transition, ...] = ()
    start: tuple[str, ...] = ()


def _refs(machine: StateMachine, flows: set[str], journeys: set[str]) -> list[str]:
    out = []
    ids = {s.id for s in machine.states}
    where = f"state machine {machine.id}"
    for name in machine.start:
        if name not in ids:
            out.append(f"{where} has an unknown first state: {name}")
    for t in machine.transitions:
        for end in (t.src, t.dst):
            if end not in ids:
                out.append(f"{where} has a transition with an unknown state: {end}")
        if t.flow and t.flow not in flows:
            out.append(f"{where}, transition {t.src} to {t.dst}, has an unknown flow: {t.flow}")
        if t.journey and t.journey not in journeys:
            out.append(
                f"{where}, transition {t.src} to {t.dst}, has an unknown sequence: {t.journey}"
            )
    return out


def problems(
    machines: Iterable[StateMachine],
    components: set[str],
    flows: set[str],
    journeys: set[str],
) -> list[str]:
    """Find the references of the state machines that the model does not have."""
    out: list[str] = []
    seen: set[str] = set()
    for machine in machines:
        if machine.id in seen:
            out.append(f"state machine {machine.id} is in the model two times")
        seen.add(machine.id)
        if machine.of not in components:
            out.append(f"state machine {machine.id} has an unknown component: {machine.of}")
        if not machine.states:
            out.append(f"state machine {machine.id} has no states")
        names = [s.id for s in machine.states]
        for name in sorted({n for n in names if names.count(n) > 1}):
            out.append(f"state machine {machine.id} has the state {name} two times")
        out += _refs(machine, flows, journeys)
    return out


def _known(symbol: str, modules: Mapping[str, Any]) -> bool:
    module, _dot, name = symbol.rpartition(".")
    record = modules.get(module) or {}
    return any(c.get("name") == name for c in record.get("constants") or [])


def symbol_problems(machines: Iterable[StateMachine], facts: Mapping[str, Any]) -> list[str]:
    """Find each state symbol that is not a constant of a module in the facts."""
    modules = facts.get("components") or {}
    return [
        f"state machine {machine.id}: the facts have no constant {state.symbol} "
        f"for the state {state.id}"
        for machine in machines
        for state in machine.states
        if state.symbol and not _known(state.symbol, modules)
    ]


def findings(machine: StateMachine) -> list[str]:
    """Give the states with no transition in, except the first states, and with no
    transition out."""
    out = []
    for state in machine.states:
        if state.id not in machine.start and not any(
            t.dst == state.id for t in machine.transitions
        ):
            out.append(f'The state "{state.id}" has no transition in.')
        if not any(t.src == state.id for t in machine.transitions):
            out.append(f'The state "{state.id}" has no transition out.')
    return out


def layout(machine: StateMachine) -> dict[str, tuple[int, int]]:
    """Give the column and the row of each state.

    The column is the smallest count of transitions from a first state. A state with a
    transition back to the state that reaches it stays in the column of that state, in a
    new row. Thus two states that change into each other are one above the other. A state
    that no first state reaches goes in the column after the last one. The rows are in
    model order.
    """
    depth: dict[str, int] = {name: 0 for name in machine.start}
    if not depth and machine.states:
        depth[machine.states[0].id] = 0
    frontier = list(depth)
    pairs = {(t.src, t.dst) for t in machine.transitions}
    while frontier:
        name = frontier.pop(0)
        for t in machine.transitions:
            if t.src == name and t.dst not in depth:
                back = name not in machine.start and (t.dst, name) in pairs
                depth[t.dst] = depth[name] + (0 if back else 1)
                frontier.append(t.dst)
    last = max(depth.values(), default=0) + 1
    rows: dict[int, int] = {}
    out = {}
    for state in machine.states:
        column = depth.get(state.id, last)
        out[state.id] = (column, rows.get(column, 0))
        rows[column] = rows.get(column, 0) + 1
    return out
