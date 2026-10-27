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
- A line with a control character, such as a newline in a module name from a file name.
  The current line shows each such character as an escape (`terminal_text.printable`).
  This form is the first form, so the other forms read the line with the escapes.

For one release, an answer item in an earlier form selects the line in the current form.
`current_line` applies the patterns in their sequence. Thus an item can change in two or
more steps. `warnings` gives one warning for each item in an earlier form, and also the
warnings for the previous decision kind names. An item that is a current line gets no
warning: the callers give the current lines as `present`.

A name or a reason in a current line can contain the text of an earlier form. Thus each
pattern has its fixed text at its fixed position. An item that is a current line stays
the same: the callers give the current lines as `present`. An item that is longer than
`LONGEST_MIGRATED` also stays the same.

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
import functools
import re
from collections.abc import Callable, Container, Iterable
from typing import NamedTuple

from systemap import decision_kinds
from systemap.config import Answer
from systemap.decision_kinds import PREVIOUS, Answered
from systemap.journey_coverage import kind_words
from systemap.terminal_text import UNSAFE, printable


class EarlierForm(NamedTuple):
    """One earlier form of a line: its name, its pattern, and the current form."""

    name: str
    pattern: re.Pattern[str]
    current: str | Callable[[re.Match[str]], str]


def _group_kind(found: re.Match[str]) -> str:
    return f"{found['head']}{kind_words(found['kind'])}s{found['rest']}"


def _parsed(found: re.Match[str]) -> str:
    return f"{found['line']}{found['syntax'] or found['error']}"


_PREVIOUS_KINDS = "|".join(re.escape(name) for name in PREVIOUS)

# The parts of a line. Each pattern has its fixed text at its fixed position, and each
# variable part has a limit. Thus a match is linear in the length of the line, and the
# text of a name or of a reason cannot move the fixed text to a different position.
# A nested-map prefix can come before a line.
_MAP = r"(?:\S+: )?"
# A file in a location: no ":", and parentheses only in pairs, as in "app/(shop)/a.ts".
_FILE = r"[^():]*(?:\([^():]*\)[^():]*)*"
# A module name. A file name with a space gives a name with a space, as "pkg.my file".
# A word after a space does not start with "(", because " (" starts the location.
_MODULE = r"\S+(?: [^\s(]\S*)*"
# The location of a module record or of a test file, with the earlier line number.
_WHERE = rf"(?:module {_MODULE} \({_FILE}(?::\d+)?\)|test file [^:]+(?::\d+)?)"
# A quoted value as Python `repr` gives it.
_QUOTED = r"""(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")"""
# The reason of an earlier module record: a parse error, a read error, or an error name.
_ERROR = r"(?:source could not be parsed: \w+|source could not be read: .*?|\w+)"
_SYNTAX = "The parser could not parse the source syntax."

# The control characters and separators that `terminal_text.printable` replaces.
_CONTROL = UNSAFE.pattern.removeprefix("[").removesuffix("]")

