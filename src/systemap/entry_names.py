"""The entry rule for a component whose modules do not define one public name to start.

A command-line script can start the full module and define no public name. The `entry`
of its component then cannot be a public name. This module gives the two other forms
of a correct `entry`:

- The name or the label of an entry point of the component modules, if the adapter
  wrote an empty `symbol` for it. An empty `symbol` tells that the entry point does not
  start one public name, for example a package bin or a `__main__` module.
- An empty `entry`, if the modules define no public name and start no entry point.
  Then no name is available for `entry`.

The functions read only language-neutral facts. A fact that is not known gives no pass.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from systemap.model import public_names, source_parsed


def started_module(entry: str, modules: Collection[str], facts: Mapping[str, Any]) -> str:
    """Give the module of an entry point that has the name or the label `entry`.

    The entry point must be in one of `modules` and do not start one public name. An
    entry point without a `symbol` fact is not known, and gives no module.
    """
    if not entry:
        return ""
    for point in facts.get("entry_points", []):
        named = entry in (point.get("name"), point.get("label"))
        if named and point.get("module") in modules and point.get("symbol") == "":
            return str(point["module"])
    return ""


def missing_entry(
    card: str, modules: list[str], symbols: list[str], facts: Mapping[str, Any]
) -> list[str]:
    """Give the check line for a component with an empty entry, or no line.

    The caller excludes the kinds that can have an empty entry. If the names are not
    known (`names_not_known`), the result is not known and gives no line."""
    if nothing_to_name(modules, len(symbols), facts) or names_not_known(modules, symbols, facts):
        return []
    return [f"{card} has no entry. Its modules are {', '.join(modules + symbols)}"]


def nothing_to_name(modules: Collection[str], symbols: int, facts: Mapping[str, Any]) -> bool:
    """True when the modules define no public name and start no entry point.

    `symbols` counts the symbol claims of the component. A symbol claim gives a name. If
    the facts have no entry point list, or a module did not parse fully, the names are
    not known, and the result is False.
    """
    points = facts.get("entry_points")
    if symbols or not modules or not isinstance(points, list):
        return False
    if any(point.get("module") in modules for point in points):
        return False
    records = facts.get("components", {})
    return all(_names_nothing(records.get(module, {})) for module in modules)


def _names_nothing(record: Mapping[str, Any]) -> bool:
    return source_parsed(record) and not public_names(record) and not record.get("unknown")


def names_not_known(modules: Collection[str], symbols: list[str], facts: Mapping[str, Any]) -> bool:
    """True when the modules give no known name to start, and a module has unknown names.

    A module has unknown names if it did not parse fully or has an unknown public surface.
    Then an empty entry is not a pass and not a failure. The `source inventory
    unresolved` group or the `unknown surface` group gives the module and the cause."""
    points = facts.get("entry_points")
    if symbols or not modules or not isinstance(points, list):
        return False
    if any(point.get("module") in modules for point in points):
        return False
    records = [facts.get("components", {}).get(module, {}) for module in modules]
    if any(public_names(record) for record in records):
        return False
    return any(not source_parsed(record) or record.get("unknown") for record in records)
