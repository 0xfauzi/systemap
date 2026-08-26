"""Readable views of the facts file: what `systemap facts` prints.

The facts file runs to hundreds of kilobytes on a real tree, and an agent
that reads it whole spends its context on JSON it will not use. These
views are what the skill's first step reads instead, one question each:

    --modules          one line per module: its public names, its imports
                       inside the package, the tests that import it
    --module NAME      one module's full record
    --entry-points     where a run can start, the way a person names it
    --external         every third-party import, and the modules that use it
    --imports NAME     what one module imports, and what imports it

Nothing here is a fact the file does not hold; every line is read out of
the same records `systemap check` reads.
"""

from __future__ import annotations

import difflib
import json
from typing import Any

from systemap.extract import entry_label, is_empty_marker
from systemap.model import public_names


class UnknownModule(KeyError):
    """A module name the facts do not have; `closest` is the nearest they do."""

    def __init__(self, name: str, closest: str) -> None:
        super().__init__(name)
        self.name = name
        self.closest = closest


def _record(facts: dict[str, Any], name: str) -> dict[str, Any]:
    components: dict[str, Any] = facts.get("components", {})
    if name in components:
        return dict(components[name])
    matches = difflib.get_close_matches(name, sorted(components), n=1, cutoff=0.0)
    raise UnknownModule(name, matches[0] if matches else "")


def modules(facts: dict[str, Any]) -> list[str]:
    """One line per module, in name order."""
    components: dict[str, Any] = facts.get("components", {})
    out = [f"modules: {len(components)}; each with its public names, imports and tests"]
    for name in sorted(components):
        record = components[name]
        if is_empty_marker(record):
            out.append(f"  {name}: empty package marker")
            continue
        out.append(
            f"  {name}: {len(public_names(record))} names, "
            f"{len(record.get('imports', []))} imports, {record.get('tests_total', 0)} tests"
        )
    return out


def module(facts: dict[str, Any], name: str) -> list[str]:
    """One module's full record, as JSON a reader can scan."""
    return json.dumps(
        _record(facts, name), indent=2, ensure_ascii=False, sort_keys=True
    ).splitlines()


def entry_points(facts: dict[str, Any]) -> list[str]:
    points: list[dict[str, str]] = facts.get("entry_points", [])
    out = [f"entry points: {len(points)}; a journey names each that matters"]
    out += [f"  {entry_label(p)}: {p['module']}" for p in points]
    return out


def external(facts: dict[str, Any]) -> list[str]:
    """Every third-party import, with the modules that import it."""
    components: dict[str, Any] = facts.get("components", {})
    by_import: dict[str, list[str]] = {}
    for name in sorted(components):
        for imported in components[name].get("external", []):
            by_import.setdefault(imported, []).append(name)
    out = [f"external imports: {len(by_import)}; the model sdk line reads these"]
    out += [f"  {imported}: {', '.join(users)}" for imported, users in sorted(by_import.items())]
    return out


def imports(facts: dict[str, Any], name: str) -> list[str]:
    """What one module imports from the package, and what imports it."""
    record = _record(facts, name)
    uses: dict[str, list[str]] = record.get("uses", {})
    out = [f"{name} imports {len(uses)} modules of the package"]
    for target, names in sorted(uses.items()):
        taken = "the whole module" if names == ["*"] else ", ".join(names)
        out.append(f"  {target} ({taken})")
    importers: list[str] = record.get("imported_by", [])
    out.append(f"{name} is imported by {len(importers)} modules of the package")
    out += [f"  {m}" for m in importers]
    return out


VIEWS = (
    "views: --modules (one line per module), --module NAME (its record), --entry-points, "
    "--external, --imports NAME (what it imports and what imports it)"
)


def overview(summary: list[str]) -> list[str]:
    """What `systemap facts` prints with no option: the extract summary and the views."""
    return [*summary, VIEWS]
