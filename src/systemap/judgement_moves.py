"""This module changes recorded answer items for finding lines that moved to a different map.

Before this change, the top map gave an `unknown surface` line for each module. Each
nested map also gave a copy of the line with its map prefix. After this change, each
module line occurs one time, in the map that owns the module. The lines about the full
repository occur one time, in the top map.

Thus an `item` of a recorded exact answer can name a line that does not occur. If the
item without its map prefix agrees with one and only one current line without its map
prefix, the item applies to that current line. The configuration text does not change.
The evidence digest of the current line must agree with the recorded digest.

The line for a source parse error also changed. Its source excerpt is now the line of
the error and the line before it, and the line ends with the parser version. An item
in the earlier form applies to a current line in the same way: its text up to the end
of "The parser could not parse the source syntax." must agree with one and only one
current line.

The line for a re-export target outside the extracted module set also changed (facts
format 9 to 10). The earlier line had the location `:1` for each statement, and one line
for each name. The current line has the line of the statement and ends with the names.
An item in the earlier form applies to a current line if the module, the file, and the
target agree with one and only one current line of this form. A line for a declaration
file has a different meaning, so an earlier item does not apply to it.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable

from systemap import answer_migrations
from systemap.config import Answer
from systemap.judgement import unprefixed

# The kind of the lines that moved. Items of other kinds do not change.
MOVED_KIND = "unknown surface: "
# The fixed text of the parse line. The excerpt and the parser version come after it.
PARSE_REASON = "The parser could not parse the source syntax."
# A re-export target line, in the earlier form or in the current form. The key is the
# line without the line number of the location and without the names.
TARGET_LINE = re.compile(
    r"^(?P<head>(?:\S+: )?unknown surface: module \S+ \(.+?)(?::\d+)?\): "
    r"(?P<reason>the re-export target .+ is outside the extracted module set\.)"
    r"(?: Names: .*)?$"
)


def current_lines(answers: Iterable[Answer], lines: list[str]) -> list[Answer]:
    """Give the answers with each moved item changed to its current line."""
    present = set(lines)
    by_bare: dict[str, list[str]] = {}
    for line in lines:
        bare = unprefixed(line)
        if bare.startswith(MOVED_KIND):
            by_bare.setdefault(bare, []).append(line)
        if PARSE_REASON in bare:
            by_bare.setdefault(_parse_key(bare), []).append(line)
        if target := _target_key(line):
            by_bare.setdefault(target, []).append(line)
    out: list[Answer] = []
    for answer in answers:
        items = tuple(_current(item, present, by_bare) for item in answer.items)
        out.append(answer if items == answer.items else dataclasses.replace(answer, items=items))
    return out


def _current(item: str, present: set[str], by_bare: dict[str, list[str]]) -> str:
    # An item can also be in an earlier form (`answer_migrations`). Compare its current
    # form. A moved item becomes the current line, so the form migration does not change it.
    now = answer_migrations.current_line(item)
    if now in present:
        return item
    found = by_bare.get(unprefixed(now), [])
    if not found and PARSE_REASON in now:
        found = by_bare.get(_parse_key(unprefixed(now)), [])
    if not found and (target := _target_key(now)):
        found = by_bare.get(target, [])
    return found[0] if len(found) == 1 else item


def _target_key(line: str) -> str:
    """Give the key of a re-export target line, or an empty string. The key keeps the
    map prefix, because the line of each map is a different line."""
    found = TARGET_LINE.match(line)
    return f"{found['head']}): {found['reason']}" if found else ""


def _parse_key(line: str) -> str:
    """Give the text of a parse line up to the end of the fixed reason."""
    return line[: line.index(PARSE_REASON) + len(PARSE_REASON)]
