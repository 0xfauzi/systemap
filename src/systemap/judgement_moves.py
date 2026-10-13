"""This module changes recorded answer items for finding lines that moved to a different map.

Before this change, the top map gave an `unknown surface` line for each module. Each
nested map also gave a copy of the line with its map prefix. After this change, each
module line occurs one time, in the map that owns the module. The lines about the full
repository occur one time, in the top map.

Thus an `item` of a recorded exact answer can name a line that does not occur. If the
item without its map prefix agrees with one and only one current line without its map
prefix, the item applies to that current line. The configuration text does not change.
The evidence digest of the current line must agree with the recorded digest.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from systemap.config import Answer
from systemap.judgement import unprefixed

# The kind of the lines that moved. Items of other kinds do not change.
MOVED_KIND = "unknown surface: "


def current_lines(answers: Iterable[Answer], lines: list[str]) -> list[Answer]:
    """Give the answers with each moved item changed to its current line."""
    present = set(lines)
    by_bare: dict[str, list[str]] = {}
    for line in lines:
        bare = unprefixed(line)
        if bare.startswith(MOVED_KIND):
            by_bare.setdefault(bare, []).append(line)
    out: list[Answer] = []
    for answer in answers:
        items = tuple(_current(item, present, by_bare) for item in answer.items)
        out.append(answer if items == answer.items else dataclasses.replace(answer, items=items))
    return out


def _current(item: str, present: set[str], by_bare: dict[str, list[str]]) -> str:
    if item in present:
        return item
    found = by_bare.get(unprefixed(item), [])
    return found[0] if len(found) == 1 else item
