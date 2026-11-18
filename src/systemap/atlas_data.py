"""The page data of the atlas page: the canvas data object with the additions of the atlas.

The atlas page (docs/design/atlas.md) draws from the canvas data object (`canvas_data`).
It does not make a second copy of the map data. This module adds only the values that the
canvas page does not have:

- `y` of a flow: the relation sentence of the model (`Meaning.relation`). A flow without
  a sentence has no `y`.

The canvas page does not get these keys. Thus its data and its page size do not change.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from systemap import canvas_data, nest
from systemap.config import Config


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


def build(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    open_lines: Collection[str] | None = None,
    changes: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Give the page data of the atlas page: `canvas_data.build` and the sentences."""
    data = canvas_data.build(cfg, tree, facts, open_lines=open_lines, changes=changes)
    return add_sentences(tree, data)
