"""Readable views of the facts file: what `systemap facts` prints.

The facts file runs to hundreds of kilobytes on a real tree, and an agent
that reads it whole spends its context on JSON it will not use. These
views are what the skill's first step reads instead, one question each:

    --modules          one line per module: the first sentence of its
                       docstring, then its public names, imports and
                       tests counted
    --docstrings       one line per module: the first sentence of its
                       docstring, and nothing else
    --module NAME      one module's record, rendered: its docstring, its
                       public names with their kinds, what it imports,
                       what imports it, its third-party imports, and how
                       many tests import it (never their names)
    --names NAME       one module's public names with their kinds, a
                       re-export marked with the module that defines it
    --entry-points     where a run can start, the way a person names it,
                       each with its target: the function a console
                       script calls, or the script a subcommand belongs to
    --external         every third-party import, and the modules that use it
    --imports NAME     what one module imports, and what imports it

Nothing here is a fact the file does not hold; every line is read out of
the same records `systemap check` reads. No view prints a test's name:
the map says what, never how much, and a test name is a how-much.
"""

from __future__ import annotations

import difflib
import re
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


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def first_sentence(text: str) -> str:
    """The first sentence of a docstring's opening paragraph, or empty."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    return re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]


NO_DOCSTRING = "no docstring"
EMPTY_MARKER = "empty package marker"


def _opening(record: dict[str, Any]) -> str:
    """What a module's line says about it: its first sentence, or that it has none."""
    return first_sentence(record.get("docstring", "")) or NO_DOCSTRING


def kinds(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Every public name with its kind, in source order; a re-export says whence.

    A facts file from before `names` was recorded offers its functions,
    classes, errors and constants, which is what it has.
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
    """One line per module, in name order: the first sentence, then the counts."""
    components: dict[str, Any] = facts.get("components", {})
    out = [
        f"modules: {len(components)}; each with the first sentence of its docstring, "
        "then its public names, imports and tests counted"
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
    """One line per module: the first sentence of its docstring."""
    components: dict[str, Any] = facts.get("components", {})
    with_one = sum(1 for r in components.values() if first_sentence(r.get("docstring", "")))
    out = [
        f"docstrings: {with_one} of {len(components)} modules have one; the first sentence of each"
    ]
    for name in sorted(components):
        record = components[name]
        out.append(f"  {name}: {EMPTY_MARKER if is_empty_marker(record) else _opening(record)}")
    return out


def _listed(items: list[str], none: str) -> str:
    return ", ".join(items) if items else none


def module(facts: dict[str, Any], name: str) -> list[str]:
    """One module's record, rendered for a reader; never a test's name."""
    record = _record(facts, name)
    out = [f"{name} ({record.get('file', '')})"]
    if is_empty_marker(record):
        out.append(f"  {EMPTY_MARKER}: an __init__ with no public names and no imports")
        return out
    out.append(f"  docstring: {_opening(record)}")
    named = kinds(record)
    out.append(f"  public names: {len(named)}")
    out += [f"    {n}: {kind}" for n, kind in named]
    out.append(f"  imports: {_listed(list(record.get('imports', [])), 'nothing from the package')}")
    out.append(
        f"  imported by: {_listed(list(record.get('imported_by', [])), 'nothing in the package')}"
    )
    out.append(f"  external: {_listed(list(record.get('external', [])), 'none')}")
    total, primary = int(record.get("tests_total", 0)), int(record.get("tests_primary", 0))
    out.append(f"  tests: {total} import it ({primary} in a file named after it)")
    return out


def names(facts: dict[str, Any], name: str) -> list[str]:
    """One module's public names with their kinds, in source order."""
    record = _record(facts, name)
    named = kinds(record)
    out = [f"{name}: {_plural(len(named), 'public name')}"]
    out += [f"  {n}: {kind}" for n, kind in named]
    return out


def entry_points(facts: dict[str, Any]) -> list[str]:
    """Where a run can start, each with its target beside it."""
    points: list[dict[str, str]] = facts.get("entry_points", [])
    out = [
        f"entry points: {len(points)}; a journey names each that matters; the target is the "
        "function a console script calls, or the script a subcommand belongs to"
    ]
    for p in points:
        target = f", target {p['target']}" if p.get("target") else ""
        out.append(f"  {entry_label(p)}: {p['module']}{target}")
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
    for target, taken_names in sorted(uses.items()):
        taken = "the whole module" if taken_names == ["*"] else ", ".join(taken_names)
        out.append(f"  {target} ({taken})")
    importers: list[str] = record.get("imported_by", [])
    out.append(f"{name} is imported by {len(importers)} modules of the package")
    out += [f"  {m}" for m in importers]
    return out


VIEWS = (
    "views: --modules (one line per module: first sentence, counts), --docstrings (first "
    "sentence only), --module NAME (its record, rendered), --names NAME (its public names "
    "with kinds), --entry-points (with targets), --external, --imports NAME (what it "
    "imports and what imports it)"
)


def overview(summary: list[str]) -> list[str]:
    """What `systemap facts` prints with no option: the extract summary and the views."""
    return [*summary, VIEWS]
