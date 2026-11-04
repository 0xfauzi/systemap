"""Read the answer items of an earlier line form in `[judgement] answered`.

A finding line is also an identifier, so a change of its text needs a migration. This
module is the one migration path for `judgement` and `audit` (`AGENTS.md`). Each earlier
form has one pattern in `EARLIER_FORMS`. These lines changed:

- The `jev mis-fold` and `jev owner` lines of `audit` ended with the pick of the provider,
  for example ", which reads like Reader". The detail row now gives the pick.
- Facts format 13: the `crossing import` line gave the count of the importing modules,
  as in "imports Config in 3 modules and". The `package_export` line gave "(+2 more)"
  after the target and the count of the targets in the reason. A count can change while
  the finding stays the same. The rows below the line give the counts now.
- A line with a control character, such as a newline in a module name from a file name.
  The current line shows each such character as an escape (`terminal_text.printable`).
  This form is the first form, so the other forms read the line with the escapes.

An answer item in an earlier form selects the line in the current form. `current_line`
applies the patterns in their sequence. Thus an item can change in two or more steps.
`warnings` gives one warning for each item in an earlier form. An item that is a current
line gets no warning: the callers give the current lines as `present`.

2.0.0 and 3.0.0 also read the forms of 2.0.0 and of the releases before it: the "jev"
kind names of the `audit` lines, the `entry point` line with a kind identifier such as
"public_functions", and the `unknown surface` lines with "under Python <version>", "the
npm tsconfig package", "the TypeScript syntax", a line number in the location, a source
excerpt, or a parser version. From 3.1.0, systemap does not read these forms. An item in
such a form matches no line, and the judgement report gives it as a stale answer. An item
with a previous kind name is an `audit` item. The judgement report also gives it as a
stale answer, with the current line (`renamed_items`, `decision_kinds.renamed`).

Before 2.0.0, the `jev mis-fold` and `jev owner` lines ended with the pick of the
provider. No release gave a `decision` line with the pick. The "provider pick" form gives
the current line of such an item after the change of its kind name.

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
from systemap.terminal_text import UNSAFE, printable


class EarlierForm(NamedTuple):
    """One earlier form of a line: its name, its pattern, and the current form."""

    name: str
    pattern: re.Pattern[str]
    current: str | Callable[[re.Match[str]], str]


# The parts of a line. Each pattern has its fixed text at its fixed position, and each
# variable part has a limit. Thus a match is linear in the length of the line, and the
# text of a name or of a reason cannot move the fixed text to a different position.
# A nested-map prefix can come before a line.
_MAP = r"(?:\S+: )?"
# A file in a location: no ":", and parentheses only in pairs, as in "app/(shop)/a.ts".
_FILE = r"[^():]*(?:\([^():]*\)[^():]*)*"
# A quoted value as Python `repr` gives it.
_QUOTED = r"""(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")"""
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
        "provider pick",
        re.compile(
            rf"^(?P<line>{_MAP}decision "
            r"(?:mis-fold: \S+ claims \S+|owner: \S+ is claimed by no card))"
            r"(?:, which reads like .+|; it reads like .+|; closest: .+)$"
        ),
        r"\g<line>",
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


def stale(item: str) -> str:
    """Tell why an answer item matches no line, and what the maintainer must do."""
    shown = f"'{printable(item)}'"
    if cause := retired(item):
        return f"{shown} is no longer a finding: {cause}. Remove it from [judgement] answered."
    if names := decision_kinds.renamed(item):
        now = current_line(item.replace(names[0], names[1], 1))
        return (
            f'{shown} has the previous kind name "{names[0]}", which systemap does not read. '
            f"Change it to '{printable(now)}' in [judgement] answered."
        )
    return f"{shown} is now missing. Remove it from [judgement] answered."


def renamed_items(answers: Iterable[Answer]) -> list[str]:
    """Give each item and each reviewed line with a previous kind name, one time.

    `audit` reads such an answer, but its items match no line. `judgement` gives these
    items as stale answers, because CI uses `judgement` and not `audit`."""
    found = (item for answer in answers for item in (*answer.items, *answer.reviewed))
    return list(dict.fromkeys(item for item in found if decision_kinds.renamed(item)))


def warnings(answers: Iterable[Answer], present: Container[str] = ()) -> list[str]:
    """Give one warning for each item in an earlier form.

    `present` contains the current lines. An item that is a current line gets no warning,
    because the item is correct."""
    items = (
        item
        for answer in answers
        for item in (*answer.items, *answer.reviewed)
        if item not in present
    )
    now = {item: current_line(item) for item in items}
    earlier = [
        item
        for item, line in now.items()
        if line != item
        and not retired(item)
        # A decision line is an `audit` line, and `judgement` does not give it. `audit`
        # changes an item in an earlier form of a decision line without a warning. An
        # item with a previous kind name is a stale answer (`renamed_items`).
        and decision_kinds.kind_of(item) is None
        and decision_kinds.renamed(item) is None
    ]
    return [
        f'warning: [judgement] answered uses the earlier line "{item}". Change it to "{now[item]}".'
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
