"""Module roles tell if an import crossing must have a flow.

An import crossing is two components of one map where modules of the first component
import modules of the second component, and no flow connects them. The helper or
handoff code of the imported modules is a judgement that no import rule can calculate.
Thus the unit of the judgement is the imported module:

- A `module use` line names one module that other components import. Its exact answer
  gives the module role of the module: `helper`, `handoff`, or `mixed`.
- A `crossing import` line is open only when its import crossing uses a handoff module
  or a handoff name of a mixed module. An import crossing that uses a module with no
  accepted module role waits. It is not a line, but the `module use` line of the module
  is open. An import crossing that uses only helper code is closed.

The unit of an import is the module that defines the imported name, when the module has
the same component as the imported module (`use_units`). An import of a full module
uses the attribute names of its call-site records when the facts give them. Else the
import uses the full module, with the name `"*"`.

This module reads only facts, the model, and the recorded answers. It reads no language
name. A unit has its line in the deepest map that owns the module (`_line_map`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from systemap import config_answers, import_forms, judgement_evidence, nest
from systemap.config_answers import Answer
from systemap.crossing import crossing_imports, crossing_line, crossing_pairs
from systemap.evidence import owners, ref_module
from systemap.model import Component

KIND = "module use"
LINE = "module use: other components import {} and no flow connects them to its component"
_LINE = re.compile(
    r"^module use: other components import (.+) and no flow connects them to its component$"
)
STAR = "*"
HELPER, HANDOFF, MIXED = "helper", "handoff", "mixed"
OPEN, WAITING, CLOSED = "open", "waiting", "closed"
# The module role of a unit with no accepted answer, and of a unit with a refused answer.
NONE, REFUSED = "none", "refused"
# The record keys of a module record that give its names (`provided`).
_NAME_KEYS = ("names", "functions", "classes", "constants", "types")


def line_module(line: str) -> str | None:
    """Give the module of a `module use` line without a map prefix, or None."""
    found = _LINE.match(line)
    return found[1] if found else None


def module_line(module: str) -> str:
    """Give the `module use` line of a module, without a map prefix."""
    return LINE.format(module)


def bare(item: str) -> str:
    """Remove the map prefix of a `module use` item."""
    head = f"{KIND}: "
    if item.startswith(head):
        return item
    _prefix, sep, rest = item.partition(": ")
    return rest if sep and rest.startswith(head) else item


def item_module(item: str) -> str | None:
    """Give the module of a `module use` item, with or without a map prefix, or None."""
    return line_module(bare(item))


# ---- units of one import (section 7.1 of the specification) ----------------------------


class _Names:
    """The names entries of the module records, with one table for each module."""

    def __init__(self, components: Mapping[str, Any]) -> None:
        self.components = components
        self._tables: dict[str, dict[str, Mapping[str, Any]]] = {}

    def entry(self, module: str, name: str) -> Mapping[str, Any] | None:
        """Give the names entry `name` of the module, or None."""
        table = self._tables.get(module)
        if table is None:
            record = self.components.get(module)
            entries = record.get("names", []) if isinstance(record, Mapping) else []
            table = {
                e["name"]: e
                for e in entries
                if isinstance(e, Mapping) and isinstance(e.get("name"), str)
            }
            self._tables[module] = table
        return table.get(name)


def _site_names(site: Mapping[str, Any]) -> set[str] | None:
    """Give the attribute names of one call-site record, or None when they are not known."""
    local = str(site.get("local", ""))
    rows = site.get("uses")
    if "." in local or local == STAR or not isinstance(rows, list) or not rows:
        return None
    found = {str(row[2]) for row in rows if isinstance(row, list | tuple) and len(row) > 2}
    return None if "" in found or not found else found


def star_names(record: Mapping[str, Any], target: str) -> set[str]:
    """Give the call-site names of an import of the full module `target`, or `{"*"}`.

    The names are not known when the adapter gives no call sites, when no call-site
    record is for the import, when the module object has a dotted or a `*` local name,
    when a record has no rows, or when a row uses the module object as a value."""
    sites = record.get("call_sites")
    if not isinstance(sites, list):
        return {STAR}
    found = [
        _site_names(s)
        for s in sites
        if isinstance(s, Mapping)
        and s.get("bound") == "import"
        and s.get("name") == STAR
        and s.get("target") == target
    ]
    if not found or any(names is None for names in found):
        return {STAR}
    return set().union(*(names for names in found if names is not None))


def _resolve(
    names: _Names, owner: Mapping[str, str], target: str, name: str
) -> tuple[str, str, str]:
    """Give the unit, the name in the unit, and a note for one imported name.

    A name that a different module of the same component defines goes to that module,
    with its name there. A name that a module of a different component defines stays on
    `target`, and the note tells it."""
    entry = names.entry(target, name)
    defined = entry.get("defined_in") if entry is not None else None
    if entry is None or not isinstance(defined, str) or defined == target:
        return target, name, ""
    if defined not in names.components:
        return target, name, ""
    if owner.get(defined) == owner.get(target):
        return defined, str(entry.get("defined_as") or name), ""
    other = owner.get(defined) or "no component"
    return target, name, f"{target}:{name} is defined in {defined} ({other})."


def _edge_units(
    names: _Names, owner: Mapping[str, str], module: str, target: str
) -> tuple[dict[str, set[str]], list[str]]:
    """Give the units of one import with their names, and the notes of `target`."""
    record = names.components[module]
    found = set(record.get("uses", {}).get(target) or [STAR])
    if STAR in found:
        found = (found - {STAR}) | star_names(record, target)
    out: dict[str, set[str]] = {}
    notes: list[str] = []
    for name in sorted(found):
        unit, used, note = (
            (target, STAR, "") if name == STAR else _resolve(names, owner, target, name)
        )
        out.setdefault(unit, set()).add(used)
        if note:
            notes.append(note)
    return out, notes


def use_units(
    components: Mapping[str, Any], owner: Mapping[str, str], module: str, target: str
) -> dict[str, set[str]]:
    """Give the units of the import of `target` by `module`, with the names of each unit."""
    return _edge_units(_Names(components), owner, module, target)[0]


def provided(record: Any) -> frozenset[str]:
    """Give the names that the facts of a module define or import."""
    if not isinstance(record, Mapping):
        return frozenset()
    out: set[str] = set()
    for key in _NAME_KEYS:
        for entry in record.get(key) or []:
            if isinstance(entry, Mapping) and isinstance(entry.get("name"), str):
                out.add(entry["name"])
            elif isinstance(entry, str):
                out.add(entry)
    for found in (record.get("uses") or {}).values():
        out |= {name for name in found if isinstance(name, str) and name != STAR}
    return frozenset(out)


# ---- the index (section 7.2) -------------------------------------------------------------


@dataclass(frozen=True)
class User:
    """One run-time import of a unit: the map, the importing component and module, the
    imported module, and the names."""

    map: str
    component: str
    module: str
    target: str
    names: tuple[str, ...]


@dataclass
class Unit:
    """One imported module: its users, the crossing import lines that use it, its notes,
    the names that its facts give, and the map of its line with its component there."""

    module: str
    provided: frozenset[str] = frozenset()
    users: list[User] = field(default_factory=list)
    crossings: list[str] = field(default_factory=list)
    notes: set[str] = field(default_factory=set)
    line_map: str | None = None
    prefix: str = ""
    component: str = ""

    @property
    def used(self) -> frozenset[str]:
        """The names that the users import, without `"*"`."""
        return frozenset(n for user in self.users for n in user.names if n != STAR)

    @property
    def star(self) -> bool:
        """Tell if a user imports the full module with no known names."""
        return any(STAR in user.names for user in self.users)

    @property
    def known(self) -> frozenset[str]:
        return self.used | self.provided

    @property
    def line(self) -> str:
        return self.prefix + module_line(self.module)


@dataclass(frozen=True)
class Crossing:
    """One import crossing: its line, its map, its two components, its run-time imports,
    and the names that it uses in each unit."""

    line: str
    map: str
    source: str
    target: str
    edges: tuple[tuple[str, str], ...]
    units: Mapping[str, frozenset[str]]


@dataclass(frozen=True)
class Index:
    """The units and the import crossings of all loaded maps, and the module records."""

    units: Mapping[str, Unit]
    crossings: Mapping[str, Crossing]
    components: Mapping[str, Any]


def _add_edges(
    names: _Names,
    owner: Mapping[str, str],
    units: dict[str, Unit],
    user: tuple[str, str, str],
    edges: Iterable[tuple[str, str]],
) -> dict[str, frozenset[str]]:
    """Add the users of the run-time imports of one import crossing. Give its units.

    `user` is the map ID, the importing component, and the crossing import line."""
    map_id, component, line = user
    per_unit: dict[str, set[str]] = {}
    for module, target in edges:
        found, notes = _edge_units(names, owner, module, target)
        for u, used in found.items():
            unit = units.get(u)
            if unit is None:
                unit = units[u] = Unit(u, provided(names.components.get(u)))
            unit.users.append(User(map_id, component, module, target, tuple(sorted(used))))
            if line not in unit.crossings:
                unit.crossings.append(line)
            per_unit.setdefault(u, set()).update(used)
        if notes:
            units[target].notes.update(notes)
    return {u: frozenset(used) for u, used in sorted(per_unit.items())}


def _runtime(
    components: Mapping[str, Any], edges: Iterable[tuple[str, str]]
) -> tuple[tuple[str, str], ...]:
    return tuple((m, t) for m, t in edges if import_forms.runtime(components.get(m), t))


def index(tree: nest.Tree, facts: dict[str, Any]) -> Index:
    """Give the units and the import crossings of all loaded maps of the tree.

    The users of a unit are the run-time imports of the import crossings. An import only
    for type checks makes no user."""
    components = facts.get("components", {})
    names = _Names(components)
    tables = {m.id: owners(m.model, facts) for m in tree.maps}
    units: dict[str, Unit] = {}
    crossings: dict[str, Crossing] = {}
    for m in tree.maps:
        for (p, q), edges in crossing_imports(m.model, facts).items():
            line = m.prefix + crossing_line(p, q)
            run = _runtime(components, edges)
            found = _add_edges(names, tables[m.id], units, (m.id, p, line), run)
            crossings[line] = Crossing(line, m.id, p, q, run, found)
    cards = {m.id: {c.id: c for c in m.model.components} for m in tree.maps}
    for unit in units.values():
        line_map = _line_map(tree, tables, cards, unit.module)
        if line_map is not None:
            unit.line_map, unit.prefix = line_map.id, line_map.prefix
            unit.component = tables[line_map.id][unit.module]
    return Index(units, crossings, components)


def _line_map(
    tree: nest.Tree,
    tables: Mapping[str, Mapping[str, str]],
    cards: Mapping[str, Mapping[str, Component]],
    module: str,
) -> nest.Map | None:
    """Give the map of the line of a unit (section 7.3), or None.

    Start at the top map. While the component of the module opens a nested map, continue
    in that map. When that map is not loaded (a scoped load), give None. When a map has
    no component for the module, give the last map that had one."""
    loaded = {m.id: m for m in tree.maps}
    current: nest.Map = tree.top
    last: nest.Map | None = None
    while True:
        card_id = tables[current.id].get(module)
        if card_id is None:
            return last
        card = cards[current.id].get(card_id)
        if card is None or card.map is None or card.kind == "actor":
            return current
        child = loaded.get(f"{current.id}/{card_id}" if current.id else card_id)
        if child is None:
            return None
        last, current = current, child


def lines(found: Index, tree: nest.Tree) -> list[str]:
    """Give one `module use` line for each unit whose line map is a reported map."""
    order = {m.id: n for n, m in enumerate(tree.maps)}
    reported = {m.id for m in tree.reported}
    chosen = [u for u in found.units.values() if u.line_map in reported]
    chosen.sort(key=lambda u: (order.get(u.line_map or "", 0), u.module))
    return [u.line for u in chosen]


def evidence(found: Index) -> dict[str, str]:
    """Give the evidence digest of each unit (`judgement_evidence.use_state`), also for a
    unit with no line in this run."""
    return {
        module: judgement_evidence.digest(judgement_evidence.use_state(found.components, module))
        for module in found.units
    }


# ---- module role answers (section 9) -----------------------------------------------------


def role_answer(answer: Answer) -> str | None:
    """Give the module of a module role answer: an exact answer with one `module use` item."""
    return item_module(answer.items[0]) if len(answer.items) == 1 else None


def symbol_issue(answer: Answer, unit: Unit) -> str | None:
    """Give the text of a module role answer whose names the facts do not give, or None."""
    item, module, symbol = answer.items[0], unit.module, answer.symbol
    if answer.role == MIXED:
        bad = next((name for name in answer.handoff if name not in unit.known), None)
        return f"'{item}': {bad} in handoff is not a name of {module}." if bad else None
    if answer.role == HANDOFF:
        if symbol and symbol not in unit.known:
            return f"'{item}': {symbol} is not a name of {module}."
        return None
    if not unit.known:
        return (
            f"'{item}': the facts give no names for {module}. Remove the symbol."
            if symbol
            else None
        )
    if not symbol:
        return f"'{item}': role \"helper\" must have a symbol: a name from the rows below the line."
    if symbol in unit.used or (unit.star and symbol in unit.provided):
        return None
    return (
        f"'{item}': {symbol} is not a name of {module} that other components import. Give a "
        "name from the rows below the line."
    )


@dataclass(frozen=True)
class Ref:
    """One source record of a flow: the flow, the cited location, its module, and the
    unit and the name that it cites (`""` when the record cites no name)."""

    flow: str
    artifact: str
    location: str
    module: str
    unit: str
    name: str


def flow_refs(tree: nest.Tree, facts: dict[str, Any]) -> list[Ref]:
    """Give the source records of the flows of all loaded maps. The freshness of a record
    is not examined."""
    names = _Names(facts.get("components", {}))
    out: list[Ref] = []
    for m in tree.maps:
        owner = owners(m.model, facts)
        for f in m.model.flows:
            for ref in f.source_refs:
                location = ref.rpartition("@")[0] or ref
                module, symbol = ref_module(ref), location.partition(":")[2]
                unit, name = (module, "")
                if symbol:
                    unit, name, _note = _resolve(names, owner, module, symbol)
                out.append(Ref(f.name, f.artifact, location, module, unit, name))
    return out


def cites(ref: Ref, unit: Unit, components: Mapping[str, Any]) -> tuple[bool, str]:
    """Tell if a source record cites a unit, and give the cited name.

    The record cites the unit when its unit is the unit, or when its module defines a
    name that the users import from the unit (a unit that re-exports names)."""
    if ref.unit == unit.module:
        return True, ref.name
    names = _Names(components)
    for name in sorted(unit.used):
        entry = names.entry(unit.module, name)
        if entry is not None and entry.get("defined_in") == ref.module:
            return True, name
    return False, ""


def flow_issue(
    answer: Answer, unit: Unit, refs: Iterable[Ref], components: Mapping[str, Any]
) -> str | None:
    """Give the text of a helper or mixed answer that a flow source record contradicts."""
    if answer.role == HANDOFF:
        return None
    item = answer.items[0]
    for ref in refs:
        cited, name = cites(ref, unit, components)
        if not cited:
            continue
        head = f"'{item}': the flow {ref.flow} ({ref.artifact}) cites {ref.location}"
        if answer.role == HELPER:
            return (
                f"{head}. Thus the map shows that {unit.module} takes part in a flow. Change "
                'the module role to "handoff" or "mixed".'
            )
        if name and name not in answer.handoff:
            return (
                f"{head}, and {name} is not in handoff. Add {name} to handoff, or change the "
                'module role to "handoff".'
            )
    return None


@dataclass(frozen=True)
class Roles:
    """The accepted module role answers by module, and the records of the refused ones."""

    accepted: Mapping[str, Answer]
    refused: list[dict[str, Any]]

    @property
    def refused_modules(self) -> frozenset[str]:
        return frozenset(row["module"] for row in self.refused)


def roles(
    given: Iterable[Answer],
    found: Index,
    unit_evidence: Mapping[str, str],
    tree: nest.Tree,
    facts: dict[str, Any],
) -> Roles:
    """Accept or refuse each module role answer whose module is a unit (section 9.2).

    The map prefix of the item does not change the result. An answer for a module that is
    not a unit is inactive. An answer with a different evidence digest is pending: it is
    not accepted and not refused."""
    accepted: dict[str, Answer] = {}
    refused: list[dict[str, Any]] = []
    refs: list[Ref] | None = None
    for answer in given:
        module = role_answer(answer)
        unit = found.units.get(module) if module else None
        if unit is None or answer.evidence != unit_evidence.get(unit.module):
            continue
        refs = flow_refs(tree, facts) if refs is None else refs
        issue, cause = _issue(answer, unit, refs, found.components)
        if issue is None:
            accepted.setdefault(unit.module, answer)
            continue
        refused.append(
            {
                "answer": answer.label,
                "items": list(answer.items),
                "cause": cause,
                "text": issue,
                "lines": int(unit.line_map is not None),
                "module": unit.module,
            }
        )
    return Roles(accepted, refused)


def _issue(
    answer: Answer, unit: Unit, refs: Iterable[Ref], components: Mapping[str, Any]
) -> tuple[str | None, str]:
    """Give the text and the cause of a refused module role answer, or None and `""`."""
    issue = symbol_issue(answer, unit)
    if issue is not None:
        return issue, "symbol"
    issue = flow_issue(answer, unit, refs, components)
    return (issue, "flow_source") if issue is not None else (None, "")


def check_role(
    answer_like: Answer | Mapping[str, Any],
    found: Index,
    unit_evidence: Mapping[str, str],
    tree: nest.Tree,
    facts: dict[str, Any],
) -> str | None:
    """Give the text of a module role answer that the rules refuse, or None.

    The answer can be an entry of `[judgement] answered`. Then the static rules of the
    answer form apply first, and the text has no location. Then the rules of `roles`
    apply. An answer that is inactive or pending is not refused. An answer with no
    evidence digest has the digest of its unit."""
    if not isinstance(answer_like, Answer):
        try:
            answer_like = config_answers.answer_entry(answer_like, "")
        except ValueError as error:
            return str(error).strip()
    module = role_answer(answer_like)
    unit = found.units.get(module) if module else None
    if unit is None:
        return None
    current = unit_evidence.get(unit.module)
    if answer_like.evidence and answer_like.evidence != current:
        return None
    return _issue(answer_like, unit, flow_refs(tree, facts), found.components)[0]


# ---- import crossing states (section 10) -------------------------------------------------


def handoff_names(answer: Answer | None, used: frozenset[str]) -> tuple[bool, str]:
    """Tell if an import crossing uses handoff code of a unit with the names `used`.

    Also give the text of the unit for the `handoff modules:` row: the handoff names that
    the import crossing uses, or "the module"."""
    if answer is None or answer.role == HELPER:
        return False, ""
    if answer.role == HANDOFF:
        return True, ""
    hit = sorted(used & set(answer.handoff))
    if hit:
        return True, ", ".join(hit)
    return (STAR in used), "the module"


def _state(units: Mapping[str, frozenset[str]], accepted: Mapping[str, Answer]) -> str:
    found = {
        OPEN if handoff_names(accepted.get(u), used)[0] else (NONE if u not in accepted else CLOSED)
        for u, used in units.items()
    }
    return OPEN if OPEN in found else WAITING if NONE in found else CLOSED


def crossing_states(found: Index, accepted: Mapping[str, Answer]) -> dict[str, str]:
    """Give the state of each import crossing: `open` when it uses handoff code of one or
    more units, else `waiting` when one or more units have no accepted module role, else
    `closed`."""
    return {line: _state(c.units, accepted) for line, c in found.crossings.items()}


def checked_states(
    states: Mapping[str, str],
    found: Index,
    tree: nest.Tree,
    accepted: Mapping[str, Answer],
    line_of: Callable[[Index, nest.Tree], list[str]] = lines,
) -> dict[str, str]:
    """Open each waiting import crossing that the invariant does not cover.

    The invariant: in a full tree, each waiting import crossing has one or more units with
    no accepted module role, and each such unit has a `module use` line. If not, the
    state becomes `open`. In a scoped tree, a unit can have no line map, so the states do
    not change."""
    out = dict(states)
    if tree.partial:
        return out
    present = set(line_of(found, tree))
    for line, state in states.items():
        if state != WAITING:
            continue
        missing = [u for u in found.crossings[line].units if u not in accepted]
        if not missing or any(found.units[u].line not in present for u in missing):
            out[line] = OPEN
    return out


# ---- delta (section 12) ------------------------------------------------------------------


def _all_units(components: dict[str, Any], owner: dict[str, str]) -> dict[str, Unit]:
    """Give the units of all run-time imports between components of one owner table."""
    names = _Names(components)
    units: dict[str, Unit] = {}
    for (p, _q), edges in crossing_pairs(components, owner).items():
        _add_edges(names, owner, units, ("", p, ""), _runtime(components, edges))
    return units


def closes_import(
    answered: Iterable[Answer],
    components: dict[str, Any],
    owner: dict[str, str],
    module: str,
    target: str,
) -> bool:
    """Tell if module role answers close a new import of `target` by `module`.

    Each unit of the import must have an exact answer with the current evidence digest,
    with the symbol rules of section 9.2, and with the module role `helper`, or `mixed`
    with no handoff name and no `"*"` in the names of the unit. The users of a unit are
    the run-time imports between components, with or without a flow, because the delta
    has no flow tree. For the same reason, the delta does not apply the flow source rule.
    """
    names = _Names(components)
    found, _notes = _edge_units(names, owner, module, target)
    by_line: dict[str, Answer] = {}
    for answer in answered:
        if len(answer.items) == 1:
            by_line.setdefault(bare(answer.items[0]), answer)
    chosen = {u: by_line.get(module_line(u)) for u in found}
    if not found or any(answer is None for answer in chosen.values()):
        return False
    units = _all_units(components, owner)
    for u, used in found.items():
        given = chosen[u]
        digest = judgement_evidence.digest(judgement_evidence.use_state(components, u))
        if given is None or given.evidence != digest or symbol_issue(given, units[u]):
            return False
        if given.role != HELPER and handoff_names(given, frozenset(used))[0]:
            return False
    return True


# ---- rows and counts ---------------------------------------------------------------------


def accepted_role(module: str, picked: Roles) -> str:
    """Give the accepted module role of a unit, or `none`. A refused answer gives `none`."""
    answer = picked.accepted.get(module)
    return answer.role if answer is not None else NONE


def unit_role(module: str, picked: Roles) -> str:
    """Give the module role of a unit: the accepted role, `refused`, or `none`."""
    answer = picked.accepted.get(module)
    if answer is not None:
        return answer.role
    return REFUSED if module in picked.refused_modules else NONE


def unit_rows(
    unit: Unit,
    found: Index,
    states: Mapping[str, str],
    refs: Iterable[Ref],
    prefixes: Mapping[str, str],
) -> list[str]:
    """Give the detail rows of a `module use` line after the count row (section 8.1)."""
    by_user: dict[tuple[str, str], set[str]] = {}
    for user in unit.users:
        by_user.setdefault((user.map, user.component), set()).update(user.names)
    rows = [f"component: {unit.component}"]
    for (map_id, component), used in sorted(by_user.items()):
        shown = ", ".join("the module" if n == STAR else n for n in sorted(used))
        rows.append(f"{prefixes.get(map_id, '')}{component} imports {shown}")
    waiting = sum(states.get(line) == WAITING for line in unit.crossings)
    rows.append(f"import crossings that wait for the module role: {waiting}")
    flows = sorted({ref.flow for ref in refs if cites(ref, unit, found.components)[0]})
    if flows:
        rows.append(f"flows that cite the module: {', '.join(flows)}")
    rows += sorted(unit.notes)
    rows += _form_rows(unit, found.components)
    return rows


def _form_rows(unit: Unit, components: Mapping[str, Any]) -> list[str]:
    """Give a row for each import of the unit only in a function body, and for each import
    of the unit by a string value."""
    edges = sorted({(user.module, user.target) for user in unit.users})
    rows = [
        f"{m} imports {t} only in a function body."
        for m, t in edges
        if import_forms.deferred(components.get(m), t)
    ]
    rows += [
        f"{module} imports a module by a string value at line {record.get('line')}: "
        f"{record.get('call')}({record.get('text') or 'a value'})."
        for module in sorted(components)
        for record in import_forms.dynamic_records(components[module])
        if record.get("target") == unit.module
    ]
    return rows


def handoff_row(crossing: Crossing, accepted: Mapping[str, Answer]) -> str:
    """Give the `handoff modules:` row of an open import crossing."""
    shown: list[str] = []
    for u, used in crossing.units.items():
        answer = accepted.get(u)
        hit, text = handoff_names(answer, used)
        if hit:
            shown.append(u if answer is not None and answer.role == HANDOFF else f"{u} ({text})")
    return f"handoff modules: {', '.join(sorted(shown))}"


def user_count(unit: Unit) -> int:
    """Give the count of the distinct components that import the unit, over all maps."""
    return len({(user.map, user.component) for user in unit.users})


def count_rows(states: Iterable[str], unit_roles: Iterable[str]) -> list[str]:
    """Give the two count rows of the text report, or no rows when the map has no import
    crossing and no unit."""
    found, picked = list(states), list(unit_roles)
    if not found and not picked:
        return []
    n = {state: found.count(state) for state in (OPEN, WAITING, CLOSED)}
    r = {role: picked.count(role) for role in (HELPER, HANDOFF, MIXED, REFUSED, NONE)}
    return [
        f"import crossings: {len(found)} have no flow. {n[OPEN]} are open. {n[WAITING]} wait "
        f"for module roles. {n[CLOSED]} are closed by module roles.",
        f"module roles: {len(picked)} modules. {r[HELPER]} helper, {r[HANDOFF]} handoff, "
        f"{r[MIXED]} mixed, {r[REFUSED]} refused, {r[NONE]} with no module role.",
    ]
