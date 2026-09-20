"""What a journey proposed from the imports would look like, and how well it matched.

This is kept for the record, not shipped: `systemap.journeys` asks the agent
to read the code instead. See the README, "Journeys".
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path as FilePath
from typing import Any

from systemap.evidence import owners
from systemap.model import Edge, Meaning, Model

# How far from the way in a walk is followed, and how many cards it may name:
# a journey a reader can hold is a handful of steps, not a tour of everything.
MAX_DEPTH = 6
MAX_CARDS = 8


@dataclass
class Walk:
    """A walk proposed for one way in: the cards in order, and where flows are missing."""

    entry: dict[str, str]
    cards: list[str] = field(default_factory=list)
    hops: list[tuple[Edge, bool]] = field(default_factory=list)

    @property
    def missing_flows(self) -> list[Edge]:
        return [edge for edge, drawn in self.hops if not drawn]

    def steps(self) -> list[Edge]:
        return [edge for edge, _drawn in self.hops]


def _names_used(root: FilePath, facts: dict[str, Any], module: str, func: str) -> set[str]:
    """The names the way in's own function uses, when it can be read.

    A module that holds a command line imports every part of the system; the
    function behind one way in touches a few of them. Reading that function
    is what tells a walk from `poetry publish` apart from a walk from
    `poetry install`.
    """
    record = facts.get("components", {}).get(module, {})
    path = root / str(record.get("file", ""))
    if not func or not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return set()
    body = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and n.name == func
        ),
        None,
    )
    if body is None:
        return set()
    out: set[str] = set()
    for node in ast.walk(body):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
    return out


def _first_modules(facts: dict[str, Any], module: str, used: set[str]) -> list[str]:
    """The modules the way in's function reaches first, by the names it uses."""
    uses = facts.get("components", {}).get(module, {}).get("uses", {})
    near = [m for m, names in uses.items() if used & set(names)]
    return near or list(uses)


def _reachable(facts: dict[str, Any], start: str, max_depth: int) -> list[str]:
    """The modules a run starting at `start` can reach through imports, nearest first."""
    components = facts.get("components", {})
    seen = {start}
    order = [start]
    edge = [start]
    for _depth in range(max_depth):
        nxt: list[str] = []
        for module in edge:
            for used in components.get(module, {}).get("uses", {}):
                if used not in seen and used in components:
                    seen.add(used)
                    order.append(used)
                    nxt.append(used)
        if not nxt:
            break
        edge = nxt
    return order


def propose(
    model: Model,
    facts: dict[str, Any],
    entry: dict[str, str],
    root: FilePath | None = None,
    max_cards: int = MAX_CARDS,
    max_depth: int = MAX_DEPTH,
) -> Walk:
    """The cards a run starting at this way in would pass through, in that order.

    With `root`, the function behind the way in is read first, so two ways in
    that share a module do not propose the same walk.
    """
    path = Walk(entry=entry)
    reached = _modules_reached(facts, entry, root, max_depth)
    _fill(path, reached, owners(model, facts), {f.edge for f in model.flows}, max_cards)
    return path


def _modules_reached(
    facts: dict[str, Any], entry: dict[str, str], root: FilePath | None, max_depth: int
) -> list[str]:
    """The modules a run from this way in touches, the way in's own module first."""
    module = entry["module"]
    used = _names_used(root, facts, module, entry.get("target") or entry.get("name", ""))
    first = _first_modules(facts, module, used) if used else []
    if not first:
        return _reachable(facts, module, max_depth)
    reached = [module, *first]
    for m in first:
        reached += [x for x in _reachable(facts, m, max_depth - 1) if x not in reached]
    return reached


def _fill(
    path: Walk, reached: list[str], owner: dict[str, str], flows: set[Edge], max_cards: int
) -> None:
    """Each module as the card that claims it, once each, with the hop between."""
    for module in reached:
        cid = owner.get(module)
        if cid is None or cid in path.cards:
            continue
        if path.cards:
            edge = (path.cards[-1], cid)
            path.hops.append((edge, edge in flows or (edge[1], edge[0]) in flows))
        path.cards.append(cid)
        if len(path.cards) >= max_cards:
            return


def actors(meaning: Meaning, journey_id: str) -> list[str]:
    """The cards a written journey puts the reader in front of, in order."""
    out: list[str] = []
    for j in meaning.journeys:
        if j.id != journey_id:
            continue
        for step in j.steps:
            for cid in (*step.acts, *step.edge):
                if cid not in out:
                    out.append(cid)
    return out


def overlap(proposed: list[str], written: list[str]) -> float:
    """How much of a written walk a proposal found: the share of cards in both."""
    a, b = set(proposed), set(written)
    return len(a & b) / len(a | b) if a | b else 0.0
