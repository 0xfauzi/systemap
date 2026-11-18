"""The page data of the atlas page: the canvas data object with the additions of the atlas.

The atlas page (docs/design/atlas.md) draws from the canvas data object (`canvas_data`).
It does not make a second copy of the map data. This module adds only the values that the
canvas page does not have:

- `y` of a flow: the relation sentence of the model (`Meaning.relation`). A flow without
  a sentence has no `y`.
- `ne` of a map with sequences: the entry points of the map with no sequence, as the
  linked page counts them (`page_sequences`, the scope of judgement). `t` is the count
  of the entry points of the map, `c` the count with a sequence, `x` the short names of
  the first NE_SHOWN entry points with no sequence, and `mo` the count of the others.
  The facts can have no entry points. Then the map has no `ne`.

The canvas page does not get these keys. Thus its data and its page size do not change.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from systemap import canvas_data, nest
from systemap.config import Config
from systemap.journey_coverage import outside_map, reviewed_entries, ways_in_without_journey
from systemap.page_sequences import short_entry

NE_SHOWN = 8


def add_sentences(tree: nest.Tree, data: dict[str, Any]) -> dict[str, Any]:
    """Add the relation sentence `y` to each flow of each map of `data`, in place.

    The maps of the data are in tree order, and the flows of a map are in model order
    (`canvas_data`). Give `data`."""
    for m, out in zip(tree.maps, data["maps"], strict=True):
        for flow, item in zip(m.model.flows, out["flows"], strict=True):
            sentence = m.meaning.relation(flow)
            if sentence:
                item["y"] = sentence
    return data


def add_entries(tree: nest.Tree, facts: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Add `ne` to each map of `data` with sequences, in place. Give `data`."""
    if facts.get("entry_points") is None:
        return data
    covered = reviewed_entries(m.meaning for m in tree.maps)
    for m, out in zip(tree.maps, data["maps"], strict=True):
        if not m.meaning.journeys:
            continue
        skip = outside_map(m.model, m.top, facts)
        every = ways_in_without_journey(m.meaning, facts, skip=skip, covered=())
        missing = [
            short_entry(p)
            for p in ways_in_without_journey(m.meaning, facts, skip=skip, covered=covered)
        ]
        out["ne"] = {
            "t": len(every),
            "c": len(every) - len(missing),
            "x": missing[:NE_SHOWN],
            "mo": max(0, len(missing) - NE_SHOWN),
        }
    return data


def build(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    open_lines: Collection[str] | None = None,
    changes: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Give the page data of the atlas page: `canvas_data.build`, the sentences and the
    entry points with no sequence."""
    data = canvas_data.build(cfg, tree, facts, open_lines=open_lines, changes=changes)
    return add_entries(tree, facts, add_sentences(tree, data))
