"""The facts command prints selected views of extracted source data.

Each option gives module summaries, docstrings, public names, imports, or entry points.
The views use the same records as the map checks. They give test counts without test
names.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from systemap.extract import entry_label, is_empty_marker
from systemap.model import public_names


class UnknownModule(KeyError):
    """The requested module is missing from the facts. The closest attribute gives the
    nearest available name.
    """

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


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def first_sentence(text: str) -> str:
    """This function gives the opening sentence of the initial docstring paragraph, or an
    empty string.
    """
    text = " ".join((text or "").split())
    if not text:
        return ""
    return re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]


NO_DOCSTRING = "No docstring is available."
EMPTY_MARKER = "empty package marker"


def _opening(record: dict[str, Any]) -> str:
    """This function gives the opening docstring sentence or a notice that no docstring is
    available.
    """
    return first_sentence(record.get("docstring", "")) or NO_DOCSTRING


def kinds(record: dict[str, Any]) -> list[tuple[str, str]]:
    """This function gives public names and their kinds in source order.

    Re-exports give their defining modules. Older facts use the recorded functions,
    classes, errors, and constants.
    """
    names = record.get("names")
    if names is not None:
        out: list[tuple[str, str]] = []
        for n in names:
            kind = str(n.get("kind", "object"))
            source = n.get("reexport_of")
            out.append((n["name"], f"{kind}, re-exported from {source}" if source else kind))
        return out
    return (
        [(f["name"], "function") for f in record.get("functions", [])]
        + [(c["name"], "class") for c in record.get("classes", [])]
        + [(e["name"], "error") for e in record.get("errors", [])]
        + [(k["name"], "constant") for k in record.get("constants", [])]
    )


def modules(facts: dict[str, Any]) -> list[str]:
    """This function gives a summary line for each module in name order."""
    components: dict[str, Any] = facts.get("components", {})
    out = [
        (
            f"modules: {len(components)}. Each line gives the opening docstring sentence "
            f"and the public name, import, and test counts."
        )
    ]
    for name in sorted(components):
        record = components[name]
        if is_empty_marker(record):
            out.append(f"  {name}: {EMPTY_MARKER}")
            continue
        counts = ", ".join(
            (
                _plural(len(public_names(record)), "name"),
                _plural(len(record.get("imports", [])), "import"),
                _plural(int(record.get("tests_total", 0)), "test"),
            )
        )
        out.append(f"  {name}: {_opening(record)} ({counts})")
    return out


def docstrings(facts: dict[str, Any]) -> list[str]:
    """This function gives the opening docstring sentence for each module."""
    components: dict[str, Any] = facts.get("components", {})
    with_one = sum(1 for r in components.values() if first_sentence(r.get("docstring", "")))
    out = [
        (
            f"docstrings: {with_one} of {len(components)} modules have docstrings. Each "
            f"line gives the opening sentence."
        )
    ]
    for name in sorted(components):
        record = components[name]
        out.append(f"  {name}: {EMPTY_MARKER if is_empty_marker(record) else _opening(record)}")
    return out


def _listed(items: list[str], none: str) -> str:
    return ", ".join(items) if items else none


def module(facts: dict[str, Any], name: str) -> list[str]:
    """This function formats one module record without test names."""
    record = _record(facts, name)
    out = [f"{name} ({record.get('file', '')})"]
    if is_empty_marker(record):
        out.append(f"  {EMPTY_MARKER}: The __init__ has no public names or imports.")
        return out
    out.append(f"  docstring: {_opening(record)}")
    named = kinds(record)
    out.append(f"  public names: {len(named)}")
    out += [f"    {n}: {kind}" for n, kind in named]
    out.append(f"  imports: {_listed(list(record.get('imports', [])), 'no internal imports')}")
    out.append(
        f"  imported by: {_listed(list(record.get('imported_by', [])), 'no internal importers')}"
    )
    out.append(f"  external: {_listed(list(record.get('external', [])), 'none')}")
    total, primary = int(record.get("tests_total", 0)), int(record.get("tests_primary", 0))
    out.append(
        f"  tests: {total} tests import the module ({primary} in a test file with the module name)"
    )
    return out


def names(facts: dict[str, Any], name: str) -> list[str]:
    """This function gives the public names and kinds of one module in source order."""
    record = _record(facts, name)
    named = kinds(record)
    out = [f"{name}: {_plural(len(named), 'public name')}"]
    out += [f"  {n}: {kind}" for n, kind in named]
    return out


def entry_points(facts: dict[str, Any]) -> list[str]:
    """This function gives entry point names and their source targets."""
    points: list[dict[str, str]] = facts.get("entry_points", [])
    out = [
        (
            f"entry points: {len(points)}. A sequence specifies each applicable entry "
            f"point. The target is a console-script function or a subcommand script."
        )
    ]
    for p in points:
        target = f", target {p['target']}" if p.get("target") else ""
        out.append(f"  {entry_label(p)}: {p['module']}{target}")
    return out


def external(facts: dict[str, Any]) -> list[str]:
    """This function gives external imports and the modules that use them."""
    components: dict[str, Any] = facts.get("components", {})
    by_import: dict[str, list[str]] = {}
    for name in sorted(components):
        for imported in components[name].get("external", []):
            by_import.setdefault(imported, []).append(name)
    out = [f"external imports: {len(by_import)}. The model sdk diagnostic uses these imports."]
    out += [f"  {imported}: {', '.join(users)}" for imported, users in sorted(by_import.items())]
    return out


def imports(facts: dict[str, Any], name: str) -> list[str]:
    """This function gives internal imports to and from one module."""
    record = _record(facts, name)
    uses: dict[str, list[str]] = record.get("uses", {})
    out = [f"{name} imports {len(uses)} modules of the package"]
    for target, taken_names in sorted(uses.items()):
        taken = "all of the module" if taken_names == ["*"] else ", ".join(taken_names)
        out.append(f"  {target} ({taken})")
    importers: list[str] = record.get("imported_by", [])
    out.append(f"{len(importers)} modules of the package import {name}")
    out += [f"  {m}" for m in importers]
    return out


VIEWS = (
    "views: Use --modules for module summaries, --docstrings for opening "
    "sentences, --module NAME for a module record, and --names NAME for public "
    "names. Use --entry-points for entry point targets, --external for external "
    "imports, and --imports NAME for internal imports."
)


def overview(summary: list[str]) -> list[str]:
    """This function gives the extraction summary and available facts views."""
    return [*summary, VIEWS]
