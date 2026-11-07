"""The sequences of each map for the canvas page (docs/design/nested-canvas.md, "Views").

`canvas_data` adds the key `sq` to a map that has sequences. A map without sequences
gets no key. Thus the canvas data of a tree without sequences does not change.

`sq` is a list in model order. Each sequence has these keys:

- `id`: the sequence ID. `n`: the label.
- `st`: the recorded start (`Journey.starts`), if any.
- `en`: the short name of the entry point, as the linked page gives it
  (`page_sequences.data`), if any.
- `dr`: 1 if an agent wrote the sequence as a draft.
- `s`: the steps in order. Each step has `f`, the index of its flow in the flows of the
  map, or -1 if the step names no one flow (the rule of `schematic._step_index`). It can
  also have `a` (the acting components), `me` (the measurement components) and `y` (the
  step sentence).

This module adds no facts. It reads the meaning of the map and the entry points of the
facts.
"""

from __future__ import annotations

from typing import Any

from systemap import flow_ids, nest
from systemap.model import Journey, Model, Step
from systemap.page_sequences import short_entry
from systemap.source_facts import entry_identity, entry_label


def entry(journey: Journey, points: list[dict[str, str]]) -> str:
    """Give the short entry point name of a sequence, as the linked page does.

    The recorded start names the entry point, or the first covered command does."""
    if journey.starts:
        for p in points:
            if journey.starts in (p.get("name"), entry_label(p)):
                return short_entry(p)
        return journey.starts
    by_id = {entry_identity(p): p for p in points}
    covered = [by_id[c] for c in journey.covers if c in by_id]
    commands = [p for p in covered if p.get("kind") == "subcommand"] or covered
    return short_entry(commands[0]) if commands else ""


def flow_index(step: Step, model: Model, edge_index: dict[str, int]) -> int:
    """Give the index of the flow of a step, or -1 if the step names no one flow."""
    found = flow_ids.step_flow(step, model.flows)[0]
    return -1 if found is None else edge_index[found.key]


def _step(step: Step, model: Model, edge_index: dict[str, int]) -> dict[str, Any]:
    out: dict[str, Any] = {"f": flow_index(step, model, edge_index)}
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
