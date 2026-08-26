"""A first grouping to argue with: what `systemap suggest` prints.

Nothing says how many components a map should have, and a first draft
with no starting point tends to a card per module. This reads the facts
alone and proposes one card per package with two or more modules, from
the package structure, and lists the imports between the proposals, from
the import graph. It is a starting point, never the answer, and its
header says so: a component is what a reader would point at and name,
and a package is only where the files happen to sit. A proposal that
does two things is split, two that do one are folded, and the judgement
lines push from both sides once the model exists.

Empty package markers are left out, as the coverage rule leaves them
out. A module alone in its package is listed to fold into a neighbour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from systemap.extract import empty_markers, is_empty_marker

# Past this many modules a proposal is more than one thing a reader would
# name; the skill's target is three to ten.
SPLIT_ABOVE = 10

HEADER = (
    "suggest: a first grouping to argue with, never the answer",
    "  one proposal per package with two or more modules, from the package structure; "
    "the imports between proposals, from the import graph. A component is what a reader "
    "would point at and name: split a proposal that does two things, fold two that do "
    "one. A component usually holds three to ten modules; a repository of N modules "
    "usually lands between N/10 and N/3 cards.",
)


@dataclass(frozen=True)
class Proposal:
    """One proposed card: an id to argue with, the package, its modules."""

    id: str
    package: str
    modules: tuple[str, ...]


def package_of(module: str, record: dict[str, Any]) -> str:
    """The package a module sits in: itself for an `__init__`, else its parent."""
    if str(record.get("file", "")).endswith("__init__.py"):
        return module
    head, _, _ = module.rpartition(".")
    return head or module


def camel(dotted: str, whole: bool = False) -> str:
    """`wharf_server.render.emit` to `RenderEmit`: the segments after the root,
    CamelCased; with `whole`, the root too (`WharfServerRenderEmit`)."""
    parts = dotted.split(".")
    segments = parts if whole else (parts[1:] or parts)
    return "".join(
        "".join(word[:1].upper() + word[1:] for word in re.split(r"[_\W]+", seg) if word)
        for seg in segments
    )


def proposals(facts: dict[str, Any]) -> tuple[list[Proposal], list[str]]:
    """(one proposal per package with two or more modules, the modules alone in theirs)."""
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
    """(from, to, the imports) for every pair of proposals with an import between them."""
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
    """What `systemap suggest` prints."""
    groups, alone = proposals(facts)
    markers = empty_markers(facts)
    total = len(facts.get("components", {}))
    out = list(HEADER)
    out.append(
        f"proposals: {len(groups)}, from {total} modules ({len(alone)} alone in their package, "
        f"{len(markers)} empty package markers left out)"
    )
    for p in groups:
        out.append(f"  {p.id} ({p.package}): {len(p.modules)} modules: {', '.join(p.modules)}")
        if len(p.modules) > SPLIT_ABOVE:
            out.append(f"    more than {SPLIT_ABOVE} modules: split it by purpose")
    if alone:
        out.append(f"alone in their package, to fold into a neighbour: {', '.join(alone)}")
    between = crossings(facts, groups)
    out.append(f"crossing imports between proposals: {len(between)} pairs")
    for src, dst, imports in between:
        shown = ", ".join(imports[:3]) + (
            f" and {len(imports) - 3} more" if len(imports) > 3 else ""
        )
        out.append(f"  {src} -> {dst}: {len(imports)} ({shown})")
    return out
