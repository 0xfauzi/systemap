"""The judgement report refuses some answers of `[judgement] answered`.

A family answer selects all lines of a kind or of a component. For the kinds in
`NO_FAMILY_KINDS`, each line tells about the source of one import crossing, one module,
or one flow. One family answer for all these lines tells nothing about each line, and it
also hides a new line. Thus the report does not apply such an answer, and it gives it as
a refused answer with the cause:

- `family`: the answer has no items, and it selects lines of a kind in
  `NO_FAMILY_KINDS` with `kind`, `crossing`, `crossing_into`, or `crossing_from`.
- `items`: the answer has two or more items, and one or more items are lines of a kind
  in `NO_FAMILY_KINDS`.

From the module roles, the family text for `crossing import` lines tells the maintainer
to give the module use answers first. `correct_stale` corrects the stale answers of the
import crossings that module roles hide.

The rule reads only the form of the answer. Thus an answer that selects no line now is
a refused answer, not a stale answer. The configuration still reads these keys with no
error, so that `systemap decisions pending` can operate while the answer is refused.
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping
from typing import TYPE_CHECKING, Any

from systemap import answer_migrations, module_use
from systemap.config_answers import Answer
from systemap.crossing import CROSSING_LINE

if TYPE_CHECKING:
    from systemap.judgement import Answered

NO_FAMILY_KINDS = ("crossing import", "module use", "declared flow")
CROSSING_KIND = "crossing import"


def _bare(line: str) -> str:
    """Remove the map prefix of a line of a kind in `NO_FAMILY_KINDS`."""
    if _starts_with_kind(line):
        return line
    _head, sep, rest = line.partition(": ")
    return rest if sep and _starts_with_kind(rest) else line


def _starts_with_kind(line: str) -> bool:
    return any(line.startswith(f"{kind}: ") for kind in NO_FAMILY_KINDS)


def _kind(line: str) -> str:
    """Give the kind of `NO_FAMILY_KINDS` of a line, or an empty text."""
    bare = _bare(line)
    return next((kind for kind in NO_FAMILY_KINDS if bare.startswith(f"{kind}: ")), "")


def form(answer: Answer) -> tuple[str, str] | None:
    """Give the cause and the kind of a refused answer, or None for an answer that the
    report can apply."""
    if not answer.items:
        if answer.crossing is not None or answer.crossing_into or answer.crossing_from:
            return ("family", CROSSING_KIND)
        if answer.kind in NO_FAMILY_KINDS:
            return ("family", answer.kind)
        return None
    if len(answer.items) < 2:
        return None
    kinds = [kind for item in answer.items if (kind := _kind(item))]
    return ("items", kinds[0]) if kinds else None


def _selects(answer: Answer, line: str, present: Container[str]) -> bool:
    """Tell if a refused answer selects a line, by the rule of `judgement.answers`."""
    if answer.items:
        return line in answer_migrations.current_items(answer.items, present)
    bare = _bare(line)
    if answer.kind:
        return bare.startswith(f"{answer.kind}: ")
    found = CROSSING_LINE.match(bare)
    if found is None:
        return False
    if answer.crossing is not None:
        return {found[1], found[2]} <= set(answer.crossing)
    if answer.crossing_into:
        return found[2] == answer.crossing_into
    return found[1] == answer.crossing_from


def texts(given: Iterable[Answer], lines: list[str]) -> list[dict[str, Any]]:
    """Give one record for each refused answer: the label, the items, the cause, the
    text for the report, and the count of the lines of `lines` that the answer selects."""
    present = set(lines)
    out: list[dict[str, Any]] = []
    for answer in given:
        found = form(answer)
        if found is None:
            continue
        cause, kind = found
        count = sum(_selects(answer, line, present) for line in lines)
        if cause == "family":
            text = (
                f"{answer.label} selects {count} lines. A family answer cannot close a {kind} "
                "line. Remove the answer. Then give one exact answer for each line."
            )
            if kind == CROSSING_KIND:
                text += " Give the module use answers first."
        else:
            text = (
                f"{answer.label} has {len(answer.items)} items. An answer for a {kind} line "
                "must have one item. Give one exact answer for each line."
            )
        out.append(
            {
                "answer": answer.label,
                "items": list(answer.items),
                "cause": cause,
                "text": text,
                "lines": count,
            }
        )
    return out


UNUSED = (
    "'{item}' is not necessary: module roles close this import crossing. Remove it from "
    "[judgement] answered."
)


def correct_stale(
    result: Answered, states: Mapping[str, str], found: module_use.Index
) -> list[str]:
    """Correct the stale answers of `result` for the lines that module roles hide.

    - An item for a waiting crossing import line is not stale. The line can open again.
    - An item for a closed crossing import line is an unused answer with a row.
    - A module role answer for a module that is not a unit is inactive while the module
      is in the facts. It applies again when a new user with no flow comes. An answer for
      a unit with no line map in a scoped run is also not stale.

    Give the items of the unused answers."""
    kept: list[str] = []
    unused: list[str] = []
    for item in result.stale:
        line = answer_migrations.current_line(item, states)
        state = states.get(line)
        if state == module_use.CLOSED:
            result.unused.append(UNUSED.format(item=item))
            unused.append(item)
        elif state != module_use.WAITING and not _inactive(item, found):
            kept.append(item)
    result.stale[:] = kept
    return unused


def _inactive(item: str, found: module_use.Index) -> bool:
    """Tell if a module role item is inactive: its module is in the facts but it is not a
    unit, or it is a unit with no line map."""
    module = module_use.item_module(item)
    if module is None:
        return False
    unit = found.units.get(module)
    return unit.line_map is None if unit is not None else module in found.components
