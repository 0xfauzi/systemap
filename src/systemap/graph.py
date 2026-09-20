"""The map as something to walk: what a card feeds, what walks through it, what governs it.

The model holds more than a list of parts. Each flow says that a named
artifact moves from one card to another; each journey step traces one of
those flows; each invariant names the cards whose code must keep it true.
Together they answer the question a reader of a change actually has: if
this part changed, what else does that reach, and what does it mean for
someone using the system?

This module is the walk itself, and nothing else: it reads a model and a
meaning and returns plain data, so the commands that ask (`ripple`, the
journey checks, `plan`) all follow the same structure and can be tested
without a repository.

The walk follows flows in the direction they carry their artifact: a change
in the card that sends something can reach the card that receives it. It
does not walk backwards, because a reader of a change is asking what this
change affects, not what could have affected it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from systemap.model import Edge, Flow, Invariant, Journey, Meaning, Model


@dataclass(frozen=True)
class Hop:
    """One step of a walk: the flow followed, and how many flows from the start."""

    flow: Flow
    depth: int


def out_flows(model: Model) -> dict[str, list[Flow]]:
    """The flows leaving each card, by card id."""
    out: dict[str, list[Flow]] = {}
    for f in model.flows:
        out.setdefault(f.src, []).append(f)
    return out


def in_flows(model: Model) -> dict[str, list[Flow]]:
    """The flows arriving at each card, by card id."""
    out: dict[str, list[Flow]] = {}
    for f in model.flows:
        out.setdefault(f.dst, []).append(f)
    return out


def steps_on(meaning: Meaning) -> dict[Edge, list[tuple[Journey, int]]]:
    """For each edge, the journey steps that trace it, as (journey, step number)."""
    out: dict[Edge, list[tuple[Journey, int]]] = {}
    for journey in meaning.journeys:
        for k, step in enumerate(journey.steps):
            out.setdefault(step.edge, []).append((journey, k))
    return out


def rules_on(model: Model) -> dict[str, list[Invariant]]:
    """The invariants that name each card, by card id."""
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
    """What a walk reached: the cards, how far each is, and the flows followed."""

    start: frozenset[str]
    depth_of: dict[str, int] = field(default_factory=dict)
    hops: list[Hop] = field(default_factory=list)

    @property
    def cards(self) -> list[str]:
        return sorted(self.depth_of)

    @property
    def reached(self) -> list[str]:
        """The cards the walk arrived at, without the ones it started from."""
        return sorted(c for c in self.depth_of if c not in self.start)

    @property
    def edges(self) -> set[Edge]:
        return {h.flow.edge for h in self.hops}

    def at(self, depth: int) -> list[str]:
        return sorted(c for c, d in self.depth_of.items() if d == depth)


def walk(model: Model, start: Iterable[str], keep: Keep = _always, max_depth: int = 3) -> Walk:
    """Follow the flows out of `start` while `keep` says the artifact carries the change.

    `keep(flow, depth)` is asked once per flow considered. Answering no stops
    the walk there: the artifact that flow carries is the same as before, so
    nothing past it is reached through this edge. `max_depth` is the last
    resort against a map where everything eventually reaches everything.
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
    """The journeys that trace any of these edges, each with the step numbers."""
    wanted = set(edges)
    out = []
    for journey in meaning.journeys:
        steps = [k for k, step in enumerate(journey.steps) if step.edge in wanted]
        if steps:
            out.append((journey, steps))
    return out


def rules_over(model: Model, cards: Iterable[str]) -> list[tuple[Invariant, list[str]]]:
    """The invariants governing any of these cards, each with the cards it governs here."""
    wanted = set(cards)
    out = []
    for rule in model.invariants:
        named = sorted(wanted & set(rule.governs))
        if named:
            out.append((rule, named))
    return out


def gaps(journey: Journey) -> list[int]:
    """The step numbers where a journey jumps: step k does not carry on from k-1.

    A step carries on when it starts where the one before it ended, or when it
    leaves the same card (two things sent from one place), or when it ends
    where the one before it ended (two things arriving at one place). Anything
    else means the reader is asked to jump, and a step is probably missing.
    """
    out = []
    for k in range(1, len(journey.steps)):
        before, now = journey.steps[k - 1].edge, journey.steps[k].edge
        carries_on = now[0] == before[1] or now[0] == before[0] or now[1] == before[1]
        if not carries_on:
            out.append(k)
    return out
