"""The state machines of each map for the canvas page (docs/design/views.md).

`canvas_data` adds the key `sm` to a map that has state machines (`Meaning.machines`). A
map without them gets no key. Thus the canvas data of such a tree does not change.

`sm` is a list in model order. Each state machine has these keys:

- `id`, `n` (the label) and `of` (the component).
- `st`: the states. Each has `id`, `c` and `r` (the column and the row, `states.layout`),
  and can have `sym` (the source symbol), `y` (the sentence) and `first` (1 for a first
  state).
- `tr`: the transitions. Each has `a` and `b` (the indexes of its two states), `l` (the
  label), `f` (the index of its flow in the flows of the map, or -1) and `q` (the index of
  its sequence in the sequences of the map, or -1). It can have `c` (the cause) and `src`
  (the source symbol that decides it).
- `fd`: the lines of `states.findings`, if the machine has them.

This module adds no facts. It reads the meaning and the flows of the map.
"""

from __future__ import annotations

from typing import Any

from systemap import nest, states


def _some(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value not in ("", [], None, 0)}


def _machine(machine: states.StateMachine, flows: dict[str, int], seqs: dict[str, int]) -> Any:
    at = states.layout(machine)
    index = {s.id: i for i, s in enumerate(machine.states)}
    return {
        "id": machine.id,
        "n": machine.label,
        "of": machine.of,
        "st": [
            {"id": s.id, "c": at[s.id][0], "r": at[s.id][1]}
            | _some(sym=s.symbol, y=s.say, first=int(s.id in machine.start))
            for s in machine.states
        ],
        "tr": [
            {
                "a": index[t.src],
                "b": index[t.dst],
                "l": t.label,
                "f": flows.get(t.flow, -1),
                "q": seqs.get(t.journey, -1),
            }
            | _some(c=t.cause, src=t.source)
            for t in machine.transitions
        ],
        **_some(fd=states.findings(machine)),
    }


def of_map(m: nest.Map) -> dict[str, Any]:
    """Give `{"sm": [...]}` for a map with state machines, and an empty object for the others."""
    if not m.meaning.machines:
        return {}
    flows = {f.key: i for i, f in enumerate(m.model.flows)}
    seqs = {j.id: i for i, j in enumerate(m.meaning.journeys)}
    return {"sm": [_machine(machine, flows, seqs) for machine in m.meaning.machines]}
