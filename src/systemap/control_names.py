"""The control name rule removes a source name that contains a control character.

A TypeScript string export name, such as `export { a as "x\\ny" }`, can contain a control
character. A package.json name, a bin key, and a pyproject.toml script key can also
contain one. A terminal can use such a character as a command, and a newline in a name
can divide one finding line into two lines. Thus the extraction removes each such name
from the facts. It records one unknown record with the cause `name` for each name. The
record shows the name as `terminal_text.printable` gives it.

A name without a control character does not change. Thus the facts of a normal
repository do not change.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from systemap import unknown_causes
from systemap.source_facts import entry_identity
from systemap.terminal_text import has_control, printable

# The lists of a module record whose items have a public `name`.
SURFACE_KEYS = ("functions", "classes", "errors", "types", "constants", "names", "api")
# The fields of an entry point that a finding line or a label can contain.
ENTRY_KEYS = ("kind", "name", "module", "target", "symbol")
# The fields of an entry point issue that its finding line contains.
ISSUE_KEYS = ("kind", "name", "target")
ENTRY_REASON = "The name or the target of the entry point contains a control character."


def _named_control(item: Any) -> bool:
    return isinstance(item, dict) and has_control(str(item.get("name", "")))


def refuse_surface_names(record: dict[str, Any]) -> None:
    """Remove each public name with a control character from a module record.

    Each removed name gives one unknown record with the cause `name`.
    """
    refused: list[str] = []
    for key in SURFACE_KEYS:
        refused += _removed(record, key)
    problems = [_name_problem(name) for name in dict.fromkeys(refused)]
    if problems:
        record.setdefault("unknown", []).extend(problems)


def _removed(record: dict[str, Any], key: str) -> list[str]:
    """Remove the items with a control character in their name from the list at `key`.
    Give the removed names."""
    items = record.get(key)
    if not isinstance(items, list):
        return []
    removed = [str(item["name"]) for item in items if _named_control(item)]
    if removed:
        record[key] = [item for item in items if not _named_control(item)]
    return removed


def _name_problem(name: str) -> dict[str, Any]:
    return {
        "line": 0,
        "reason": f"the export name '{printable(name)}' contains a control character.",
        "source": "",
        "cause": unknown_causes.NAME,
    }


def _entry_control(point: dict[str, Any]) -> bool:
    return any(has_control(str(point.get(key, ""))) for key in ENTRY_KEYS)


def refuse_entry_points(
    points: list[dict[str, Any]], issues: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Give the entry points without a control character, and the issues.

    Each removed entry point gives one issue with the cause `name`. The name and the
    target of each issue show a control character as an escape. If a kept entry point
    has `same_as` for a removed entry point, the first such entry point gets an empty
    `same_as`. The others then refer to it.
    """
    kept = [point for point in points if not _entry_control(point)]
    removed = [point for point in points if _entry_control(point)]
    if removed:
        _move_same_as(kept, {entry_identity(point) for point in removed})
    refused = [_entry_issue(point) for point in removed]
    return kept, [_shown_issue(issue) for issue in [*issues, *refused]]


def _move_same_as(points: Iterable[dict[str, Any]], removed: set[str]) -> None:
    moved: dict[str, str] = {}
    for point in points:
        same = point.get("same_as", "")
        if same in removed:
            point["same_as"] = moved.get(same, "")
            moved.setdefault(same, entry_identity(point))


def _entry_issue(point: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(point.get("kind", "")),
        "name": str(point.get("name", "")),
        "target": str(point.get("target", "") or point.get("module", "")),
        "reason": ENTRY_REASON,
        "cause": unknown_causes.NAME,
    }


def _shown_issue(issue: dict[str, Any]) -> dict[str, Any]:
    if not any(has_control(str(issue.get(key, ""))) for key in ISSUE_KEYS):
        return issue
    shown = {key: printable(str(issue[key])) for key in ISSUE_KEYS if key in issue}
    return {**issue, **shown}
