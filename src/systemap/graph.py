"""The graph gives component connections, sequence steps, and invariants as structured
data.

Each flow carries an artifact from one component to another. Sequence steps refer to
flows. Invariants specify the components that must obey them. The graph traversal uses
the flow direction.

Three continuity rules gave no usable sequence validation in seven benchmark maps.
Adjacent-edge checks marked 30 steps. actor checks marked 46 and 27 steps. The manual
examination found no real error in the 30 adjacent-edge results. The other results were
mostly correct branches and returns. The code includes none of these rules.

The traversal experiment used 366 pull requests. It found half of the changed
components. import traversal found all changed components. Thus, no ripple command is
available. The recorded experiment is in `bench/jev/ripple.py`. The plan command uses
the graph for context, not impact prediction.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from systemap.model import Edge, Flow, Invariant, Journey, Meaning, Model


@dataclass(frozen=True)
class Hop:
    """This record gives a traversed flow and its depth from the start."""

    flow: Flow
    depth: int


def out_flows(model: Model) -> dict[str, list[Flow]]:
    """This function indexes outgoing flows by component ID."""
    out: dict[str, list[Flow]] = {}
    for f in model.flows:
        out.setdefault(f.src, []).append(f)
    return out


def in_flows(model: Model) -> dict[str, list[Flow]]:
    """This function indexes incoming flows by component ID."""
    out: dict[str, list[Flow]] = {}
    for f in model.flows:
        out.setdefault(f.dst, []).append(f)
    return out


def neighbours(model: Model, card: str) -> list[str]:
    """This function gives components one flow from the specified component, in either
    direction.

    The experiment used 359 pull requests. The median list had 6 components. 72%
    included a component with changed code. Import lists had 20 components and a 77% hit
    rate. These results give context, not proof of impact. The recorded experiment is in
    `bench/jev/near.py`.
    """
    found = {f.dst for f in model.flows if f.src == card}
    found |= {f.src for f in model.flows if f.dst == card}
    return sorted(found - {card})


def steps_on(meaning: Meaning) -> dict[Edge, list[tuple[Journey, int]]]:
    """This function indexes sequence steps by flow edge, with sequence IDs and step
    numbers.
    """
    out: dict[Edge, list[tuple[Journey, int]]] = {}
    for journey in meaning.journeys:
        for k, step in enumerate(journey.steps):
            out.setdefault(step.edge, []).append((journey, k))
    return out


def rules_on(model: Model) -> dict[str, list[Invariant]]:
    """This function indexes invariants by component ID."""
    out: dict[str, list[Invariant]] = {}
    for rule in model.invariants:
        for cid in rule.governs:
            out.setdefault(cid, []).append(rule)
    return out


Keep = Callable[[Flow, int], bool]


def _always(_flow: Flow, _depth: int) -> bool:
    return True


@dataclass
class Walk:
    """This record contains traversed components, depths, and flows."""

    start: frozenset[str]
    depth_of: dict[str, int] = field(default_factory=dict)
    hops: list[Hop] = field(default_factory=list)

    @property
    def cards(self) -> list[str]:
        return sorted(self.depth_of)

    @property
    def reached(self) -> list[str]:
        """This function gives traversed components without the start components."""
        return sorted(c for c in self.depth_of if c not in self.start)

    @property
    def edges(self) -> set[Edge]:
        return {h.flow.edge for h in self.hops}

    def at(self, depth: int) -> list[str]:
        return sorted(c for c, d in self.depth_of.items() if d == depth)


def walk(model: Model, start: Iterable[str], keep: Keep = _always, max_depth: int = 3) -> Walk:
    """This function traverses outgoing flows from start while keep lets traversal
    continue.

    The keep callback runs once for each examined flow. A false result stops traversal
    on that edge. The max_depth parameter limits traversal through connected cycles.
    """
    leaving = out_flows(model)
    found = Walk(start=frozenset(start))
    found.depth_of.update(dict.fromkeys(found.start, 0))
    edge: list[str] = sorted(found.start)
    for depth in range(1, max_depth + 1):
        taken = [f for cid in edge for f in leaving.get(cid, []) if keep(f, depth)]
        found.hops += [Hop(f, depth) for f in taken]
        nxt = sorted({f.dst for f in taken} - set(found.depth_of))
        if not nxt:
            break
        found.depth_of.update(dict.fromkeys(nxt, depth))
        edge = nxt
    return found


def journeys_through(meaning: Meaning, edges: Iterable[Edge]) -> list[tuple[Journey, list[int]]]:
    """This function gives sequences that use the selected edges and their step numbers."""
    wanted = set(edges)
    out = []
    for journey in meaning.journeys:
        steps = [k for k, step in enumerate(journey.steps) if step.edge in wanted]
        if steps:
            out.append((journey, steps))
    return out


def rules_over(model: Model, cards: Iterable[str]) -> list[tuple[Invariant, list[str]]]:
    """This function gives invariants for the selected components and their applicable
    component sets.
    """
    wanted = set(cards)
    out = []
    for rule in model.invariants:
        named = sorted(wanted & set(rule.governs))
        if named:
            out.append((rule, named))
    return out
