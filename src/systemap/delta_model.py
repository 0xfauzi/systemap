"""Compare the map at the base commit with the map on disk for the pull request comment.

The comparison gives the components, flows, sequences, and invariants that the change
added, removed, or changed. It also gives the components with changed source code, and
the sequences and invariants that refer to a changed component or flow.

The comparison gives no decision. The delta lines and the exit code do not use it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from systemap import evidence, nest
from systemap.model import Component, Edge, Flow, Invariant, Journey, Meaning, Model

ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"
# A component whose claims did not change, but whose modules have changed source.
SOURCE = "changed source"

# The component fields that make a claim. Positions and review digests are not claims.
COMPONENT_FIELDS = (
    "does",
    "interface",
    "implemented_by",
    "entry",
    "kind",
    "region",
    "container",
    "note",
    "calls_model",
    "map",
)
FLOW_FIELDS = ("artifact", "kind")
EMPTY = Model(canvas=(0, 0), containers=(), regions=(), components=(), flows=(), flow_kinds=())
NO_MEANING = Meaning(plain={})


@dataclass(frozen=True)
class Item:
    """One map item that the change added, removed, or changed.

    `name` identifies the item for the reader. `detail` gives the changed fields, the
    evidence change, or the changed steps.
    """

    how: str
    name: str
    detail: tuple[str, ...] = ()


@dataclass(frozen=True)
class Drawn:
    """One flow for the picture of the change, with its component names."""

    src: str
    dst: str
    artifact: str
    how: str


@dataclass(frozen=True)
class MapChange:
    """The map changes between the base commit and the model on disk.

    `marks` gives the change of each component in the picture. `error` gives the reason
    that the comparison has no model at the base commit.
    """

    components: tuple[Item, ...] = ()
    flows: tuple[Item, ...] = ()
    sequences: tuple[Item, ...] = ()
    invariants: tuple[Item, ...] = ()
    sequence_count: int = 0
    invariant_count: int = 0
    drawn: tuple[Drawn, ...] = ()
    marks: Mapping[str, str] = field(default_factory=dict)
    error: str = ""

    @property
    def model_changed(self) -> bool:
        """True when a component, flow, sequence, or invariant changed in the model."""
        items = (*self.components, *self.flows, *self.sequences, *self.invariants)
        return any(item.how in (ADDED, REMOVED, CHANGED) for item in items)


# ---- one map ------------------------------------------------------------------------


@dataclass
class _Found:
    """The items of one map, collected in the comparison order."""

    components: list[Item] = field(default_factory=list)
    flows: list[Item] = field(default_factory=list)
    sequences: list[Item] = field(default_factory=list)
    invariants: list[Item] = field(default_factory=list)
    drawn: list[Drawn] = field(default_factory=list)
    marks: dict[str, str] = field(default_factory=dict)
    sequence_count: int = 0
    invariant_count: int = 0


@dataclass(frozen=True)
class _Side:
    """One map at one commit: the model, its meaning, and the source facts."""

    model: Model
    meaning: Meaning
    facts: dict[str, Any]


def _differ(a: object, b: object, names: Iterable[str]) -> tuple[str, ...]:
    return tuple(name for name in names if getattr(a, name) != getattr(b, name))


def _component_fields(b: Component, h: Component, base: _Side, head: _Side) -> tuple[str, ...]:
    """Give the claim fields that differ, with `plain` from the meaning."""
    found = _differ(b, h, COMPONENT_FIELDS)
    if base.meaning.plain.get(b.id, "") != head.meaning.plain.get(h.id, ""):
        found += ("plain",)
    return found


def _source_changed(base: _Side, head: _Side) -> set[str]:
    """Give the components with changed, added, or removed modules.

    The rule is the source review rule: a module changes when its syntax digest
    changes. Comments and formatting do not change it.
    """
    b: dict[str, Any] = base.facts.get("components", {})
    h: dict[str, Any] = head.facts.get("components", {})

    def digest(record: Mapping[str, Any]) -> object:
        return record.get("syntax_sha", record.get("sha"))

    changed = {m for m in set(b) & set(h) if digest(b[m]) != digest(h[m])}
    at_head = evidence.owners(head.model, head.facts)
    at_base = evidence.owners(base.model, base.facts)
    out = {at_head[m] for m in changed | (set(h) - set(b)) if m in at_head}
    out |= {at_base[m] for m in set(b) - set(h) if m in at_base}
    return out & head.model.ids


def _components(base: _Side, head: _Side, name: _Names, found: _Found) -> set[str]:
    """Collect added, removed, and changed components. Give the changed component ids."""
    before = {c.id: c for c in base.model.components}
    after = {c.id: c for c in head.model.components}
    source = _source_changed(base, head)
    items = [_component(before.get(c.id), c, base, head, source) for c in head.model.components]
    items += [Item(REMOVED, c.id) for c in base.model.components if c.id not in after]
    for item in items:
        if item.how:
            found.components.append(Item(item.how, name.card(item.name), item.detail))
            found.marks[name.card(item.name)] = item.how
    return {item.name for item in items if item.how and item.how != REMOVED}


def _component(
    old: Component | None, c: Component, base: _Side, head: _Side, source: set[str]
) -> Item:
    """Give the change of one component. An empty `how` means no change."""
    if old is None:
        return Item(ADDED, c.id)
    fields = _component_fields(old, c, base, head)
    if fields:
        return Item(CHANGED, c.id, fields)
    return Item(SOURCE if c.id in source else "", c.id)


def _cited(f: Flow) -> set[str]:
    """Give the modules and symbols that the source records cite, without their digests.

    A new digest for the same module or symbol is a renewed source review, not a change.
    """
    return {ref.rpartition("@")[0] or ref for ref in f.source_refs}


def _flow_fields(b: Flow, h: Flow, base: _Side, head: _Side, states: _States) -> tuple[str, ...]:
    """Give the flow fields that differ, the relation sentence, and the evidence change."""
    found = _differ(b, h, FLOW_FIELDS)
    if _cited(b) != _cited(h):
        found += ("source_refs",)
    if base.meaning.relations.get(b.edge, "") != head.meaning.relations.get(h.edge, ""):
        found += ("relation",)
    was, now = states.base[b.edge].state, states.head[h.edge].state
    if was != now:
        found += (f"evidence {was} to {now}",)
    return found


@dataclass(frozen=True)
class _States:
    base: Mapping[Edge, evidence.Evidence]
    head: Mapping[Edge, evidence.Evidence]


def _flows(
    base: _Side, head: _Side, observed_by: tuple[str, ...], name: _Names, found: _Found
) -> set[Edge]:
    """Collect added, removed, and changed flows. Give the changed edges."""
    states = _States(
        evidence.of_model(base.model, base.meaning, base.facts, observed_by),
        evidence.of_model(head.model, head.meaning, head.facts, observed_by),
    )
    before = {f.edge: f for f in base.model.flows}
    after = {f.edge: f for f in head.model.flows}
    touched: set[Edge] = set()
    for f in head.model.flows:
        old = before.get(f.edge)
        fields = () if old is None else _flow_fields(old, f, base, head, states)
        if old is None or fields:
            how = ADDED if old is None else CHANGED
            found.flows.append(Item(how, name.flow(f), fields))
            found.drawn.append(Drawn(name.card(f.src), name.card(f.dst), f.artifact, how))
            touched.add(f.edge)
    for f in base.model.flows:
        if f.edge not in after:
            found.flows.append(Item(REMOVED, name.flow(f)))
            found.drawn.append(Drawn(name.card(f.src), name.card(f.dst), f.artifact, REMOVED))
    return touched


def _journey_key(j: Journey) -> tuple[object, ...]:
    return (j.label, j.starts, j.steps)


def _steps(j: Journey, cards: set[str], edges: set[Edge]) -> list[int]:
    """Give the step numbers whose flow changed or has an end at a changed component."""
    return [n for n, step in enumerate(j.steps, 1) if step.edge in edges or set(step.edge) & cards]


def _sequence(old: Journey | None, j: Journey, cards: set[str], edges: set[Edge]) -> Item | None:
    """Give the change of one sequence, or None if it has no changed step."""
    if old is None or _journey_key(old) != _journey_key(j):
        return Item(ADDED if old is None else CHANGED, j.label)
    steps = _steps(j, cards, edges)
    if not steps:
        return None
    word = "step" if len(j.steps) == 1 else "steps"
    return Item("", j.label, (f"{len(steps)} of {len(j.steps)} {word}",))


def _sequences(
    base: _Side, head: _Side, cards: set[str], edges: set[Edge], name: _Names, found: _Found
) -> None:
    """Collect added, removed, and changed sequences, and the sequences with changed steps."""
    before = {j.id: j for j in base.meaning.journeys}
    after = {j.id for j in head.meaning.journeys}
    found.sequence_count += len(head.meaning.journeys)
    for j in head.meaning.journeys:
        item = _sequence(before.get(j.id), j, cards, edges)
        if item is not None:
            found.sequences.append(Item(item.how, name.text(item.name), item.detail))
    found.sequences += [
        Item(REMOVED, name.text(j.label)) for j in base.meaning.journeys if j.id not in after
    ]


def _invariant_key(i: Invariant) -> tuple[object, ...]:
    return (i.text, tuple(sorted(i.governs)))


def _invariants(base: _Side, head: _Side, cards: set[str], name: _Names, found: _Found) -> None:
    """Collect added, removed, and changed invariants, and those of changed components."""
    before = {i.n: i for i in base.model.invariants}
    after = {i.n for i in head.model.invariants}
    found.invariant_count += len(head.model.invariants)
    for i in sorted(head.model.invariants, key=lambda i: i.n):
        old = before.get(i.n)
        if old is None or _invariant_key(old) != _invariant_key(i):
            how = ADDED if old is None else CHANGED
            found.invariants.append(Item(how, name.text(str(i.n)), (i.text,)))
        elif set(i.governs) & cards:
            found.invariants.append(Item("", name.text(str(i.n)), (i.text,)))
    found.invariants += [
        Item(REMOVED, name.text(str(i.n)), (i.text,))
        for i in sorted(base.model.invariants, key=lambda i: i.n)
        if i.n not in after
    ]


@dataclass(frozen=True)
class _Names:
    """Names for the items of one map. A nested map adds its id."""

    map_id: str

    def card(self, cid: str) -> str:
        return f"{self.map_id}/{cid}" if self.map_id else cid

    def text(self, text: str) -> str:
        return f"{self.map_id}: {text}" if self.map_id else text

    def flow(self, f: Flow) -> str:
        return self.text(f"{f.src} -> {f.dst} ({f.artifact})")


def _one_map(
    base: _Side, head: _Side, observed_by: tuple[str, ...], map_id: str, found: _Found
) -> None:
    name = _Names(map_id)
    cards = _components(base, head, name, found)
    edges = _flows(base, head, observed_by, name, found)
    _sequences(base, head, cards, edges, name, found)
    _invariants(base, head, cards, name, found)


# ---- the map tree -------------------------------------------------------------------


def _sides(
    base: nest.Tree | None, head: nest.Tree
) -> list[tuple[str, tuple[Model, Meaning], tuple[Model, Meaning]]]:
    """Pair the maps by id. A map at one commit only is compared with an empty map."""
    before = {m.id: (m.model, m.meaning) for m in (base.maps if base else ())}
    after = {m.id: (m.model, m.meaning) for m in head.maps}
    if base is None:
        # Without the base model, only source changes count: use the model on disk.
        before = dict(after)
    ids = [m.id for m in head.maps] + [i for i in before if i not in after]
    empty = (EMPTY, NO_MEANING)
    return [(i, before.get(i, empty), after.get(i, empty)) for i in ids]


def compare(
    base_tree: nest.Tree | str,
    head_tree: nest.Tree,
    base_facts: dict[str, Any],
    head_facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> MapChange:
    """Compare the maps. A string for `base_tree` is the reason that it is not available.

    Without the base model, the comparison uses the model on disk for both commits. Then
    it gives only the components with changed source, the flows with a changed evidence
    state, and the sequences and invariants of these components.
    """
    base = base_tree if isinstance(base_tree, nest.Tree) else None
    found = _Found()
    mechanisms = tuple(observed_by)
    for map_id, (bm, bmeaning), (hm, hmeaning) in _sides(base, head_tree):
        _one_map(
            _Side(bm, bmeaning, base_facts),
            _Side(hm, hmeaning, head_facts),
            mechanisms,
            map_id,
            found,
        )
    return MapChange(
        components=tuple(found.components),
        flows=tuple(found.flows),
        sequences=tuple(found.sequences),
        invariants=tuple(found.invariants),
        sequence_count=found.sequence_count,
        invariant_count=found.invariant_count,
        drawn=tuple(found.drawn),
        marks=found.marks,
        error="" if base else str(base_tree),
    )
