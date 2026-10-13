"""Read the answer items of an earlier line form in `[judgement] answered`.

A finding line is also an identifier, so a change of its text needs a migration. The
facts format 8 changed the line for a source parse error. The line must not name one
language. Before, it ended with "under Python <version>". Now it ends with
"(parser version <version>)".

For one release, an answer item in the earlier form selects the line in the current
form. `current_line` gives the current form of an item. `warnings` gives one warning for
each item in the earlier form, and also the warnings for the previous decision kind
names.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from systemap import decision_kinds
from systemap.decision_kinds import Answered

# The earlier form of the parse error line. A nested-map prefix can come before it.
_EARLIER_PARSE_LINE = re.compile(
    r"^(?P<line>(?:\S+: )?unknown surface: module \S+ .+) under Python (?P<parser>\S+)$"
)


def current_line(line: str) -> str:
    """Give the current form of a line. A line in the current form stays the same."""
    found = _EARLIER_PARSE_LINE.match(line)
    return f"{found['line']} (parser version {found['parser']})" if found else line


def current_items(items: Iterable[str]) -> tuple[str, ...]:
    """Give the current form of each configured item."""
    return tuple(current_line(item) for item in items)


def warnings(answers: Iterable[Answered]) -> list[str]:
    """Give one warning for each previous kind name and each item in an earlier form."""
    given = list(answers)
    earlier = [
        item
        for answer in given
        for item in (*answer.items, *answer.reviewed)
        if current_line(item) != item
    ]
    return decision_kinds.warnings(given) + [
        f'warning: [judgement] answered uses the earlier line "{item}". Change it to '
        f'"{current_line(item)}". Only this release reads the earlier line.'
        for item in dict.fromkeys(earlier)
    ]
