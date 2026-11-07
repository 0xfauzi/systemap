"""The change keys of the canvas data: the change marks and the roll-up of each map.

The Changes view of the canvas page (`page_canvas_changes`) reads these keys. This module
adds no facts. It uses the change data of each map (`change.for_page`), the change marks
of the change map (`schematic_change.change_marks`), and the map changes of each map
(`delta_model.MapChange` in the key `map` of the change data).

The roll-up comes from step 8 of docs/design/nested-parts.md (`page_rollup` on the branch
claude/nested-step-8). `Rollup`, `_counts`, `records` and `_below` are copies of that code.
The roll-up counts only the map changes of each map: the added, removed and changed
components, flows, sequences and invariants. An invariant is in the counts. Thus a map
with only a changed rule is a changed map. A source change is not in a count. It shows as
a change mark on each card that claims its module. Thus no change is counted two times.

A card that opens a map is "changed inside" when the roll-up of that map is `changed`:
that map or a map below it has map changes. If the base tree does not load, a map has no
map changes or a map change gives an error. Then the roll-up is not known. No card is then
"changed inside", and the data gives the reason, not zero.

The keys of a map with change data (`keys`), in addition to `ch`:

- `cm`: the change mark of each card that has a mark other than "none": "changed",
  "tests", "imports" or "end". A card that is not in `cm` has the mark "none".
- `cl`: the indexes of the lost flows: the flows of a card with changed source that have
  structural or declared evidence. Only these flows show in the Changes view.
- `cr`: the roll-up record. With a known roll-up, `n` is the count of the map changes of
  this map, `w` gives them in words (`counted`), and `b` is 1 when a map below this map
  changed. Without a known roll-up, `e` gives the reason.
- `ci`: the IDs of the cards that are "changed inside", only with a known roll-up.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from systemap import delta_model, evidence, nest, schematic_change
from systemap.delta_model import MapChange

# The groups of a roll-up count, with the noun of one item.
GROUPS = (
    ("components", "component"),
    ("flows", "flow"),
    ("sequences", "sequence"),
    ("invariants", "invariant"),
)
HOWS = (delta_model.ADDED, delta_model.REMOVED, delta_model.CHANGED)
CHANGED_INSIDE = "changed inside"
NO_MAP_CHANGES = "the change data has no map changes"


@dataclass(frozen=True)
class Rollup:
    """The roll-up record of one map.

    `counts` gives (how, noun, number) for each group with changes. `own` is the number of
    changed items of this map. `below` tells if a map below this map changed."""

    map_id: str
    counts: tuple[tuple[str, str, int], ...] = ()
    own: int = 0
    below: bool = False

    @property
    def changed(self) -> bool:
        """Tell if this map or a map below it changed."""
        return bool(self.own) or self.below


@dataclass(frozen=True)
class Rollups:
    """The roll-up records of all maps of one render.

    `error` gives the reason that the roll-up is not known, or "" when it is known."""

    records: dict[str, Rollup]
    error: str = ""

    @property
    def known(self) -> bool:
        return not self.error


def _counts(change: MapChange) -> tuple[tuple[str, str, int], ...]:
    out = []
    for group, noun in GROUPS:
        items = getattr(change, group)
        out += [(how, noun, n) for how in HOWS if (n := sum(i.how == how for i in items))]
    return tuple(out)


def records(tree: nest.Tree, changes: Mapping[str, MapChange | None]) -> dict[str, Rollup]:
    """Give the roll-up record of each map. A map without map changes has no counts."""
    own: dict[str, tuple[tuple[str, str, int], ...]] = {}
    for m in tree.maps:
        change = changes.get(m.id)
        own[m.id] = _counts(change) if change is not None and not change.error else ()
    changed = {map_id for map_id, counts in own.items() if counts}
    return {
        m.id: Rollup(
            m.id,
            own[m.id],
            sum(n for _how, _noun, n in own[m.id]),
            any(_below(m.id, other) for other in changed),
        )
        for m in tree.maps
    }


def _below(map_id: str, other: str) -> bool:
    """Tell if the map `other` is below the map `map_id`."""
    return other != map_id and (not map_id or other.startswith(map_id + "/"))


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def counted(r: Rollup) -> str:
    """Give the counts of a roll-up record, for example "1 added flow, 2 changed components"."""
    return ", ".join(plural(n, f"{how} {noun}") for how, noun, n in r.counts)


def rollups(tree: nest.Tree, changes: Mapping[str, Mapping[str, Any]]) -> Rollups:
    """Give the roll-up of the maps with change data (`change.for_page` of each map).

    The roll-up is not known when a map with change data has no map changes, or when its
    map changes give an error (the base tree did not load)."""
    found: dict[str, MapChange | None] = {}
    errors = []
    for m in tree.maps:
        ch = changes.get(m.id) or {}
        if not compared(ch):
            continue
        one = ch.get("map")
        found[m.id] = one if isinstance(one, MapChange) else None
        errors.append(one.error if isinstance(one, MapChange) else NO_MAP_CHANGES)
    return Rollups(records(tree, found), next((e for e in errors if e), ""))


def compared(ch: Mapping[str, Any]) -> bool:
    """Tell if the change data has a revision comparison (`page_changes.has_comparison`)."""
    return bool(ch.get("has_change") or ch.get("comparison_requested"))


def marks(
    m: nest.Map, backed: evidence.ByFlow, ch: Mapping[str, Any]
) -> schematic_change.ChangeMarks:
    """Give the change marks of the map, with the same inputs as the change map of a page."""
    return schematic_change.change_marks(
        m.model,
        backed,
        "change",
        set(ch.get("direct") or ()),
        set(ch.get("adjacent") or ()),
        schematic_change.tests_only(ch),
        set(ch.get("modules") or ()),
    )


def keys(
    tree: nest.Tree,
    m: nest.Map,
    backed: evidence.ByFlow,
    ch: Mapping[str, Any],
    found: Rollups,
) -> dict[str, Any]:
    """Give the change keys of one map (see the module docstring), or no key for a map
    without a revision comparison."""
    if not compared(ch):
        return {}
    got = marks(m, backed, ch)
    out: dict[str, Any] = {
        "cm": {cid: mark for cid, mark in got.cards.items() if mark != "none"},
        "cl": sorted(got.lost),
        "cr": _record(found, m.id),
    }
    if found.known:
        out["ci"] = _inside(tree, m, found.records)
    return {key: value for key, value in out.items() if value not in ({}, [])}


def _record(found: Rollups, map_id: str) -> dict[str, Any]:
    if not found.known:
        return {"e": found.error}
    r = found.records[map_id]
    return {"n": r.own, **({"w": counted(r)} if r.own else {}), **({"b": 1} if r.below else {})}


def _inside(tree: nest.Tree, m: nest.Map, found: Mapping[str, Rollup]) -> list[str]:
    """Give the IDs of the cards of `m` that open a map whose roll-up is `changed`."""
    opens: Collection[nest.Map] = tree.children(m)
    return sorted(child.card for child in opens if found[child.id].changed)
