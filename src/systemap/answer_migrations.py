"""Read the answer items of an earlier line form in `[judgement] answered`.

A finding line is also an identifier, so a change of its text needs a migration. A
shared finding line must not name one language. These lines changed:

- Facts format 8: the line for a source parse error ended with "under Python
  <version>". Now it ends with "(parser version <version>)".
- Facts format 9: the line for a configuration package ended with "the npm tsconfig
  package could not be read". Now it ends with "the configuration package could not be
  read".
- Facts format 9: the reason "The parser could not parse the TypeScript syntax." is now
  "The parser could not parse the source syntax."
- The `entry point` line for a group of entry points gave the kind identifier, as in
  "7 public_functions into Api". Now it gives the kind as words, as in "7 public
  functions into Api". A kind without "_", such as `route`, does not change.
- Facts format 11: a finding line is the identity of the finding. Thus it contains no
  value that changes while the finding stays the same (`AGENTS.md`). The `unknown
  surface` line of a module record had the location "(<file>:<line>)". The current line has
  "(<file>)". The line of a test file record had "test file <file>:<line>:". The current line has
  "test file <file>:". A parse line ended with " Source excerpt: '<text>'", with
  " (parser version <version>)", or with the two. The current line ends with the reason. The
  judgement report gives these values in rows below the line, and `judgement --json`
  gives them in `sources`.

For one release, an answer item in an earlier form selects the line in the current
form. `current_line` gives the current form of an item. It applies the patterns in
their sequence. Thus an item can change in two or more steps. `warnings` gives one warning for
each item in an earlier form, and also the warnings for the previous decision kind
names.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from systemap import decision_kinds
from systemap.decision_kinds import Answered
from systemap.journey_coverage import kind_words

# Each earlier form, and its current form. A nested-map prefix can come before a line.
_EARLIER_FORMS = (
    (
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: module \S+ .+) under Python (?P<parser>\S+)$"
        ),
        r"\g<line> (parser version \g<parser>)",
    ),
    (
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: .+ extends .+): "
            r"the npm tsconfig package could not be read$"
        ),
        r"\g<line>: the configuration package could not be read",
    ),
    (
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: .+: )"
            r"The parser could not parse the TypeScript syntax\.(?P<rest>.*)$"
        ),
        r"\g<line>The parser could not parse the source syntax.\g<rest>",
    ),
    # Facts format 11: the parse line without its source excerpt and parser version.
    (
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: (?:module|test file) .+?)"
            r"(?: Source excerpt: .*?)? \(parser version [^()]*\)$"
        ),
        r"\g<line>",
    ),
    # Facts format 11: the earlier parse line with an excerpt and no parser version.
    (
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: (?:module|test file) .+?: "
            r"The parser could not parse the source syntax\.) Source excerpt: .*$"
        ),
        r"\g<line>",
    ),
    # Facts format 11: the location of a module record without the line number.
    (
        re.compile(
            r"^(?P<head>(?:\S+: )?unknown surface: module \S+ \([^():]+):\d+(?P<tail>\): .*)$"
        ),
        r"\g<head>\g<tail>",
    ),
    # Facts format 11: the file of a test file record without the line number.
    (
        re.compile(r"^(?P<head>(?:\S+: )?unknown surface: test file [^:]+):\d+(?P<tail>: .*)$"),
        r"\g<head>\g<tail>",
    ),
)


# The `entry point` line for a group, with a kind identifier that contains "_".
_GROUP_KIND = re.compile(
    r"^(?P<head>(?:\S+: )?entry point \d+ )(?P<kind>\w*_\w*)s(?P<rest> into .+ have no sequence.*)$"
)


def current_line(line: str) -> str:
    """Give the current form of a line. A line in the current form stays the same."""
    for earlier, current in _EARLIER_FORMS:
        found = earlier.match(line)
        if found:
            line = found.expand(current)
    group = _GROUP_KIND.match(line)
    if group:
        return f"{group['head']}{kind_words(group['kind'])}s{group['rest']}"
    return line


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
