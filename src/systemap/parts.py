"""The nested parts of a map: the file name of each nested map.

All model files of a tree are in the folder of the top model, because a model file can
import a different file only from its own folder. The stem of a nested map is its map ID
in lower case, with `_` in place of each `/`. The file name is the stem with `.py`. A
`map=` value is relative to the model file of the parent map, which is in the same
folder. Thus the file name is also the `map=` value.

For example, the map `Gateway/Routes` has the file name `gateway_routes.py`.
"""

from __future__ import annotations

SUFFIX = ".py"


def map_id(parent: str, card: str) -> str:
    """Give the ID of the map that a component of the parent map opens."""
    return f"{parent}/{card}" if parent else card


def stem(map_id: str) -> str:
    """Give the stem of the model file of a nested map."""
    return map_id.lower().replace("/", "_")


def file_name(map_id: str) -> str:
    """Give the file name of a nested map, which is also its `map=` value."""
    return stem(map_id) + SUFFIX