# Each earlier form, and its current form.
EARLIER_FORMS = (
    EarlierForm(
        "control character",
        re.compile(rf"^(?=[^{_CONTROL}]*[{_CONTROL}])(?P<line>.*)\Z", re.S),
        lambda found: printable(found["line"]),
    ),
    EarlierForm(
        "parser name",
        re.compile(
            rf"^(?P<line>{_MAP}unknown surface: module {_MODULE} \({_FILE}(?::\d+)?\): {_ERROR})"
            r" under Python (?P<parser>\S+)$"
        ),
        r"\g<line> (parser version \g<parser>)",
    ),
    EarlierForm(
        "npm package",
        re.compile(
            rf"^(?P<line>{_MAP}unknown surface: [^'\"]+? extends {_QUOTED}): "
            r"the npm tsconfig package could not be read$"
        ),
        r"\g<line>: the configuration package could not be read",
    ),
    EarlierForm(
        "language syntax",
        re.compile(
            rf"^(?P<line>{_MAP}unknown surface: {_WHERE}: )"
            r"The parser could not parse the TypeScript syntax\."
            r"(?P<rest>(?: Source excerpt: .*| \(parser version [^()]*\))?)$"
        ),
        r"\g<line>The parser could not parse the source syntax.\g<rest>",
    ),
    EarlierForm(
        "parser version",
        re.compile(
            rf"^(?P<line>{_MAP}unknown surface: {_WHERE}: )"
            rf"(?:(?P<syntax>{re.escape(_SYNTAX)})(?: Source excerpt: .*?)?|(?P<error>{_ERROR}))"
            r" \(parser version [^()]*\)$"
        ),
        _parsed,
    ),
    EarlierForm(
        "source excerpt",
        re.compile(
            rf"^(?P<line>{_MAP}unknown surface: {_WHERE}: {re.escape(_SYNTAX)})"
            r" Source excerpt: .*$"
        ),
        r"\g<line>",
    ),
    EarlierForm(
        "module line number",
        re.compile(rf"^(?P<head>{_MAP}unknown surface: module \S+ \({_FILE}):\d+(?P<tail>\): .*)$"),
        r"\g<head>\g<tail>",
    ),
    EarlierForm(
        "test file line number",
        re.compile(rf"^(?P<head>{_MAP}unknown surface: test file [^:]+):\d+(?P<tail>: .*)$"),
        r"\g<head>\g<tail>",
    ),
    EarlierForm(
        "entry kind identifier",
        re.compile(
            rf"^(?P<head>{_MAP}entry point \d+ )(?P<kind>(?=[^\W_]*_)\w+?)s"
            # The component name can contain a space. It is the same in the two positions.
            r"(?P<rest> into (?P<card>[^()]+) have no sequence \(component (?P=card)\))$"
        ),
        _group_kind,
    ),
    EarlierForm(
        "provider pick",
        re.compile(
            rf"^(?P<line>{_MAP}(?:jev|decision) "
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
            rf"^(?P<head>{_MAP}crossing import: \S+ imports \S+) in \d+ modules?"
            r"(?P<tail> and no flow connects them)$"
        ),
        r"\g<head>\g<tail>",
    ),
    EarlierForm(
        "package export count",
        re.compile(
            rf"^(?P<head>{_MAP}unknown surface: package_export \S+ -> .+?)"
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


# The length limit of an item that a migration can change. The longest item in
# `[judgement] answered` of this repository has 57 characters, and the longest finding
# line in the tests has fewer than 600 characters. A longer item stays the same.
LONGEST_MIGRATED = 4096


def current_line(line: str, present: Container[str] = ()) -> str:
    """Give the current form of a line. A line in the current form stays the same.

    A line in `present` is a current line, so it also stays the same. A line that is
    longer than `LONGEST_MIGRATED` stays the same."""
    if line in present or len(line) > LONGEST_MIGRATED:
        return line
    return _migrated(line)


@functools.lru_cache(maxsize=1024)
def _migrated(line: str) -> str:
    """Apply each earlier form in sequence. The cache makes the work one time for each item."""
    for form in EARLIER_FORMS:
        found = form.pattern.match(line)
        if found:
            current = form.current
            line = current(found) if callable(current) else found.expand(current)
    return line


def current_items(items: Iterable[str], present: Container[str] = ()) -> tuple[str, ...]:
    """Give the current form of each configured item. An item in `present` stays the same."""
    return tuple(current_line(item, present) for item in items)


def retired(item: str) -> str:
    """Give the cause if an item is for a line that is no longer a finding, or ""."""
    return next((cause for pattern, cause in _RETIRED if pattern.match(item)), "")


class _Unmatched(NamedTuple):
    """The items of an answer that are not current lines, and the kind of the answer."""

    items: tuple[str, ...]
    kind: str
    reviewed: tuple[str, ...]


def _unmatched(answer: Answered, present: Container[str]) -> _Unmatched:
    return _Unmatched(
        tuple(item for item in answer.items if item not in present),
        answer.kind,
        tuple(item for item in answer.reviewed if item not in present),
    )


def kind_warnings(answers: Iterable[Answered], present: Container[str]) -> list[str]:
    """Give one warning for each previous kind name (`decision_kinds.warnings`).

    `present` contains the current lines. An item that is a current line gets no warning,
    also if its text looks like a decision line with a previous kind name."""
    return decision_kinds.warnings([_unmatched(answer, present) for answer in answers])


def warnings(answers: Iterable[Answered], present: Container[str] = ()) -> list[str]:
    """Give one warning for each previous kind name and each item in an earlier form.

    `present` contains the current lines. An item that is a current line gets no warning,
    because the item is correct."""
    given = [_unmatched(answer, present) for answer in answers]
    items = (item for answer in given for item in (*answer.items, *answer.reviewed))
    now = {item: current_line(item) for item in items}
    earlier = [
        item
        for item, line in now.items()
        if line != item
        and not retired(item)
        # `decision_kinds.warnings` gives the warning for a decision line.
        and decision_kinds.kind_of(item) is None
    ]
    return decision_kinds.warnings(given) + [
        f'warning: [judgement] answered uses the earlier line "{item}". Change it to '
        f'"{now[item]}". Only this release reads the earlier line.'
        for item in earlier
    ]


# ---- the earlier forms that need the current lines ----------------------------------

# The kind of the lines that moved. Items of other kinds do not change.
MOVED_KIND = "unknown surface: "
# A re-export target line, in the earlier form or in the current form. The key is the
# line without the line number of the location and without the names.
TARGET_LINE = re.compile(
    rf"^(?P<head>{_MAP}unknown surface: module \S+ \({_FILE})(?::\d+)?\): "
    rf"(?P<reason>the re-export target {_QUOTED} is outside the extracted module set\.)"
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
    now = current_line(item, present)
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
