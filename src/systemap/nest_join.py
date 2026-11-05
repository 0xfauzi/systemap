"""The boundary checks between a component that opens a map and its nested map.

`check_nesting` compares only the actors and the module claims of a nested map. A flow
to an actor has the evidence state `external`, so the import evidence does not examine
it. Thus this module gives two judgement kinds for the boundary of each nested map:

- `boundary flow`: a nested flow between an internal component and the actor X needs a
  parent flow between the opening card and X, in the same direction. A parent flow
  between the opening card and X needs at least one nested flow with the actor X, in
  the same direction.
- `boundary import`: a module of an internal component imports a module that X owns.
  X must be an actor of the nested map, and a nested flow must connect the component
  and the actor X.

The owner X of an imported module is the component of the nearest ancestor map that
claims the module (`outside_owners`). If that component is the opening card of the map
or of a map above it, the module is inside the map and the import gives no line. The
actor of the nested map has the ID of X. At level 2, X can be a component of a map
above the direct parent map. Then the direct parent map must also have an actor X.

A line contains only the map prefix, the kind, the component names, and the fixed text.
The import count and the import pairs are in a row below the line and in the fields of
`judgement --json` (`fields`). The evidence of a line (`state`) is the claims of the
opening card and of the component X, the parent flows between them, the nested flows
with the actor X, and for a `boundary import` line, the import pairs with the imported
names. A change to one of these values makes an exact answer stale.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from systemap import card_review, nest
from systemap.evidence import owners
from systemap.model import Component, Flow, Model

FLOW_KIND = "boundary flow"
IMPORT_KIND = "boundary import"
KINDS = (FLOW_KIND, IMPORT_KIND)

Pair = tuple[str, str]


@dataclass(frozen=True)
class Finding:
    """One boundary line of a nested map, with the values below the line.

    `inner` is the internal component that the line names, or "" for a line about a
    parent flow. `parent_flow` gives the source and the destination of the parent flow
    that the line is about. `imports` gives the import pairs of a `boundary import` line.
    """

    line: str
    map_id: str
    card: str
    other: str
    inner: str
    parent_flow: Pair
    imports: tuple[Pair, ...] = ()

    @property
    def kind(self) -> str:
        return IMPORT_KIND if self.imports else FLOW_KIND

    @property
    def count(self) -> int:
        """The count of the modules of the internal component that import X."""
        return len({module for module, _target in self.imports})


def outside_owners(tree: nest.Tree, child: nest.Map, facts: dict[str, Any]) -> dict[str, str]:
    """Give the owner of each module outside the map `child`.

    The owner is the component of the nearest ancestor map that claims the module. A
    module of the card that opens a map on the path from the top map to `child` is
    inside the map, and has no owner here. At level 2, the owner can be a component of
    a map above the direct parent map. The direct parent map must then have an actor
    with the ID of the owner."""
    out: dict[str, str] = {}
    inside: set[str] = set()
    m: nest.Map | None = child
    while m is not None and m.parent is not None:
        parent = tree.get(m.parent)
        _add_owners(owners(parent.model, facts), m.card, out, inside)
        m = parent
    return out


def _add_owners(found: dict[str, str], card: str, out: dict[str, str], inside: set[str]) -> None:
    """Add the owners of one ancestor map to `out`, or the modules of `card` to `inside`.
    A module that a nearer map gave keeps its first value."""
    for module, owner in found.items():
        if module in out or module in inside:
            continue
        if owner == card:
            inside.add(module)
        else:
            out[module] = owner


def _is_actor(model: Model, cid: str) -> bool:
    found = model.find(cid)
    return found is not None and found.kind == "actor"


def _directed(model: Model, src: str, dst: str) -> list[Flow]:
    return [f for f in model.flows if f.src == src and f.dst == dst]


def _ends(f: Flow) -> tuple[tuple[str, str, bool], ...]:
    """Give the two readings of a flow: (inner, other, True) when the inner end sends,
    and (inner, other, False) when the other end sends."""
    return ((f.src, f.dst, True), (f.dst, f.src, False))


def _crossing(model: Model, card: str, inner: str, other: str) -> bool:
    """Tell if a flow end pair goes from an internal component to an actor of the map."""
    return other != card and _is_actor(model, other) and not _is_actor(model, inner)


def _nested_flow(m: nest.Map, parent: nest.Map, end: tuple[str, str, bool]) -> Finding | None:
    """Give the finding for one nested flow with an actor, or None if the parent map has
    the flow in the same direction."""
    inner, other, out = end
    if not _crossing(m.model, m.card, inner, other):
        return None
    src, dst = (m.card, other) if out else (other, m.card)
    if _directed(parent.model, src, dst):
        return None
    what = f"{inner} sends to actor {other}" if out else f"actor {other} sends to {inner}"
    line = f"{m.prefix}{FLOW_KIND}: {what}, and the parent map has no flow from {src} to {dst}"
    return Finding(line, m.id, m.card, other, inner, (src, dst))


def _flow_lines(tree: nest.Tree, m: nest.Map) -> Iterator[Finding]:
    """Give the `boundary flow` findings of one nested map."""
    parent = tree.get(m.parent or "")
    found = [_nested_flow(m, parent, end) for f in m.model.flows for end in _ends(f)]
    unique = {one.line: one for one in found if one is not None}
    yield from unique.values()
    yield from _parent_flow_lines(m, parent)


def _shown_inside(model: Model, other: str, out: bool) -> bool:
    """Tell if a nested flow connects an internal component and the actor `other`, with
    the actor as destination (`out`) or as source."""
    if not _is_actor(model, other):
        return False
    ends = [(g.src, g.dst) if out else (g.dst, g.src) for g in model.flows]
    return any(o == other and not _is_actor(model, i) for i, o in ends)


def _parent_flow_lines(m: nest.Map, parent: nest.Map) -> Iterator[Finding]:
    """Give the findings for the parent flows of the card with no nested flow."""
    edges = dict.fromkeys(f.edge for f in parent.model.flows if m.card in f.edge)
    for src, dst in edges:
        out = src == m.card
        other = dst if out else src
        if src == dst or _shown_inside(m.model, other, out):
            continue
        tail = f"to actor {other}" if out else f"from actor {other}"
        line = (
            f"{m.prefix}{FLOW_KIND}: the parent flow from {src} to {dst} has no nested flow {tail}"
        )
        yield Finding(line, m.id, m.card, other, "", (src, dst))


def import_pairs(tree: nest.Tree, m: nest.Map, facts: dict[str, Any]) -> dict[Pair, list[Pair]]:
    """Give the imports from the internal components of a nested map to the owners
    outside the map, for each pair of an internal component and an owner."""
    components = facts.get("components", {})
    inner = owners(m.model, facts)
    outside = outside_owners(tree, m, facts)
    out: dict[Pair, list[Pair]] = {}
    for module in sorted(components):
        p = inner.get(module)
        if not p:
            continue
        for target in sorted(components[module].get("uses", {})):
            q = outside.get(target)
            if q:
                out.setdefault((p, q), []).append((module, target))
    return out


def _toward(tree: nest.Tree, m: nest.Map, other: str) -> Pair:
    """Give the direction of the parent flow for a `boundary import` line: from the card
    to X, or from X to the card if only that parent flow exists."""
    parent, card = tree.get(m.parent or ""), m.card
    only_in = not _directed(parent.model, card, other) and _directed(parent.model, other, card)
    return (other, card) if only_in else (card, other)


def _import_lines(tree: nest.Tree, m: nest.Map, facts: dict[str, Any]) -> Iterator[Finding]:
    """Give the `boundary import` findings of one nested map."""
    model, card = m.model, m.card
    joined = {frozenset(f.edge) for f in model.flows}
    for (inner, other), rows in import_pairs(tree, m, facts).items():
        head = f"{m.prefix}{IMPORT_KIND}: {inner} imports {other}, and "
        if not _is_actor(model, other):
            line = f"{head}{other} is not an actor of the map inside {card}"
        elif frozenset((inner, other)) not in joined:
            line = f"{head}no flow connects {inner} and actor {other}"
        else:
            continue
        yield Finding(line, m.id, card, other, inner, _toward(tree, m, other), tuple(rows))


def map_findings(tree: nest.Tree, m: nest.Map, facts: dict[str, Any]) -> list[Finding]:
    """Give the boundary findings of one map. The top map has no boundary."""
    if m.parent is None or not tree.has(m.parent):
        return []
    return [*_flow_lines(tree, m), *_import_lines(tree, m, facts)]


def is_line(tree: nest.Tree, line: str) -> bool:
    """Tell if `line` is a boundary line of a nested map of the tree."""
    heads = tuple(f"{m.prefix}{kind}: " for m in tree.maps[1:] for kind in KINDS)
    return line.startswith(heads)


def lines(tree: nest.Tree, m: nest.Map, facts: dict[str, Any]) -> list[str]:
    """Give the boundary lines of one map, with the map prefix."""
    return [found.line for found in map_findings(tree, m, facts)]


def findings(tree: nest.Tree, facts: dict[str, Any]) -> dict[str, Finding]:
    """Give the boundary findings of all maps of the tree by line."""
    return {found.line: found for m in tree.maps for found in map_findings(tree, m, facts)}


def _real(tree: nest.Tree, m: nest.Map, cid: str) -> tuple[nest.Map, Component] | None:
    """Give the nearest ancestor map in which `cid` is not an actor, with the component.
    If no such map exists, give the direct parent map with its actor `cid`, or None."""
    first: tuple[nest.Map, Component] | None = None
    up = tree.parent_of(m)
    while up is not None:
        found = up.model.find(cid)
        if found is not None and found.kind != "actor":
            return up, found
        if found is not None and first is None:
            first = (up, found)
        up = tree.parent_of(up)
    return first


def _claims(where: tuple[nest.Map, Component] | None) -> Any:
    if where is None:
        return None
    m, card = where
    return [m.id, card.id, card_review.claims(card, m.model, m.meaning)]


def _records(flows: list[Flow]) -> list[list[str]]:
    return [[f.src, f.dst, f.artifact, f.kind, f.id] for f in flows]


def state(tree: nest.Tree, found: Finding, facts: dict[str, Any]) -> Any:
    """Give the evidence of a boundary line (see the module docstring)."""
    m = tree.get(found.map_id)
    parent = tree.get(m.parent or "")
    card = parent.model.find(found.card)
    other = found.other
    components = facts.get("components", {})
    return {
        "kind": found.kind,
        "card": _claims(None if card is None else (parent, card)),
        "other": _claims(_real(tree, m, other)),
        "parent_flows": _records(
            [f for f in parent.model.flows if set(f.edge) == {found.card, other}]
        ),
        "nested_flows": _records([f for f in m.model.flows if other in f.edge]),
        "imports": [
            [module, target, components.get(module, {}).get("uses", {}).get(target, [])]
            for module, target in found.imports
        ],
    }


def states(tree: nest.Tree, facts: dict[str, Any], wanted: set[str]) -> dict[str, Any]:
    """Give the evidence of each boundary line of the tree that is in `wanted`."""
    found = _findings_of(tree, facts, wanted)
    return {line: state(tree, one, facts) for line, one in found.items()}


def _findings_of(tree: nest.Tree, facts: dict[str, Any], wanted: set[str]) -> dict[str, Finding]:
    """Give the boundary findings whose lines are in `wanted`. If no line of `wanted` is a
    boundary line, the function does not find the boundary lines."""
    if not any(is_line(tree, line) for line in wanted):
        return {}
    return {line: one for line, one in findings(tree, facts).items() if line in wanted}


def fields(tree: nest.Tree, found: Finding) -> dict[str, Any]:
    """Give the `judgement --json` fields of a boundary line: `map_id`, `parent_flow`,
    `nested_flows`, and `import_pairs`. `parent_flow` has the artifacts of the parent
    flows in the direction of the line, and an empty list if no such flow exists."""
    m = tree.get(found.map_id)
    parent = tree.get(m.parent or "")
    src, dst = found.parent_flow
    return {
        "map_id": found.map_id,
        "parent_flow": {
            "src": src,
            "dst": dst,
            "artifacts": [f.artifact for f in _directed(parent.model, src, dst)],
        },
        "nested_flows": [
            {"src": f.src, "dst": f.dst, "artifact": f.artifact}
            for f in m.model.flows
            if found.other in f.edge
        ],
        "import_pairs": [{"module": a, "imports": b} for a, b in found.imports],
    }


def all_fields(tree: nest.Tree, found: Mapping[str, Finding]) -> dict[str, dict[str, Any]]:
    """Give the `judgement --json` fields of each line of `found` (`fields`)."""
    return {line: fields(tree, one) for line, one in found.items()}


def counts(found: Mapping[str, Finding]) -> dict[str, int]:
    """Give the import count of each `boundary import` line of `found` (`Finding.count`)."""
    return {line: one.count for line, one in found.items() if one.imports}


def detail(found: Mapping[str, Finding]) -> dict[str, list[str]]:
    """Give the import rows of each `boundary import` line of `found`, for the rows below
    the line."""
    return {
        line: [f"{a} imports {b}" for a, b in one.imports]
        for line, one in found.items()
        if one.imports
    }
