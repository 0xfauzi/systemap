"""The suggestion command gives possible component groups from the source facts.

The initial groups use packages with multiple modules. Imports across groups show
possible flows. The maintainer must examine the grouping against source tasks. The
command also identifies possible nested maps from component and module counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from systemap import nest
from systemap.extract import empty_markers, is_empty_marker
from systemap.model import claimed

# Past this many modules a proposal is more than one thing a reader would
# name; the skill's target is three to ten.
SPLIT_ABOVE = 10

HEADER = (
    "suggest: These groups must have a source review.",
    (
        "  The package structure gives one group for each package with two or more "
        "modules. The import graph gives connections between groups. If a group has "
        "two tasks, divide it. If two groups have one task, combine them. The "
        "suggested size is three to ten modules per component, or N/10 to N/3 "
        "components for N modules."
    ),
)


@dataclass(frozen=True)
class Proposal:
    """This record contains a proposed component ID, package, and modules."""

    id: str
    package: str
    modules: tuple[str, ...]


def package_of(module: str, record: dict[str, Any]) -> str:
    """This function selects the module parent package, or the module itself for
    __init__.py.
    """
    if str(record.get("file", "")).endswith("__init__.py"):
        return module
    head, _, _ = module.rpartition(".")
    return head or module


def camel(dotted: str, whole: bool = False) -> str:
    """This function converts dotted name segments to CamelCase, with an optional
    package-root segment.
    """
    parts = dotted.split(".")
    segments = parts if whole else (parts[1:] or parts)
    return "".join(
        "".join(word[:1].upper() + word[1:] for word in re.split(r"[_\W]+", seg) if word)
        for seg in segments
    )


def proposals(facts: dict[str, Any]) -> tuple[list[Proposal], list[str]]:
    """This function gives groups for packages with multiple modules and a separate list of
    isolated modules.
    """
    components: dict[str, Any] = facts.get("components", {})
    by_package: dict[str, list[str]] = {}
    for module in sorted(components):
        record = components[module]
        if is_empty_marker(record):
            continue
        by_package.setdefault(package_of(module, record), []).append(module)
    ids: dict[str, str] = {}
    short = {pkg: camel(pkg) for pkg in by_package}
    counts: dict[str, int] = {}
    for name in short.values():
        counts[name] = counts.get(name, 0) + 1
    for pkg, name in short.items():
        # Two packages that shorten to one id keep their whole path.
        ids[pkg] = name if counts[name] == 1 else camel(pkg, whole=True)
    out: list[Proposal] = []
    alone: list[str] = []
    for pkg in sorted(by_package):
        modules = by_package[pkg]
        if len(modules) >= 2:
            out.append(Proposal(ids[pkg], pkg, tuple(modules)))
        else:
            alone.extend(modules)
    return out, alone


def crossings(facts: dict[str, Any], groups: list[Proposal]) -> list[tuple[str, str, list[str]]]:
    """This function gives import connections across proposal pairs."""
    components: dict[str, Any] = facts.get("components", {})
    owner = {m: p.id for p in groups for m in p.modules}
    found: dict[tuple[str, str], list[str]] = {}
    for module in sorted(owner):
        for target in sorted(components.get(module, {}).get("uses", {})):
            src, dst = owner[module], owner.get(target, "")
            if dst and dst != src:
                found.setdefault((src, dst), []).append(f"{module} -> {target}")
    return [(src, dst, imports) for (src, dst), imports in sorted(found.items())]


def lines(facts: dict[str, Any]) -> list[str]:
    """This function formats the component-group suggestions."""
    groups, alone = proposals(facts)
    markers = empty_markers(facts)
    total = len(facts.get("components", {}))
    out = list(HEADER)
    out.append(
        f"proposals: {len(groups)}, from {total} modules ({len(alone)} modules are "
        f"alone in their package, {len(markers)} empty package markers are omitted)"
    )
    for p in groups:
        out.append(f"  {p.id} ({p.package}): {len(p.modules)} modules: {', '.join(p.modules)}")
        if len(p.modules) > SPLIT_ABOVE:
            out.append(f"    more than {SPLIT_ABOVE} modules: Divide the group by task.")
    if alone:
        out.append(
            f"These modules are alone in their package. Put them in a related component: "
            f"{', '.join(alone)}"
        )
    between = crossings(facts, groups)
    out.append(f"crossing imports between proposals: {len(between)} pairs")
    for src, dst, imports in between:
        shown = ", ".join(imports[:3]) + (
            f" and {len(imports) - 3} more" if len(imports) > 3 else ""
        )
        out.append(f"  {src} -> {dst}: {len(imports)} ({shown})")
    return out


def nesting_lines(tree: nest.Tree, facts: dict[str, Any]) -> list[str]:
    """This function identifies maps or components above the configured size limits.

    The largest module groups give possible nested-map components. A nested map must
    contain the same modules as its parent component.
    """
    components: dict[str, Any] = facts.get("components", {})
    out: list[str] = []
    for m in tree.maps:
        name = m.id or "the top map"
        held = {
            c.id: len(claimed(c, components))
            for c in m.model.components
            if c.kind != "actor" and not c.opens
        }
        ranked = sorted(held, key=lambda cid: (-held[cid], cid))
        n = len(m.model.components)
        if n > nest.CARDS_PER_MAP:
            candidates = [cid for cid in ranked if held[cid] > nest.MODULES_PER_CARD] or ranked[:5]
            out.append(
                f"nesting: {name} has {n} components, more than {nest.CARDS_PER_MAP}. A nested "
                f"map can reduce the component count. Open a map in a component with many "
                f'modules (set map="map/<card>.py". Use the same module set in the nested map):'
            )
            out += [f"  {cid}: {held[cid]} modules" for cid in candidates]
            continue
        wide = [cid for cid in ranked if held[cid] > nest.MODULES_PER_CARD]
        if wide:
            out.append(
                f"nesting: {name} has {n} components: "
                + ", ".join(f"{cid} ({held[cid]} modules)" for cid in wide)
                + (
                    f" more than {nest.MODULES_PER_CARD} modules: Divide the component, or open a "
                    f"map inside it."
                )
            )
    if not out:
        out.append(
            f"nesting: no map has more than {nest.CARDS_PER_MAP} components and no "
            f"component has more than {nest.MODULES_PER_CARD} modules. No nested map is "
            f"necessary."
        )
    return out
