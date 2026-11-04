"""The roll-up of the changes of a map tree, for the Changes panel of each page.

Each page compares the model of its map at the comparison base with the model on disk
(`delta_model.for_page`). After the render has these map changes for all maps, this
module makes one roll-up record for each map: the counts of the added, removed, and
changed components, flows, sequences, and invariants, and a flag for a changed map below
it. An invariant is in the counts, so that a map with only a changed rule shows as
changed. If the base tree does not load, the roll-up is not known, and the panel gives
the reason. It does not give zero.

The roll-up counts only the map changes of each map. A source change shows on each page
that contains its module, but it is not in a count. Thus no change is counted two times.

The Changes panel of a page gets two sections:

- Changes in nested maps: one link for each changed map below the page, to the Changes
  view of that map (`<path>/index.html#changes`), with its counts.
- Boundary changes: the changes at the frame of each nested map below the page
  (`boundary_changes`). The pull request summary gives the same rows.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from systemap import boundary_changes, delta_model, nest
from systemap.boundary_changes import plural
from systemap.config import Config
from systemap.delta_model import MapChange

# The groups of a roll-up count, with the noun of one item.
GROUPS = (
    ("components", "component"),
    ("flows", "flow"),
    ("sequences", "sequence"),
    ("invariants", "invariant"),
)
HOWS = (delta_model.ADDED, delta_model.REMOVED, delta_model.CHANGED)


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


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
class Changes:
    """The roll-up records and the boundary changes of one render.

    `boundary` is None if the base tree did not load. Then the panel gives the reason."""

    rollups: dict[str, Rollup]
    boundary: boundary_changes.BoundaryChanges | None = None
    error: str = ""

    @property
    def known(self) -> bool:
        """Tell if the base tree loaded. Without it, the roll-up records are not known."""
        return self.boundary is not None


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


def collect(cfg: Config, tree: nest.Tree, pages: Mapping[str, Mapping[str, Any]]) -> Changes:
    """Give the roll-up records and the boundary changes from the change data of each page.

    The base tree is the committed tree at the comparison base of the top page."""
    changes = {map_id: ch.get("map") for map_id, ch in pages.items()}
    rollups = records(tree, changes)
    base = str(pages.get(tree.top.id, {}).get("comparison_base") or "")
    if not base:
        return Changes(rollups, None, "the page has no base revision")
    old = delta_model.tree_at(cfg, base)
    if isinstance(old, str):
        return Changes(rollups, None, old)
    return Changes(rollups, boundary_changes.compute(old, tree))


def counted(r: Rollup) -> str:
    """Give the counts of a roll-up record, for example "1 added flow, 2 changed components"."""
    return ", ".join(plural(n, f"{how} {noun}") for how, noun, n in r.counts)


def up(at: str) -> str:
    """Give the relative path from the page of the map `at` to the top page folder."""
    return "../" * len(at.split("/")) if at else ""


def href(at: str, map_id: str) -> str:
    """Give the link from the page of the map `at` to the page of the map `map_id`."""
    down = "".join(f"{quote(part, safe='')}/" for part in map_id.split("/")) if map_id else ""
    return f"{up(at)}{down}index.html"


def _code(text: str) -> str:
    return f"<code>{esc(text)}</code>"


def _unknown(found: Changes) -> str:
    return f'<p class="chg-text">Not known, because {esc(found.error)}.</p>'


def _nested_rows(maps: tuple[nest.Map, ...], at: str, found: Changes) -> str:
    if not found.known:
        return _unknown(found)
    rows = "".join(
        f'<li><a href="{esc(href(at, other.id))}#changes">{esc(other.id)}</a>'
        f'<span class="chg-mc__what">{esc(counted(found.rollups[other.id]))}</span></li>'
        for other in maps
        if _below(at, other.id) and found.rollups[other.id].own
    )
    if not rows:
        return '<p class="chg-text">No map below this map changed.</p>'
    return f'<ul class="chg-nested">{rows}</ul>'


def _boundary_rows(at: str, found: Changes) -> str:
    if found.boundary is None:
        return _unknown(found)
    within = found.boundary.within(at)
    counts = {map_id: r.own for map_id, r in found.rollups.items()}
    rows = boundary_changes.rows(within, counts, _code, esc)
    if not rows:
        return '<p class="chg-text">No boundary changed.</p>'
    items = "".join(f"<li>{row}</li>" for row in rows)
    return (
        f'<ul class="chg-nested">{items}</ul>'
        '<p class="chg-foot">Accept or reject each boundary change in the review.</p>'
    )


def section(maps: tuple[nest.Map, ...], at: str, found: Changes | None) -> str:
    """Give the two sections of the Changes panel for the page of the map `at`, or
    nothing for a map without maps below it or without change data. `maps` are the maps
    of the tree."""
    if found is None or not any(_below(at, m.id) for m in maps):
        return ""
    return (
        '<section class="chg-sec" id="chg-nested" aria-label="Changes in nested maps">'
        '<div class="chg-sec__h"><h3 class="chg-cap">CHANGES IN NESTED MAPS</h3></div>'
        + _nested_rows(maps, at, found)
        + "</section>"
        '<section class="chg-sec" id="chg-boundary" aria-label="Boundary changes">'
        '<div class="chg-sec__h"><h3 class="chg-cap">BOUNDARY CHANGES</h3></div>'
        + _boundary_rows(at, found)
        + "</section>"
    )


CSS = r"""
.chg-nested{margin:0;padding:0 0 0 18px;font-size:13px;line-height:20px}
.chg-nested li{margin:2px 0}
.chg-nested .chg-mc__what{display:block}
"""
