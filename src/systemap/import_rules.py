"""Examine the import rules of a model against the import facts.

Each rule gets one result: `pass`, `fail`, or `unknown`.
`fail` gives each resolved import (source module, target module) that does not obey the rule.
`unknown` gives each module of the rule whose imports the facts do not give completely.
The examination reads only facts with the same meaning for each language:
the component of each module from the model, the resolved imports in `uses`, and the
`completeness` record. External packages are not in `uses`, and the rules do not examine them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from systemap import explain, nest
from systemap.model import ImportRule, Model, claimed, import_rule_problems, source_parsed

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

# The causes of an unknown result. A cause is a stable identifier for a program.
NO_FACTS = "no_facts"
NO_READ_STATE = "no_read_state"
NOT_PARSED = "not_parsed"
UNRESOLVED_NOT_KNOWN = "unresolved_not_known"
UNRESOLVED = "unresolved_imports"
NO_COMPONENT = "no_component"

Import = tuple[str, str]


@dataclass(frozen=True)
class Gap:
    """A module whose imports can include an import against the rule that the facts do not give."""

    module: str
    cause: str
    detail: str


@dataclass(frozen=True)
class Outcome:
    """The result of one rule, with the imports against it and the modules with unknown imports."""

    rule: ImportRule
    result: str
    imports: tuple[Import, ...] = ()
    gaps: tuple[Gap, ...] = ()


@dataclass(frozen=True)
class MapOutcomes:
    """The rule results of one map in the map tree."""

    map_id: str
    prefix: str
    rel: str
    outcomes: tuple[Outcome, ...]


def evaluate(model: Model, facts: Mapping[str, Any]) -> list[Outcome]:
    """Give the result of each rule of the model, in model order.

    A model with an incorrect rule gives no results. The model check gives its problems.
    """
    if import_rule_problems(model):
        return []
    records: Mapping[str, Any] = facts.get("components") or {}
    owners: dict[str, set[str]] = defaultdict(set)
    for component in model.components:
        for module in claimed(component, records):
            owners[module].add(component.id)
    return [_evaluate(rule, model, records, owners) for rule in model.import_rules]


def run_tree(tree: nest.Tree, facts: Mapping[str, Any]) -> list[MapOutcomes]:
    """Give the rule results of each map in tree order."""
    return [MapOutcomes(m.id, m.prefix, m.rel, tuple(evaluate(m.model, facts))) for m in tree.maps]


def _evaluate(
    rule: ImportRule,
    model: Model,
    records: Mapping[str, Any],
    owners: Mapping[str, set[str]],
) -> Outcome:
    if not records:
        return Outcome(rule, UNKNOWN, gaps=(Gap("", NO_FACTS, "No facts are available."),))
    src = set(rule.src) or (model.ids if rule.kind == "forbid_cycle" else set())
    modules = sorted(m for m, owner in owners.items() if owner & src)
    gaps = [gap for m in modules for gap in _gaps(m, records[m])]
    found, unowned = _KINDS[rule.kind](rule, modules, records, owners, src)
    gaps += unowned
    result = FAIL if found else UNKNOWN if gaps else PASS
    return Outcome(rule, result, tuple(found), tuple(gaps))


def _uses(modules: Iterable[str], records: Mapping[str, Any]) -> list[Import]:
    return [(m, t) for m in modules for t in sorted(records[m].get("uses", {})) if t != m]


def _gaps(module: str, record: Mapping[str, Any]) -> list[Gap]:
    """Give the causes for which the facts can omit an import of the module."""
    state = record.get("completeness")
    if not isinstance(state, Mapping):
        return [Gap(module, NO_READ_STATE, "The facts do not give the read condition.")]
    if not source_parsed(record):
        where = f" (line {state.get('line')})" if state.get("line") else ""
        return [Gap(module, NOT_PARSED, f"The extractor could not parse all of the source{where}.")]
    unresolved = state.get("unresolved_imports")
    if unresolved is None:
        return [Gap(module, UNRESOLVED_NOT_KNOWN, "The unresolved imports are not known.")]
    if unresolved:
        names = ", ".join(str(name) for name in unresolved)
        return [Gap(module, UNRESOLVED, f"The module has unresolved imports: {names}.")]
    return []


def _forbidden(
    rule: ImportRule,
    modules: list[str],
    records: Mapping[str, Any],
    owners: Mapping[str, set[str]],
    src: set[str],
) -> tuple[list[Import], list[Gap]]:
    """Give the imports of modules of the `dst` components."""
    dst = set(rule.dst)
    return [(m, t) for m, t in _uses(modules, records) if owners.get(t, set()) & dst], []


def _not_allowed(
    rule: ImportRule,
    modules: list[str],
    records: Mapping[str, Any],
    owners: Mapping[str, set[str]],
    src: set[str],
) -> tuple[list[Import], list[Gap]]:
    """Give the imports of modules of other components, and the imports of modules with no
    component. The rule cannot give a result for a module with no component."""
    allowed = src | set(rule.dst)
    found: list[Import] = []
    unowned: list[Gap] = []
    for m, t in _uses(modules, records):
        owner = owners.get(t, set())
        if not owner:
            unowned.append(Gap(m, NO_COMPONENT, f"The module imports {t}, which has no component."))
        elif not owner & allowed:
            found.append((m, t))
    return found, unowned


def _cycles(
    rule: ImportRule,
    modules: list[str],
    records: Mapping[str, Any],
    owners: Mapping[str, set[str]],
    selected: set[str],
) -> tuple[list[Import], list[Gap]]:
    """Give the imports between selected components that are in a cycle of components.

    The graph has only the imports between modules of the selected components.
    An import from component A to component B is in a cycle if B can get to A.
    """
    edges: dict[tuple[str, str], list[Import]] = defaultdict(list)
    for m, t in _uses(modules, records):
        for a in owners[m] & selected:
            for b in owners.get(t, set()) & selected - {a}:
                edges[(a, b)].append((m, t))
    after: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        after[a].add(b)
    found: set[Import] = set()
    for (a, b), imports in edges.items():
        if a in _reach(b, after):
            found.update(imports)
    return sorted(found), []


Examine = Callable[
    [ImportRule, list[str], Mapping[str, Any], Mapping[str, set[str]], set[str]],
    tuple[list[Import], list[Gap]],
]
_KINDS: dict[str, Examine] = {
    "forbid_import": _forbidden,
    "allow_imports": _not_allowed,
    "forbid_cycle": _cycles,
}


def _reach(start: str, after: Mapping[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    todo = [start]
    while todo:
        for nxt in after.get(todo.pop(), set()) - seen:
            seen.add(nxt)
            todo.append(nxt)
    return seen


# ---- results for a person and for a program ------------------------------------------


def ok(tree: Iterable[MapOutcomes], unknown: str) -> bool:
    """True when no rule has the result fail, and no rule is unknown under `unknown = "fail"`."""
    bad = {FAIL, UNKNOWN} if unknown == "fail" else {FAIL}
    return not any(o.result in bad for m in tree for o in m.outcomes)


def _label(rule: ImportRule) -> str:
    return f"{rule.id} ({rule.kind})"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'s' if n != 1 else ''}"


def _counts(outcomes: Iterable[Outcome]) -> dict[str, int]:
    found = [o.result for o in outcomes]
    return {state: found.count(state) for state in (FAIL, UNKNOWN, PASS)}


def report(tree: Iterable[MapOutcomes], unknown: str, teach: bool = True) -> list[str]:
    """Give the rule report lines for each map that has rules.

    The `teach` option adds the explanation rows under each group of results.
    """
    out: list[str] = []
    for m in tree:
        out += [m.prefix + line for line in _map_report(m, unknown, teach)]
    return out


def _map_report(m: MapOutcomes, unknown: str, teach: bool) -> list[str]:
    if not m.outcomes:
        return []
    counts = _counts(m.outcomes)
    head = f"import rules: {_plural(len(m.outcomes), 'rule')}, " + ", ".join(
        f"{n} {state}" for state, n in counts.items()
    )
    return [head, *_failed(m, teach), *_unknown(m, unknown, teach)]


def _failed(m: MapOutcomes, teach: bool) -> list[str]:
    failed = [o for o in m.outcomes if o.result == FAIL]
    if not failed:
        return []
    return [
        f"rule fail: {_plural(len(failed), 'rule')}",
        *(explain.rows("rule fail") if teach else []),
        *(f"  {_label(o.rule)}: {src} imports {dst}" for o in failed for src, dst in o.imports),
        f"  fix: Remove each listed import from the source, or change the rule in {m.rel}.",
    ]


def _unknown(m: MapOutcomes, unknown: str, teach: bool) -> list[str]:
    found = [o for o in m.outcomes if o.result == UNKNOWN]
    if not found:
        return []
    effect = "This result causes exit 1" if unknown == "fail" else "This result is a warning"
    return [
        f"rule unknown: {_plural(len(found), 'rule')}. {effect} "
        f'with [rules] unknown = "{unknown}".',
        *(explain.rows("rule unknown") if teach else []),
        *(f"  {_label(o.rule)}: {_gap_text(g)}" for o in found for g in o.gaps),
        "  fix: Correct the listed source or imports. Then use systemap refresh.",
    ]


def _gap_text(gap: Gap) -> str:
    return f"{gap.module}: {gap.detail}" if gap.module else gap.detail


def payload(tree: Iterable[MapOutcomes], unknown: str, problems: list[str]) -> dict[str, Any]:
    """Give the rule results as one JSON object for a program."""
    maps = list(tree)
    outcomes = [o for m in maps for o in m.outcomes]
    return {
        "ok": not problems and ok(maps, unknown),
        "unknown_policy": unknown,
        "problems": problems,
        "counts": _counts(outcomes),
        "rules": [_record(m.map_id, o) for m in maps for o in m.outcomes],
    }


def _record(map_id: str, outcome: Outcome) -> dict[str, Any]:
    rule = outcome.rule
    return {
        "map": map_id,
        "id": rule.id,
        "kind": rule.kind,
        "src": list(rule.src),
        "dst": list(rule.dst),
        "reason": rule.reason,
        "invariant": rule.invariant,
        "result": outcome.result,
        "imports": [{"source": src, "target": dst} for src, dst in outcome.imports],
        "unknown": [
            {"module": g.module, "cause": g.cause, "detail": g.detail} for g in outcome.gaps
        ],
    }
