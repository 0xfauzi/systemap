"""The sequences of each map for the canvas page (docs/design/nested-canvas.md, "Views").

`canvas_data` adds the key `sq` to a map that has sequences. A map without sequences
gets no key. Thus the canvas data of a tree without sequences does not change.

`sq` is a list in model order. Each sequence has these keys:

- `id`: the sequence ID. `n`: the label.
- `st`: the recorded start (`Journey.starts`), if any.
- `en`: the short name of the entry point, as the linked page gives it
  (`page_sequences.entry`), if any.
- `dr`: 1 if an agent wrote the sequence as a draft.
- `s`: the steps in order. Each step has `f`, the index of its flow in the flows of the
  map, or -1 if the step names no one flow (`flow_ids.step_index`, the rule of the linked
  page). It can also have `a` (the acting components), `me` (the measurement components)
  and `y` (the step sentence).

This module adds no facts. It reads the meaning of the map and the entry points of the
facts.
"""

from __future__ import annotations

from typing import Any

from systemap import flow_ids, nest
from systemap.model import Model, Step
from systemap.page_sequences import entry


def _step(step: Step, model: Model, edge_index: dict[str, int]) -> dict[str, Any]:
    out: dict[str, Any] = {"f": flow_ids.step_index(step, model, edge_index)}
    if step.acts:
        out["a"] = list(step.acts)
    if step.measures:
        out["me"] = list(step.measures)
    if step.say:
        out["y"] = step.say
    return out


def of_map(m: nest.Map, facts: dict[str, Any]) -> dict[str, Any]:
    """Give `{"sq": [...]}` for a map with sequences, and an empty object for the others."""
    if not m.meaning.journeys:
        return {}
    points: list[dict[str, str]] = facts.get("entry_points") or []
    edge_index = {f.key: i for i, f in enumerate(m.model.flows)}
    out = []
    for j in m.meaning.journeys:
        one: dict[str, Any] = {"id": j.id, "n": j.label}
        if j.starts:
            one["st"] = j.starts
        name = entry(j, points)
        if name:
            one["en"] = name
        if j.drafted:
            one["dr"] = 1
        one["s"] = [_step(s, m.model, edge_index) for s in j.steps]
        out.append(one)
    return {"sq": out}
