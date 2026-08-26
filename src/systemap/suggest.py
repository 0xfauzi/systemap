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

Once a model exists, `nesting_lines` reads the tree of maps and says
when a map is past forty cards, the point where one canvas stops
working, and names the cards with the most modules as the candidates to
open a map on (`Component.map`); a card whose modules exceed ten is a
candidate on any map.
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


def nesting_lines(tree: nest.Tree, facts: dict[str, Any]) -> list[str]:
    """When to open a map inside a card, read from the tree and the facts.

    A map past `nest.CARDS_PER_MAP` cards is named, with the cards that
    hold the most modules as the candidates to open, most first; on any
    map a card whose modules exceed `nest.MODULES_PER_CARD` is a
    candidate too. A card that already opens a map is not proposed
    again. With nothing past either line, one line says so.
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
                f"nesting: {name} holds {n} cards, past {nest.CARDS_PER_MAP}; one canvas "
                "stops working there. Open a map inside the cards with the most modules "
                '(map="map/<card>.py" on the card; its cards claim exactly the card\'s modules):'
            )
            out += [f"  {cid}: {held[cid]} modules" for cid in candidates]
            continue
        wide = [cid for cid in ranked if held[cid] > nest.MODULES_PER_CARD]
        if wide:
            out.append(
                f"nesting: {name} holds {n} cards; "
                + ", ".join(f"{cid} ({held[cid]} modules)" for cid in wide)
                + f" past {nest.MODULES_PER_CARD} modules: split the card, or open a map "
                "inside it"
            )
    if not out:
        out.append(
            f"nesting: no map is past {nest.CARDS_PER_MAP} cards and no card holds more than "
            f"{nest.MODULES_PER_CARD} modules; nothing to open"
        )
    return out
