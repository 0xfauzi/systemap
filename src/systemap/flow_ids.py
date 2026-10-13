"""The flow identifier, and the checks that use it.

A flow can have an explicit `id`. Without an id, the identifier of the flow is `SRC->DST`.
Thus each model without ids keeps its identifiers, its digests, and its finding lines.

Two or more flows can connect one ordered pair only if each of these flows has an
explicit id. Relation sentences, layer overrides, and verb overrides use the flow
identifier as the key. The old `(SRC, DST)` key is also correct, but only for a pair
that one flow connects. A sequence step names its flow with `flow="ID"`, or with the
old `edge=(SRC, DST)` for a pair that one flow connects.

This module imports no model class when it runs, because `model` imports this module.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from systemap.model import Edge, Flow, Journey, Meaning, Model, Step

ARROW = "->"
# An explicit id cannot contain ">", so it is never equal to a `SRC->DST` identifier.
ID_FORM = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
NO_EDGE: tuple[str, str] = ("", "")
KEYED = ("relations", "layer_overrides", "verb_overrides")

V = TypeVar("V")


def default_key(src: str, dst: str) -> str:
    """Give the identifier of a flow without an explicit id."""
    return f"{src}{ARROW}{dst}"


def name(flow: Flow) -> str:
    """Give the flow for a line that a person reads: `SRC -> DST`, then `[ID]` if it has an id.

    A flow without an id gives the same text as before flow ids, so its lines do not change.
    """
    ends = f"{flow.src} -> {flow.dst}"
    return f"{ends} [{flow.id}]" if flow.id else ends


def lookup(mapping: Mapping[Any, V], target: Flow | Edge | str) -> V | None:
    """Give the value for a flow from a mapping that uses flow identifiers or pairs as keys.

    For a flow, the flow identifier comes first, then the pair. A pair or an identifier
    selects only its own key.
    """
    key = getattr(target, "key", None)
    if key is None:
        return mapping.get(target)
    if key in mapping:
        return mapping[key]
    return mapping.get(getattr(target, "edge", None))


def counts(flows: Iterable[Flow]) -> dict[Edge, int]:
    """Give the number of flows on each ordered pair."""
    out: dict[Edge, int] = {}
    for f in flows:
        out[f.edge] = out.get(f.edge, 0) + 1
    return out


def pair_problems(flows: tuple[Flow, ...]) -> list[str]:
    """Find incorrect ids, ids that two flows use, pairs with flows that have no id, and
    flows with the same component at the two ends."""
    out = _id_problems(flows) + _loop_problems(flows)
    for (src, dst), n in counts(flows).items():
        group = [f for f in flows if f.edge == (src, dst)]
        if n > 1 and not all(f.id for f in group):
            times = "twice" if n == 2 else f"{n} times"
            artifacts = " and ".join(f"'{f.artifact}'" for f in group)
            out.append(
                f"flow {src} -> {dst} appears {times} ({artifacts}). Give each flow on this "
                "pair its own id. For an artifact that goes back, add a flow in the opposite "
                "direction"
            )
    return out


def _loop_problems(flows: tuple[Flow, ...]) -> list[str]:
    """Find flows with the same component at the two ends. The router cannot make a path
    that shows these flows."""
    return [
        f"flow {f.src} -> {f.dst} has the same component at the two ends. A flow must "
        "connect two different components"
        for f in flows
        if f.src == f.dst
    ]


def _id_problems(flows: tuple[Flow, ...]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for f in (f for f in flows if f.id):
        if not ID_FORM.fullmatch(f.id):
            out.append(
                f"flow {f.src} -> {f.dst} has the id '{f.id}'. An id contains only letters, "
                "digits, '_', '.', and '-'. It starts with a letter, a digit, or '_'"
            )
        if f.id in seen:
            out.append(f"flow id {f.id} identifies two flows. Give each flow its own id")
        seen.add(f.id)
    return out


def key_problems(model: Model, meaning: Meaning) -> list[str]:
    """Find unknown keys, pair keys for a pair with many flows, and two keys for one flow."""
    out: list[str] = []
    keys = {f.key for f in model.flows}
    on_pair = counts(model.flows)
    for label in KEYED:
        mapping: Mapping[Any, Any] = getattr(meaning, label)
        out += [p for key in mapping for p in _key_problem(label, key, keys, on_pair)]
        out += [
            f"{label} gives flow {name(f)} two keys: {f.key} and the pair. Remove one key"
            for f in model.flows
            if f.key in mapping and f.edge in mapping
        ]
    return out


def _key_problem(label: str, key: Any, keys: set[str], on_pair: dict[Edge, int]) -> list[str]:
    if isinstance(key, str):
        return [] if key in keys else [f"{label} has an unknown flow: {key}"]
    n = on_pair.get(key, 0)
    if n == 0:
        return [f"{label} has an unknown flow: {key[0]} -> {key[1]}"]
    if n > 1:
        return [
            f"{label} uses the pair {key[0]} -> {key[1]} as a key, but {n} flows connect "
            "this pair. Use the id of each flow as its key"
        ]
    return []


def step_flow(step: Step, flows: tuple[Flow, ...]) -> tuple[Flow | None, str]:
    """Give the flow of a sequence step, or None and the problem."""
    if step.flow:
        found = next((f for f in flows if f.key == step.flow), None)
        if found is None:
            return None, f"has an unknown flow id: {step.flow}"
        if step.edge not in (NO_EDGE, found.edge):
            return None, (
                f"names flow {step.flow} ({name(found)}) and the different edge "
                f"{step.edge[0]} -> {step.edge[1]}. Remove the edge"
            )
        return found, ""
    on_edge = [f for f in flows if f.edge == step.edge]
    if not on_edge:
        return None, f"has an unknown flow: {step.edge[0]} -> {step.edge[1]}"
    if len(on_edge) > 1:
        ids = ", ".join(f.key for f in on_edge)
        return None, (
            f"names the pair {step.edge[0]} -> {step.edge[1]}, which has {len(on_edge)} "
            f"flows ({ids}). Name one flow with flow=ID"
        )
    return on_edge[0], ""


def resolve(model: Model, meaning: Meaning) -> Meaning:
    """Give the meaning with the edge of each step that names its flow by id only.

    Code that reads `Step.edge` then gets the two endpoints of the flow. A step with an
    unknown id keeps its empty edge, and the meaning check gives the problem.
    """
    journeys = tuple(_resolved(journey, model.flows) for journey in meaning.journeys)
    if journeys == meaning.journeys:
        return meaning
    return dataclasses.replace(meaning, journeys=journeys)


def _resolved(journey: Journey, flows: tuple[Flow, ...]) -> Journey:
    steps = []
    for step in journey.steps:
        found = next((f for f in flows if f.key == step.flow), None) if step.flow else None
        if found is not None and step.edge == NO_EDGE:
            step = dataclasses.replace(step, edge=found.edge)
        steps.append(step)
    return dataclasses.replace(journey, steps=tuple(steps))


def journey_record(journey: Journey) -> dict[str, Any]:
    """Give the fields of a sequence for a claim digest.

    A step without `flow` and `source_refs` gives the same fields as before these fields.
    A step with `flow` gives no edge, because `resolve` can fill it. Thus a digest is the
    same before and after `resolve`.
    """
    record = dataclasses.asdict(journey)
    for step in record["steps"]:
        if step["flow"]:
            del step["edge"]
        else:
            del step["flow"]
        if not step["source_refs"]:
            del step["source_refs"]
    return record


def find(flows: tuple[Flow, ...], text: str) -> tuple[Flow | None, str]:
    """Find one flow from an id or from `SRC->DST`. Give None and the problem if not one."""
    src, arrow, dst = text.partition(ARROW)
    if arrow:
        edge = (src.strip(), dst.strip())
        found = [f for f in flows if f.edge == edge]
        what = f"{edge[0]}{ARROW}{edge[1]}"
    else:
        found = [f for f in flows if f.id and f.id == text.strip()]
        what = text.strip()
    if not found:
        return None, f"the map has no flow {what}."
    if len(found) > 1:
        ids = ", ".join(f.key for f in found)
        return None, f"{len(found)} flows connect {what}: {ids}. Give the id of one flow."
    return found[0], ""
