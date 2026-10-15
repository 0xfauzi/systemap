"""Read the answer items of an earlier line form in `[judgement] answered`.

A finding line is also an identifier, so a change of its text needs a migration. This
module is the one migration path for `judgement` and `audit` (`AGENTS.md`). Each earlier
form has one pattern in `EARLIER_FORMS`. These lines changed:

- Facts format 8: the line for a source parse error ended with "under Python
  <version>". Then it ended with "(parser version <version>)".
- Facts format 9: the line for a configuration package ended with "the npm tsconfig
  package could not be read". Now it ends with "the configuration package could not be
  read".
- Facts format 9: the reason "The parser could not parse the TypeScript syntax." is now
  "The parser could not parse the source syntax."
- Facts format 11: a finding line is the identity of the finding. Thus it contains no
  value that changes while the finding stays the same. The `unknown surface` line of a
  module record had the location "(<file>:<line>)". The current line has "(<file>)". The
  line of a test file record had "test file <file>:<line>:". A parse line ended with
  " Source excerpt: '<text>'", with " (parser version <version>)", or with the two. The
  current line ends with the reason. The judgement report gives these values in rows
  below the line, and `judgement --json` gives them in `sources`.
- The `entry point` line for a group of entry points gave the kind identifier, as in
  "7 public_functions into Api". Now it gives the kind as words, as in "7 public
  functions into Api". A kind without "_", such as `route`, does not change.
- The `decision mis-fold` and `decision owner` lines of `audit` ended with the pick of the
  provider, for example ", which reads like Reader". The detail row now gives the pick.
- The kinds of the `audit` lines started with "jev". Now they start with "decision".
- Facts format 13: the `crossing import` line gave the count of the importing modules,
  as in "imports Config in 3 modules and". The `package_export` line gave "(+2 more)"
  after the target and the count of the targets in the reason. A count can change while
  the finding stays the same. The rows below the line give the counts now.

For one release, an answer item in an earlier form selects the line in the current form.
`current_line` applies the patterns in their sequence. Thus an item can change in two or
more steps. `warnings` gives one warning for each item in an earlier form, and also the
warnings for the previous decision kind names.

Two earlier forms need the current lines. `current_lines` reads them:

- A line that moved to a nested map. Before, the top map gave an `unknown surface` line
  for each module, and each nested map gave a copy with its map prefix. Now the map that
  owns the module gives the line one time. If the item without its map prefix agrees with
  one and only one current line without its map prefix, the item applies to that line.
- A re-export target line without names (facts format 9 to 10). The current line ends
  with the names, which come from the source. An item without names applies to a current
  line if the module, the file, and the target agree with one and only one current line
  of this form. A line for a declaration file has a different meaning, so an earlier item
  does not apply to it.

`judgement` gives no line about a test file. `retired` gives the cause for an item of such
a line. The report gives the item as a stale answer with this cause.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterable
from typing import NamedTuple

from systemap import decision_kinds
from systemap.config import Answer
from systemap.decision_kinds import PREVIOUS, Answered
from systemap.journey_coverage import kind_words


class EarlierForm(NamedTuple):
    """One earlier form of a line: its name, its pattern, and the current form."""

    name: str
    pattern: re.Pattern[str]
    current: str | Callable[[re.Match[str]], str]


def _group_kind(found: re.Match[str]) -> str:
    return f"{found['head']}{kind_words(found['kind'])}s{found['rest']}"


_PREVIOUS_KINDS = "|".join(re.escape(name) for name in PREVIOUS)

# Each earlier form, and its current form. A nested-map prefix can come before a line.
EARLIER_FORMS = (
    EarlierForm(
        "parser name",
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: module \S+ .+) under Python (?P<parser>\S+)$"
        ),
        r"\g<line> (parser version \g<parser>)",
    ),
    EarlierForm(
        "npm package",
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: .+ extends .+): "
            r"the npm tsconfig package could not be read$"
        ),
        r"\g<line>: the configuration package could not be read",
    ),
    EarlierForm(
        "language syntax",
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: .+: )"
            r"The parser could not parse the TypeScript syntax\.(?P<rest>.*)$"
        ),
        r"\g<line>The parser could not parse the source syntax.\g<rest>",
    ),
    EarlierForm(
        "parser version",
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: (?:module|test file) .+?)"
            r"(?: Source excerpt: .*?)? \(parser version [^()]*\)$"
        ),
        r"\g<line>",
    ),
    EarlierForm(
        "source excerpt",
        re.compile(
            r"^(?P<line>(?:\S+: )?unknown surface: (?:module|test file) .+?: "
            r"The parser could not parse the source syntax\.) Source excerpt: .*$"
        ),
        r"\g<line>",
    ),
    EarlierForm(
        "module line number",
        re.compile(
            r"^(?P<head>(?:\S+: )?unknown surface: module \S+ \([^():]+):\d+(?P<tail>\): .*)$"
        ),
        r"\g<head>\g<tail>",
    ),
    EarlierForm(
        "test file line number",
        re.compile(r"^(?P<head>(?:\S+: )?unknown surface: test file [^:]+):\d+(?P<tail>: .*)$"),
        r"\g<head>\g<tail>",
    ),
    EarlierForm(
        "entry kind identifier",
        re.compile(
            r"^(?P<head>(?:\S+: )?entry point \d+ )(?P<kind>\w*_\w*)s"
            r"(?P<rest> into .+ have no sequence.*)$"
        ),
        _group_kind,
    ),
    EarlierForm(
        "provider pick",
        re.compile(
            r"^(?P<line>(?:\S+: )?(?:jev|decision) "
            r"(?:mis-fold: \S+ claims \S+|owner: \S+ is claimed by no card))"
            r"(?:, which reads like .+|; it reads like .+|; closest: .+)$"
        ),
        r"\g<line>",
    ),
    EarlierForm(
        "decision kind name",
        re.compile(rf"^(?P<prefix>(?:[^:]*: )?)(?P<kind>{_PREVIOUS_KINDS}): (?P<rest>.*)$"),
        lambda found: f"{found['prefix']}{PREVIOUS[found['kind']]}: {found['rest']}",
    ),
    EarlierForm(
        "crossing count",
        re.compile(
            r"^(?P<head>(?:\S+: )?crossing import: \S+ imports \S+) in \d+ modules?"
            r"(?P<tail> and no flow connects them)$"
        ),
        r"\g<head>\g<tail>",
    ),
    EarlierForm(
        "package export count",
        re.compile(
            r"^(?P<head>(?:\S+: )?unknown surface: package_export .+? -> .+?)"
            r"(?: \(\+\d+ more\))?: \d+ (?P<reason>package\.json export targets have no "
            r"resolved TypeScript modules\.)$"
        ),
        r"\g<head>: The \g<reason>",
    ),
)

# The lines that are no longer findings, and the cause.
_RETIRED = (
    (
        re.compile(r"^(?:\S+: )?unknown surface: test file "),
        "judgement gives no line about a test file",
    ),
)


def current_line(line: str) -> str:
    """Give the current form of a line. A line in the current form stays the same."""
    for form in EARLIER_FORMS:
        found = form.pattern.match(line)
        if found:
            current = form.current
            line = current(found) if callable(current) else found.expand(current)
    return line


def current_items(items: Iterable[str]) -> tuple[str, ...]:
    """Give the current form of each configured item."""
    return tuple(current_line(item) for item in items)


def retired(item: str) -> str:
    """Give the cause if an item is for a line that is no longer a finding, or ""."""
    return next((cause for pattern, cause in _RETIRED if pattern.match(item)), "")


def warnings(answers: Iterable[Answered]) -> list[str]:
    """Give one warning for each previous kind name and each item in an earlier form."""
    given = list(answers)
    earlier = [
        item
        for answer in given
        for item in (*answer.items, *answer.reviewed)
        if current_line(item) != item
        and not retired(item)
        # `decision_kinds.warnings` gives the warning for a decision line.
        and decision_kinds.kind_of(item) is None
    ]
    return decision_kinds.warnings(given) + [
        f'warning: [judgement] answered uses the earlier line "{item}". Change it to '
        f'"{current_line(item)}". Only this release reads the earlier line.'
        for item in dict.fromkeys(earlier)
    ]


# ---- the earlier forms that need the current lines ----------------------------------

# The kind of the lines that moved. Items of other kinds do not change.
MOVED_KIND = "unknown surface: "
# A re-export target line, in the earlier form or in the current form. The key is the
# line without the line number of the location and without the names.
TARGET_LINE = re.compile(
    r"^(?P<head>(?:\S+: )?unknown surface: module \S+ \(.+?)(?::\d+)?\): "
    r"(?P<reason>the re-export target .+ is outside the extracted module set\.)"
    r"(?: Names: .*)?$"
)
_PREFIXED = re.compile(rf"^\S+: (?P<rest>{MOVED_KIND}.*)$")


def current_lines(answers: Iterable[Answer], lines: list[str]) -> list[Answer]:
    """Give the answers with each moved item changed to its current line.

    The configuration text does not change. The evidence digest of the current line must
    agree with the recorded digest."""
    present = set(lines)
    by_bare: dict[str, list[str]] = {}
    for line in lines:
        bare = _bare(line)
        if bare.startswith(MOVED_KIND):
            by_bare.setdefault(bare, []).append(line)
        if target := _target_key(line):
            by_bare.setdefault(target, []).append(line)
    out: list[Answer] = []
    for answer in answers:
        items = tuple(_current(item, present, by_bare) for item in answer.items)
        out.append(answer if items == answer.items else dataclasses.replace(answer, items=items))
    return out


def _bare(line: str) -> str:
    """Remove the map prefix of an `unknown surface` line."""
    found = _PREFIXED.match(line)
    return found["rest"] if found else line


def _current(item: str, present: set[str], by_bare: dict[str, list[str]]) -> str:
    # An item can also be in an earlier text form. Compare its current form. A moved item
    # becomes the current line, so the text migration does not change it.
    now = current_line(item)
    if now in present:
        return item
    found = by_bare.get(_bare(now), [])
    if not found and " Names: " not in now and (target := _target_key(now)):
        # Only the earlier form, without names: a current item must agree on its names.
        found = by_bare.get(target, [])
    return found[0] if len(found) == 1 else item


def _target_key(line: str) -> str:
    """Give the key of a re-export target line, or an empty string. The key keeps the
    map prefix, because the line of each map is a different line."""
    found = TARGET_LINE.match(line)
    return f"{found['head']}): {found['reason']}" if found else ""
