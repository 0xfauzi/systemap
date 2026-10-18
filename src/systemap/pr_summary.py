"""The pull request summary: the architectural effect of a change, for a reviewer.

The summary has three parts. Each part uses data that other modules calculate:

- Contract: the invariants and the import rules that the change added, removed, or
  changed. systemap compares the committed model at the base commit with the model on
  disk. A reviewer accepts or rejects each contract change in the usual review.
- Map: the components, the flows, and the sequences that the change added, removed, or
  changed (`delta_model.compare`).
- Rules: the result of each import rule at the head commit (`import_rules`).

Each item row gives the assurance level and the freshness of its claim at the head
commit (`assurance.of_tree`). A removed item, an actor, and a sequence have no level.

`markdown` makes the text. It reads only its argument, so a test can give fixtures.
`collect` reads the base model and calculates the argument.

To add a part, add one field to `Summary` and one function that gives its rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from systemap import assurance, delta_git, delta_model, import_rules, nest
from systemap.assurance import Claim
from systemap.config import Config
from systemap.delta_model import ADDED, CHANGED, REMOVED, Item, MapChange
from systemap.model import ImportRule, Invariant, Model

# The maximum number of item rows in one part. A row at the end gives the count of the
# other rows.
ROWS = 5
INVARIANT, IMPORT_RULE = "invariant", "import rule"
# The reader words for the changed fields of each contract rule. The keys are schema keys.
INVARIANT_FIELDS = {"text": "text", "governs": "components", "reason": "reason"}
IMPORT_RULE_FIELDS = {
    "kind": "kind",
    "src": "source components",
    "dst": "target components",
    "reason": "reason",
    "invariant": "invariant",
}
# The record whose freshness the level row gives, for each claim type.
RECORD = {
    assurance.COMPONENT: "source review",
    assurance.FLOW: "flow review",
    assurance.INVARIANT: "source review",
    assurance.IMPORT_RULE: "facts",
}
LEGEND = (
    "Levels: established = the facts show the claim. examined = an agent or a person "
    "examined the cited source. unknown = the facts and the source reviews do not show the claim."
)


@dataclass(frozen=True)
class RuleChange:
    """One contract rule that the change added, removed, or changed.

    `id` is the invariant number or the import rule id. `fields` gives the reader words
    for the changed parts of a changed rule.
    """

    how: str
    map: str
    kind: str
    id: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Summary:
    """The data of the pull request summary.

    `maps` gives the map change of each map at the head commit, with the head map.
    `error` gives the reason that the base model does not load. Then systemap does not
    compare the contract and the map.
    """

    contract: tuple[RuleChange, ...]
    maps: tuple[tuple[nest.Map, MapChange], ...]
    claims: tuple[Claim, ...]
    rules: tuple[import_rules.MapOutcomes, ...]
    unknown_policy: str
    open_lines: int
    error: str = ""


# ---- the changes -----------------------------------------------------------------------


def _rule_changes(
    map_id: str, kind: str, base: dict[str, Any], head: dict[str, Any], fields: dict[str, str]
) -> list[RuleChange]:
    """Give the added and changed rules in the sequence of the head model. Then give the
    removed rules."""
    out: list[RuleChange] = []
    for key, rule in head.items():
        old = base.get(key)
        words = () if old is None else _differ(old, rule, fields)
        if old is None or words:
            out.append(RuleChange(ADDED if old is None else CHANGED, map_id, kind, key, words))
    out += [RuleChange(REMOVED, map_id, kind, key) for key in base if key not in head]
    return out


def _value(rule: object, name: str) -> object:
    """Give a field value. The sequence of the components in a rule is not a change."""
    value = getattr(rule, name)
    return tuple(sorted(value)) if isinstance(value, tuple) else value


def _differ(old: object, new: object, fields: dict[str, str]) -> tuple[str, ...]:
    return tuple(word for name, word in fields.items() if _value(old, name) != _value(new, name))


def _invariants(model: Model) -> dict[str, Invariant]:
    ordered = sorted(model.invariants, key=lambda rule: rule.n)
    return {str(rule.n): rule for rule in ordered}


def _import_rules(model: Model) -> dict[str, ImportRule]:
    return {rule.id: rule for rule in model.import_rules}


def contract_changes(base: nest.Tree, head: nest.Tree) -> tuple[RuleChange, ...]:
    """Give the contract changes of each map in the sequence of the head tree. Then give
    the contract changes of the removed maps.

    A map that is not in one tree has no rules in that tree.
    """
    empty = delta_model.EMPTY
    before = {m.id: m.model for m in base.maps}
    after = {m.id: m.model for m in head.maps}
    ids = [*after, *(map_id for map_id in before if map_id not in after)]
    out: list[RuleChange] = []
    for map_id in ids:
        old, new = before.get(map_id, empty), after.get(map_id, empty)
        out += _rule_changes(
            map_id, INVARIANT, _invariants(old), _invariants(new), INVARIANT_FIELDS
        )
        out += _rule_changes(
            map_id, IMPORT_RULE, _import_rules(old), _import_rules(new), IMPORT_RULE_FIELDS
        )
    return tuple(out)


def map_changes(base: nest.Tree, head: nest.Tree) -> tuple[tuple[nest.Map, MapChange], ...]:
    """Give the map change of each head map. The contract part gives the invariants."""
    before = {m.id: (m.model, m.meaning) for m in base.maps}
    empty = (delta_model.EMPTY, delta_model.NO_MEANING)
    out = []
    for m in head.maps:
        change = delta_model.compare(before.get(m.id, empty), (m.model, m.meaning))
        out.append((m, MapChange(change.components, change.flows, change.sequences)))
    return tuple(out)


def collect(
    cfg: Config, tree: nest.Tree, base_sha: str, head: dict[str, Any], open_lines: int
) -> Summary:
    """Calculate the summary data: the base model at `base_sha`, the model on disk
    `tree`, and the facts at the head commit."""
    claims = tuple(assurance.of_tree(tree, head))
    rules = tuple(import_rules.run_tree(tree, head))
    base = delta_git.model_at(cfg, base_sha)
    if isinstance(base, str):
        return Summary((), (), claims, rules, cfg.rules_unknown, open_lines, base)
    return Summary(
        contract_changes(base, tree),
        map_changes(base, tree),
        claims,
        rules,
        cfg.rules_unknown,
        open_lines,
    )


# ---- the text --------------------------------------------------------------------------


def _code(text: str) -> str:
    """Give the text as a Markdown code span. The span shows no link and no mention."""
    return "`" + " ".join(text.replace("`", "'").split()) + "`"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _level(claim: Claim | None) -> str:
    """Give the level and the freshness of a claim, or "no level"."""
    if claim is None:
        return "no level"
    if claim.level == assurance.ESTABLISHED:
        return "established from facts"
    return f"{claim.level}, {RECORD[claim.type]} {claim.freshness}"


def _named(map_id: str, name: str) -> str:
    return f"{map_id}/{name}" if map_id else name


def _fields(fields: tuple[str, ...]) -> str:
    return f" ({', '.join(fields)})" if fields else ""


def _limited(rows: list[str]) -> list[str]:
    """Give at most ROWS rows, and one row with the count of the other rows."""
    more = len(rows) - ROWS
    tail = [f"  - {_plural(more, 'more row')}"]
    return rows[:ROWS] + (tail if more > 0 else [])


def _counted(groups: Iterable[tuple[str, str]]) -> str:
    """Give the count of each group, for example "1 added flow, 2 changed components"."""
    found: dict[tuple[str, str], int] = {}
    for group in groups:
        found[group] = found.get(group, 0) + 1
    return ", ".join(_plural(n, f"{how} {noun}") for (how, noun), n in found.items())


Claims = dict[tuple[str, str, str], Claim]


def _claims(s: Summary) -> Claims:
    """Give the claims by map, type, and identifier."""
    return {(c.map, c.type, c.id): c for c in s.claims}


def _contract(s: Summary) -> list[str]:
    if not s.contract:
        return ["- **Contract:** no change"]
    claims = _claims(s)
    types = {INVARIANT: assurance.INVARIANT, IMPORT_RULE: assurance.IMPORT_RULE}
    head = (
        f"- **Contract:** {_counted((r.how, r.kind) for r in s.contract)}. "
        "Accept or reject each contract change in this review."
    )
    rows = [
        f"  - {r.how} {r.kind} {_code(_named(r.map, r.id))}{_fields(r.fields)}: "
        f"{_level(claims.get((r.map, types[r.kind], r.id)))}"
        for r in s.contract
    ]
    return [head, *_limited(rows)]


def _item_rows(m: nest.Map, change: MapChange, claims: Claims) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for item in change.components:
        claim = None if item.how == REMOVED else claims.get((m.id, assurance.COMPONENT, item.name))
        text = f"{_code(_named(m.id, item.name))}{_fields(item.fields)}"
        rows.append((item.how, "component", f"{text}: {_level(claim)}"))
    for item in change.flows:
        rows.append((item.how, "flow", _flow_row(m, item, claims)))
    for item in change.sequences:
        text = f"{_code(_named(m.id, item.name))}{_fields(item.fields)}"
        rows.append((item.how, "sequence", f"{text}: no level"))
    return rows


def _flow_row(m: nest.Map, item: Item, claims: Claims) -> str:
    src, dst = (_code(_named(m.id, end)) for end in item.ends)
    claim = None
    if item.how != REMOVED:
        claim = claims.get((m.id, assurance.FLOW, m.model.flows[item.go].key))
    return f"{src} -> {dst}, {_code(item.name)}{_fields(item.fields)}: {_level(claim)}"


def _map(s: Summary) -> list[str]:
    claims = _claims(s)
    rows = [row for m, change in s.maps for row in _item_rows(m, change, claims)]
    if not rows:
        return ["- **Map:** no change"]
    head = f"- **Map:** {_counted((how, noun) for how, noun, _text in rows)}"
    return [head, *_limited([f"  - {how} {noun} {text}" for how, noun, text in rows])]


def _rule_counts(s: Summary) -> dict[str, int]:
    found = [o.result for m in s.rules for o in m.outcomes]
    return {
        result: found.count(result)
        for result in (import_rules.PASS, import_rules.FAIL, import_rules.UNKNOWN)
    }


def _counts_text(s: Summary) -> str:
    n = _rule_counts(s)
    if not any(n.values()):
        return "none"
    return f"{n['pass']} passed, {n['fail']} failed, {n['unknown']} unknown"


def _rule_detail(outcome: import_rules.Outcome) -> str:
    """Give the first import against the rule, or the first module with unknown imports."""
    if outcome.imports:
        src, dst = outcome.imports[0]
        found, noun = f"{_code(src)} imports {_code(dst)}", "import"
        more = len(outcome.imports) - 1
    else:
        gap = outcome.gaps[0] if outcome.gaps else import_rules.Gap("", "", "")
        found = f"{_code(gap.module)}: {gap.detail}" if gap.module else gap.detail
        noun, more = "module", len(outcome.gaps) - 1
    return found + (f", and {_plural(more, 'other ' + noun)}" if more > 0 else "")


def _rules(s: Summary) -> list[str]:
    claims = _claims(s)
    head = f"- **Rules:** {_counts_text(s)}"
    if _rule_counts(s)["unknown"]:
        head += f". Policy for an unknown result: {s.unknown_policy}"
    rows = [
        f"  - {o.result} {_code(_named(m.map_id, o.rule.id))}: {_rule_detail(o)}. "
        f"Level: {_level(claims.get((m.map_id, assurance.IMPORT_RULE, o.rule.id)))}"
        for m in s.rules
        for o in m.outcomes
        if o.result != import_rules.PASS
    ]
    return [head, *_limited(rows)]


def _update(s: Summary) -> list[str]:
    if not s.open_lines:
        return []
    return [
        f"- **Map update:** necessary for {_plural(s.open_lines, 'line')}. "
        "The log of the delta job gives the action for each line."
    ]


def no_change(s: Summary) -> bool:
    """Tell if the change has no architectural effect. A failed rule is an effect."""
    return (
        not (s.error or s.contract or any(c.count for _m, c in s.maps) or s.open_lines)
        and not _rule_counts(s)["fail"]
    )


def markdown(s: Summary) -> str:
    """Give the summary as Markdown lines without the comment marker.

    Without an architectural effect, the summary is one line.
    """
    if no_change(s):
        return f"**Architecture:** no change to the contract or the map. Rules: {_counts_text(s)}."
    if s.error:
        parts = [f"- **Contract and map:** unknown. {s.error}"]
    else:
        parts = [*_contract(s), *_map(s)]
    lines = ["**Architecture**", "", *parts, *_rules(s), *_update(s), "", LEGEND]
    return "\n".join(lines)
