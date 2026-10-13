"""Find the source lines where the modules of two components meet, for `decision flow`.

The `call_sites` fact of each module gives the local names that import statements make.
It also gives the local names that get their value from an imported name. For each
local name, it gives the lines that use the name.
This module reads only that fact, the module records, and the source lines that the
fact names. It does not read source syntax.

The context has these lines, in this sequence, until it has 60 lines:

1. The import lines and the lines that use an imported name.
2. The lines that read a property of a local name that gets its value from an imported
   name, such as `ledger.record(parts)` after `ledger = Ledger()`.
3. The line of the function or method that contains each of these lines.

Then the context gives at most 12 lines from the facts of the target modules: the
signature of each imported function, class, or method that a selected line uses, and
the first sentence of the module description. If the facts do not give these lines,
the context has only the source lines.

`bench/jev/flow_context.py` and `bench/jev/call_site_context.py` measured this selection.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import repo_files
from systemap.facts import first_sentence
from systemap.language import RepositoryAdapter

WHOLE = "*"
DEFAULT = "default"
IMPORT = "import"
LINES = 60
TARGET_LINES = 12
WIDTH = 160


@dataclass
class Side:
    """One module at one end of a flow, with its call sites for the other end."""

    module: str
    lines: list[str]
    sites: list[dict[str, Any]]


Pick = tuple[int, int]  # (side index, line number)


def _source(root: Path, facts: dict[str, Any], module: str) -> list[str] | None:
    try:
        return repo_files.read_text(root, str(facts["components"][module]["file"])).splitlines()
    except (OSError, UnicodeDecodeError, KeyError):
        return None


def _side(root: Path, facts: dict[str, Any], module: str, others: list[str]) -> Side | None:
    """Give the side of one module. Raise LookupError if its fact is not known."""
    record = facts["components"][module]
    uses = record.get("uses", {})
    wanted = {b for b in others if b in uses}
    if not wanted:
        return None
    sites = record.get("call_sites")
    if sites is None:
        raise LookupError(module)
    sites = [s for s in sites if s["target"] in wanted]
    if not sites:
        return None
    text = _source(root, facts, module)
    if text is None:
        raise LookupError(module)
    return Side(module, text, sites)


# A selected line: the line, its call site, the property that it reads, and the line of
# the function that contains it (0 for none).
Item = tuple[Pick, dict[str, Any], str, int]


def _items(k: int, site: dict[str, Any]) -> list[Item]:
    """An import gives its line and each use. A value gives each use that reads a property."""
    uses = [((k, line), site, member, function) for line, function, member in site["uses"]]
    if site["bound"] == IMPORT:
        return [((k, site["line"]), site, "", 0), *uses]
    return [use for use in uses if use[2]]


def _tiers(sides: list[Side]) -> list[list[Item]]:
    """Give the import tier, the property tier, and the function tier."""
    found = [
        (site["bound"] == IMPORT, item)
        for k, side in enumerate(sides)
        for site in side.sites
        for item in _items(k, site)
    ]
    first = sorted((item for direct, item in found if direct), key=lambda item: item[0])
    second = sorted((item for direct, item in found if not direct), key=lambda item: item[0])
    functions: list[Item] = [
        ((pick[0], function), site, "", 0)
        for pick, site, _member, function in first + second
        if function and function != pick[1]
    ]
    return [first, second, functions]


def _fill(sides: list[Side], tiers: list[list[Item]]) -> list[Pick]:
    """Take the lines tier by tier until the limit. Blank lines do not count."""
    chosen: list[Pick] = []
    for (k, line), _site, _member, _function in (item for tier in tiers for item in tier):
        if len(chosen) >= LINES:
            break
        text = sides[k].lines
        if (k, line) not in chosen and 0 < line <= len(text) and text[line - 1].strip():
            chosen.append((k, line))
    return chosen


def _used(tiers: list[list[Item]], chosen: set[Pick]) -> dict[str, set[str]]:
    """Give, for each target module, the names that the chosen lines use."""
    out: dict[str, set[str]] = {}
    for pick, site, member, _function in (item for tier in tiers[:2] for item in tier):
        if pick in chosen:
            names = out.setdefault(site["target"], set())
            names |= {site["name"], member} - {WHOLE, DEFAULT, ""}
    return out


def _signatures(record: dict[str, Any], names: set[str], language: RepositoryAdapter) -> list[str]:
    out = [f["signature"] for f in record.get("functions", []) if f["name"] in names]
    for c in record.get("classes", []) + record.get("errors", []):
        if c["name"] not in names:
            continue
        methods = [m for m in c.get("methods", []) if language.method_name(m) in names]
        out.append(f"class {c['name']}" + (": " + "; ".join(methods[:2]) if methods else ""))
    for t in record.get("types", []):
        if t["name"] not in names:
            continue
        methods = [m for m in t.get("methods", []) if language.method_name(m) in names]
        head = f"{t.get('category', 'type').replace('_', ' ')} {t['name']}"
        out.append(head + (": " + "; ".join(methods[:2]) if methods else ""))
    return out


def _target_lines(
    facts: dict[str, Any], used: dict[str, set[str]], language: RepositoryAdapter
) -> list[str]:
    defs: list[str] = []
    docs: list[str] = []
    for target, names in sorted(used.items()):
        record = facts["components"].get(target, {})
        defs += [f"{target} defines: {s}"[:WIDTH] for s in _signatures(record, names, language)]
        doc = first_sentence(record.get("docstring", ""))
        if doc:
            docs.append(f"{target} docstring: {doc}"[:WIDTH])
    return (defs + docs)[:TARGET_LINES]


def _sides(
    root: Path, facts: dict[str, Any], mods: dict[str, list[str]], cards: Iterable[str]
) -> list[Side]:
    src, dst = cards
    out: list[Side] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in mods.get(a_card, []):
            side = _side(root, facts, a, mods.get(b_card, []))
            if side is not None:
                out.append(side)
    return out


def code_between(
    root: Path,
    facts: dict[str, Any],
    mods: dict[str, list[str]],
    cards: tuple[str, str],
    language: RepositoryAdapter,
) -> list[str] | None:
    """Give the flow context: at most 60 source lines and 12 lines from the facts.

    The result is None if the `call_sites` fact or the source of a module that imports
    from the other component is not known. An empty list means that no line uses a name
    from the other component.
    """
    try:
        sides = _sides(root, facts, mods, cards)
    except LookupError:
        return None
    tiers = _tiers(sides)
    chosen = _fill(sides, tiers)
    lines = [
        f"{sides[k].module}:{line}: {sides[k].lines[line - 1].strip()[:WIDTH]}"
        for k, line in sorted(chosen)
    ]
    if not lines:
        return []
    return lines + _target_lines(facts, _used(tiers, set(chosen)), language)
