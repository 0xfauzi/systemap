"""The crossing import rule finds two components where one imports the other and no flow
connects them.

An import is a static fact of the source. A flow is a claim of the map. The rule uses
source facts and an owner table, so that the delta can use the same rule at a different
commit. The judgement report, the delta and the part plan use these functions.
"""

from __future__ import annotations

import re
from typing import Any

from systemap import import_forms, nest
from systemap.evidence import owners
from systemap.model import Model

Pair = tuple[str, str]


def crossing_pairs(
    components: dict[str, Any], owner: dict[str, str], runtime_only: bool = True
) -> dict[Pair, list[tuple[str, str]]]:
    """This function indexes module imports across distinct component pairs.

    It uses source facts and an owner table so the delta can use the same rule at
    another commit. With `runtime_only`, a component pair whose imports all operate only
    for type checks is not in the result (`import_forms.runtime`). A pair in the result
    keeps all its imports, also the imports for type checks, because the evidence digest
    of an exact answer contains them.
    """
    out: dict[Pair, list[tuple[str, str]]] = {}
    for module in sorted(components):
        p = owner.get(module)
        if not p:
            continue
        for target in sorted(components[module].get("uses", {})):
            q = owner.get(target)
            if q and q != p:
                out.setdefault((p, q), []).append((module, target))
    if not runtime_only:
        return out
    return {
        pair: edges
        for pair, edges in out.items()
        if any(import_forms.runtime(components[m], t) for m, t in edges)
    }


def runtime_targets(record: dict[str, Any]) -> list[str]:
    """Give the sorted targets of the imports of a module record that can operate at run
    time. The delta and the `boundary import` rule ignore an import only for type checks."""
    return [t for t in sorted(record.get("uses", {})) if import_forms.runtime(record, t)]


def crossing_line(p: str, q: str) -> str:
    """This function gives one diagnostic for a component pair.

    The line contains no count, because a count can change while the finding stays the
    same. `crossing_counts` gives the count for the row below the line.
    """
    return f"crossing import: {p} imports {q} and no flow connects them"


def crossing_imports(model: Model, facts: dict[str, Any]) -> dict[Pair, list[tuple[str, str]]]:
    """This function gives component pairs with an import connection and no flow
    connection.
    """
    components = facts.get("components", {})
    joined = {frozenset(f.edge) for f in model.flows}
    return {
        pair: imports
        for pair, imports in crossing_pairs(components, owners(model, facts)).items()
        if frozenset(pair) not in joined
    }


def crossing_imports_without_flow(model: Model, facts: dict[str, Any]) -> list[str]:
    """This function gives one diagnostic for each ordered component pair with imports but
    no flow. The verbose detail lists these imports.
    """
    return [crossing_line(p, q) for p, q in crossing_imports(model, facts)]


def crossing_detail(model: Model, facts: dict[str, Any], prefix: str = "") -> dict[str, list[str]]:
    """This function indexes imports by their full printed crossing-import diagnostic.

    After the import rows, the rows give each import that operates only in a function
    body, and each import by a string value in a module of the source component. If the
    language adapter does not find imports for type checks, a row tells it."""
    components = facts.get("components", {})
    owner = owners(model, facts)
    details = facts.get("import_details")
    no_type = isinstance(details, list) and import_forms.TYPE not in details
    out: dict[str, list[str]] = {}
    for (p, q), imports in crossing_imports(model, facts).items():
        rows = [f"{m} imports {t}" for m, t in imports]
        rows += [
            f"{m} imports {t} only in a function body."
            for m, t in imports
            if import_forms.deferred(components.get(m), t)
        ]
        rows += _dynamic_rows(components, owner, p)
        out[prefix + crossing_line(p, q)] = rows + ([NO_TYPE_ROW] if no_type else [])
    return out


NO_TYPE_ROW = (
    "The language adapter does not find imports for type checks. Thus each import counts "
    "as an import at run time."
)


def _dynamic_rows(components: dict[str, Any], owner: dict[str, str], p: str) -> list[str]:
    """Give one row for each import by a string value in a module of the component `p`."""
    return [
        f"{module} imports a module by a string value at line {record.get('line')}: "
        f"{record.get('call')}({record.get('text') or 'a value'})."
        for module in sorted(components)
        if owner.get(module) == p
        for record in import_forms.dynamic_records(components[module])
    ]


def crossing_counts(tree: nest.Tree, facts: dict[str, Any]) -> dict[str, int]:
    """This function gives the count of the modules of the source component that import
    the destination component, for each crossing-import line of all maps."""
    return {
        m.prefix + crossing_line(p, q): len({module for module, _target in imports})
        for m in tree.reported
        for (p, q), imports in crossing_imports(m.model, facts).items()
    }


def crossing_detail_tree(tree: nest.Tree, facts: dict[str, Any]) -> dict[str, list[str]]:
    """This function gives crossing-import detail for all maps with their diagnostic
    prefixes.
    """
    out: dict[str, list[str]] = {}
    for m in tree.reported:
        out.update(crossing_detail(m.model, facts, m.prefix))
    return out


CROSSING_LINE = re.compile(r"^crossing import: (\S+) imports (\S+) and no flow connects")
