"""Compare the model at the comparison base with the model of the page.

The Changes view shows what a change did to the map: the components, flows, sequences,
and invariants that the change added, removed, or changed in the model. The source
comparison of the page cannot show these items, because it uses the model of the page
for both revisions.

The model at the comparison base comes from the committed files. The model of the page
is the model on disk. The comparison uses no source facts, so a changed evidence state
is not an item here. The Changes view gives the flows to examine for that.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from systemap import delta_git, nest
from systemap.config import Config
from systemap.model import Component, Flow, Invariant, Journey, Meaning, Model

ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"

# The reader words for the changed fields of each item. The keys are schema keys.
COMPONENT_FIELDS = {
    "does": "description",
    "plain": "card text",
    "interface": "interface",
    "implemented_by": "modules",
    "entry": "entry point",
    "kind": "kind",
    "region": "region",
    "container": "container",
    "note": "note",
    "calls_model": "model calls",
    "map": "inner map",
}
FLOW_FIELDS = {
    "artifact": "artifact",
    "kind": "kind",
    "source_refs": "source records",
    "relation": "sentence",
}
SEQUENCE_FIELDS = {"label": "name", "starts": "entry point", "steps": "steps"}
INVARIANT_FIELDS = {"text": "text", "governs": "components"}
EMPTY = Model(canvas=(0, 0), containers=(), regions=(), components=(), flows=(), flow_kinds=())
NO_MEANING = Meaning(plain={})


@dataclass(frozen=True)
class Item:
    """One map item that the change added, removed, or changed.

    `name` is the component ID, the flow artifact, the sequence label, or the invariant
    number. `fields` gives the reader words for the changed parts of a changed item.
    `ends` gives the two components of a flow. `go` is the index of the flow or the
    sequence in the model of the page, or -1 for a removed item. `text` is the text of
    an invariant.
    """

    how: str
    name: str
    fields: tuple[str, ...] = ()
    ends: tuple[str, str] = ("", "")
    go: int = -1
    text: str = ""


@dataclass(frozen=True)
class MapChange:
    """The map changes between the model at `base` and the model of the page.

    `error` gives the reason that the comparison has no model at the base revision.
    """

    components: tuple[Item, ...] = ()
    flows: tuple[Item, ...] = ()
    sequences: tuple[Item, ...] = ()
    invariants: tuple[Item, ...] = ()
    base: str = ""
    error: str = ""

    @property
    def count(self) -> int:
        return len(self.components) + len(self.flows) + len(self.sequences) + len(self.invariants)


def _differ(a: object, b: object, names: Mapping[str, str]) -> list[str]:
    return [
        word for name, word in names.items() if getattr(a, name, None) != getattr(b, name, None)
    ]


def _components(base: Model, bm: Meaning, head: Model, hm: Meaning) -> tuple[Item, ...]:
    """Give the added and changed components in model order, then the removed ones."""
    before = {c.id: c for c in base.components}
    out = [_component(before.get(c.id), c, bm, hm) for c in head.components]
    after = {c.id for c in head.components}
    out += [Item(REMOVED, c.id) for c in base.components if c.id not in after]
    return tuple(item for item in out if item.how)


def _component(old: Component | None, c: Component, bm: Meaning, hm: Meaning) -> Item:
    """Give the change of one component. An empty `how` means no change."""
    if old is None:
        return Item(ADDED, c.id)
    plain = bm.plain.get(old.id, "") != hm.plain.get(c.id, "")
    words = tuple(
        word
        for name, word in COMPONENT_FIELDS.items()
        if (plain if name == "plain" else getattr(old, name) != getattr(c, name))
    )
    return Item(CHANGED if words else "", c.id, words)


def _cited(f: Flow) -> set[str]:
    """Give the modules and symbols that the source records cite, without their digests.

    A new digest for the same module or symbol is a renewed source review, not a change.
    """
    return {ref.rpartition("@")[0] or ref for ref in f.source_refs}


def _flow_fields(old: Flow, f: Flow, bm: Meaning, hm: Meaning) -> tuple[str, ...]:
    words = _differ(old, f, {"artifact": "artifact", "kind": "kind"})
    if _cited(old) != _cited(f):
        words.append(FLOW_FIELDS["source_refs"])
    if bm.relation(old) != hm.relation(f):
        words.append(FLOW_FIELDS["relation"])
    return tuple(words)


def _flows(base: Model, bm: Meaning, head: Model, hm: Meaning) -> tuple[Item, ...]:
    """Give the added and changed flows in model order, then the removed ones."""
    before = {f.key: f for f in base.flows}
    out: list[Item] = []
    for i, f in enumerate(head.flows):
        old = before.get(f.key)
        words = () if old is None else _flow_fields(old, f, bm, hm)
        if old is None or words:
            out.append(Item(ADDED if old is None else CHANGED, f.artifact, words, f.edge, i))
    after = {f.key for f in head.flows}
    out += [Item(REMOVED, f.artifact, ends=f.edge) for f in base.flows if f.key not in after]
    return tuple(out)


def _sequences(bm: Meaning, hm: Meaning) -> tuple[Item, ...]:
    """Give the added and changed sequences in page order, then the removed ones."""
    before: dict[str, Journey] = {j.id: j for j in bm.journeys}
    out: list[Item] = []
    for k, j in enumerate(hm.journeys):
        old = before.get(j.id)
        words = () if old is None else tuple(_differ(old, j, SEQUENCE_FIELDS))
        if old is None or words:
            out.append(Item(ADDED if old is None else CHANGED, j.label, words, go=k))
    after = {j.id for j in hm.journeys}
    out += [Item(REMOVED, j.label) for j in bm.journeys if j.id not in after]
    return tuple(out)


def _governs(i: Invariant) -> Invariant:
    """Give the invariant with its components in name order, for the comparison."""
    return Invariant(i.n, i.text, tuple(sorted(i.governs)))


def _invariants(base: Model, head: Model) -> tuple[Item, ...]:
    """Give the added, changed, and removed invariants in number order."""
    before = {i.n: _governs(i) for i in base.invariants}
    after = {i.n: _governs(i) for i in head.invariants}
    out: list[Item] = []
    for n in sorted(before.keys() | after.keys()):
        old, new = before.get(n), after.get(n)
        if new is None:
            assert old is not None
            out.append(Item(REMOVED, str(n), text=old.text))
        elif old is None:
            out.append(Item(ADDED, str(n), text=new.text))
        elif words := tuple(_differ(old, new, INVARIANT_FIELDS)):
            out.append(Item(CHANGED, str(n), words, text=new.text))
    return tuple(out)


def compare(base: tuple[Model, Meaning], head: tuple[Model, Meaning], at: str = "") -> MapChange:
    """Compare two models of one map. `at` names the base revision."""
    (bm, bmeaning), (hm, hmeaning) = base, head
    return MapChange(
        components=_components(bm, bmeaning, hm, hmeaning),
        flows=_flows(bm, bmeaning, hm, hmeaning),
        sequences=_sequences(bmeaning, hmeaning),
        invariants=_invariants(bm, hm),
        base=at,
    )


# One load of the committed models for each revision, for all the maps of one render.
_TREES: dict[tuple[str, str, str], nest.Tree | str] = {}


def _tree_at(cfg: Config, revision: str) -> nest.Tree | str:
    key = (str(cfg.root), cfg.model, revision)
    if key not in _TREES:
        _TREES[key] = delta_git.model_at(cfg, revision)
    return _TREES[key]


def for_page(cfg: Config, map_id: str, model: Model, meaning: Meaning, revision: str) -> MapChange:
    """Compare the committed model of one map at `revision` with the model of its page.

    A map that is not in the base tree is compared with an empty map. If the base tree
    does not load, the result gives the reason and no items.
    """
    if not revision:
        return MapChange(error="the page has no base revision")
    tree = _tree_at(cfg, revision)
    if isinstance(tree, str):
        return MapChange(base=revision, error=tree)
    found: Iterable[nest.Map] = (m for m in tree.maps if m.id == map_id)
    old = next(((m.model, m.meaning) for m in found), (EMPTY, NO_MEANING))
    return compare(old, (model, meaning), revision)
