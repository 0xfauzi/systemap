"""The boundary changes of a map tree: the changes at the frame of each nested map.

A card that opens a map has module claims in its parent map. Its nested map divides
these claims among its internal components. A boundary change is one of these changes
between a base tree and a head tree:

- The claims of a card that opens a map changed. If a claim went from one card of a map
  to a different card of the same map, the change is a move. A move changes the two
  nested maps of the two cards.
- An import rule changed, and it selects a card that opens a map: its `src` names the
  card, or it is a `forbid_cycle` rule with an empty `src`, which selects all
  components. Such a rule records the imports at the boundary of a nested part (the
  parent contract).

The Changes panel of a page (`page_rollup`) and the pull request summary (`pr_summary`)
give the same rows (`rows`). Each row gives the number of changes in each nested map
that the boundary change touches, so a reviewer can examine the boundary change with the
nested map changes. The rows use only the model files, not the source facts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass

from systemap import delta_model, nest
from systemap.delta_model import ADDED, CHANGED, REMOVED
from systemap.model import Component, ImportRule, Model

# The reader words for the changed fields of an import rule. The keys are schema keys.
RULE_FIELDS = {
    "kind": "kind",
    "src": "source components",
    "dst": "target components",
    "reason": "reason",
    "invariant": "invariant",
}


@dataclass(frozen=True)
class ClaimChange:
    """The changed module claims of one card that opens a map.

    `map` is the ID of the parent map. `nested` is the ID of the nested map of the card in
    the head tree, or "" if the head tree has no such map."""

    map: str
    card: str
    gained: tuple[str, ...] = ()
    lost: tuple[str, ...] = ()
    nested: str = ""


@dataclass(frozen=True)
class Move:
    """One module claim that went from the card `src` to the card `dst` of one map.

    `nested` gives the IDs of the nested maps of the two cards in the head tree, or ""."""

    map: str
    claim: str
    src: str
    dst: str
    nested: tuple[str, str] = ("", "")


@dataclass(frozen=True)
class RuleChange:
    """One import rule at a boundary that the change added, removed, or changed.

    `reason` is the reason of the rule in the head tree, or in the base tree for a
    removed rule."""

    how: str
    map: str
    id: str
    fields: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class BoundaryChanges:
    """The boundary changes of a tree. `moves` gives the claims that went between cards."""

    claims: tuple[ClaimChange, ...] = ()
    moves: tuple[Move, ...] = ()
    rules: tuple[RuleChange, ...] = ()

    @property
    def count(self) -> int:
        return len(self.claims) + len(self.rules)

    def within(self, map_id: str) -> BoundaryChanges:
        """Give the boundary changes in the map `map_id` and in the maps below it."""

        def keep(found: str) -> bool:
            return not map_id or found == map_id or found.startswith(map_id + "/")

        return BoundaryChanges(
            tuple(c for c in self.claims if keep(c.map)),
            tuple(m for m in self.moves if keep(m.map)),
            tuple(r for r in self.rules if keep(r.map)),
        )


def _child(map_id: str, card: str) -> str:
    return f"{map_id}/{card}" if map_id else card


def _openers(*models: Model) -> list[str]:
    """Give the IDs of the cards that open a map in one of the models, in model order."""
    out: list[str] = []
    for model in models:
        out += [c.id for c in model.opening if c.kind != "actor" and c.map and c.id not in out]
    return out


def _claims(c: Component | None) -> set[str]:
    return set(c.implemented_by) if c is not None else set()


def _claim_changes(map_id: str, base: Model, head: Model, nested: set[str]) -> list[ClaimChange]:
    out = []
    for card in _openers(head, base):
        before, after = _claims(base.find(card)), _claims(head.find(card))
        if before != after:
            gained, lost = tuple(sorted(after - before)), tuple(sorted(before - after))
            out.append(ClaimChange(map_id, card, gained, lost, _nested(map_id, card, nested)))
    return out


def _gained(base: Model, head: Model) -> dict[str, str]:
    """Give the card of the head model that gained each claim."""
    out: dict[str, str] = {}
    for c in head.components:
        out.update(dict.fromkeys(_claims(c) - _claims(base.find(c.id)), c.id))
    return out


def _moves(map_id: str, base: Model, head: Model, nested: set[str]) -> list[Move]:
    """Give each claim that a card lost and a different card of the map gained, if one of
    the two cards opens a map."""
    openers = set(_openers(head, base))
    gained = _gained(base, head)
    lost = [
        (claim, c.id)
        for c in base.components
        for claim in sorted(_claims(c) - _claims(head.find(c.id)))
    ]
    out = []
    for claim, src in lost:
        dst = gained.get(claim, "")
        if dst and dst != src and {src, dst} & openers:
            ends = (_nested(map_id, src, nested), _nested(map_id, dst, nested))
            out.append(Move(map_id, claim, src, dst, ends))
    return out


def _nested(map_id: str, card: str, nested: set[str]) -> str:
    """Give the ID of the nested map of a card, or "" if the head tree has no such map."""
    inside = _child(map_id, card)
    return inside if inside in nested else ""


def _value(rule: object, name: str) -> object:
    """Give a field value. The sequence of the components in a rule is not a change."""
    value = getattr(rule, name)
    return tuple(sorted(value)) if isinstance(value, tuple) else value


def differ(old: object, new: object, fields: Mapping[str, str] = RULE_FIELDS) -> tuple[str, ...]:
    """Give the reader words of the fields of a rule that are different in `new`."""
    return tuple(word for name, word in fields.items() if _value(old, name) != _value(new, name))


def _selects(rule: ImportRule, openers: set[str]) -> bool:
    """Tell if the rule examines a card that opens a map (`import_rules`)."""
    if not rule.src and rule.kind == "forbid_cycle":
        return bool(openers)
    return bool(set(rule.src) & openers)


def _rule_change(
    map_id: str, key: str, old: ImportRule | None, rule: ImportRule, openers: set[str]
) -> RuleChange | None:
    """Give the change of one rule of the head model, or None for an unchanged rule or a
    rule that is not at a boundary."""
    if not (_selects(rule, openers) or (old is not None and _selects(old, openers))):
        return None
    if old is None:
        return RuleChange(ADDED, map_id, key, (), rule.reason)
    words = differ(old, rule)
    return RuleChange(CHANGED, map_id, key, words, rule.reason) if words else None


def _rule_changes(map_id: str, base: Model, head: Model) -> list[RuleChange]:
    """Give the added and changed boundary rules in head order, then the removed ones."""
    openers = set(_openers(head, base))
    before = {r.id: r for r in base.import_rules}
    after = {r.id: r for r in head.import_rules}
    found = [_rule_change(map_id, key, before.get(key), r, openers) for key, r in after.items()]
    out = [change for change in found if change is not None]
    out += [
        RuleChange(REMOVED, map_id, key, (), rule.reason)
        for key, rule in before.items()
        if key not in after and _selects(rule, openers)
    ]
    return out


def map_pairs(base: nest.Tree, head: nest.Tree) -> Iterator[tuple[str, Model, Model]]:
    """Give the ID and the base and head models of each map in the sequence of the head
    tree, then of each removed map. A map that is not in one tree is empty in that tree."""
    before = {m.id: m.model for m in base.maps}
    after = {m.id: m.model for m in head.maps}
    for map_id in [*after, *(found for found in before if found not in after)]:
        yield (
            map_id,
            before.get(map_id, delta_model.EMPTY),
            after.get(map_id, delta_model.EMPTY),
        )


def compute(base: nest.Tree, head: nest.Tree) -> BoundaryChanges:
    """Compare the boundaries of the base tree with the boundaries of the head tree.

    A map that is not in one tree has no components and no rules in that tree."""
    nested = set(head.ids)
    claims: list[ClaimChange] = []
    moves: list[Move] = []
    rules: list[RuleChange] = []
    for map_id, old, new in map_pairs(base, head):
        claims += _claim_changes(map_id, old, new, nested)
        moves += _moves(map_id, old, new, nested)
        rules += _rule_changes(map_id, old, new)
    return BoundaryChanges(tuple(claims), tuple(moves), tuple(rules))


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _inside(nested: str, counts: Mapping[str, int], code: Callable[[str], str]) -> str:
    """Give the number of changes in one nested map, or nothing without a nested map."""
    if not nested:
        return ""
    return f" Map {code(nested)}: {plural(counts.get(nested, 0), 'change')}."


def _where(map_id: str, code: Callable[[str], str]) -> str:
    return f"in the map {code(map_id)}" if map_id else "in the top map"


def rows(
    found: BoundaryChanges,
    counts: Mapping[str, int],
    code: Callable[[str], str],
    plain: Callable[[str], str] = str,
) -> list[str]:
    """Give one text row for each move, each other claim change, and each boundary rule.

    `counts` gives the number of map changes of each nested map. `code` gives a name as
    code in the output format, and `plain` gives the reason of a rule in that format."""
    out = []
    moved = {(m.map, m.src) for m in found.moves} | {(m.map, m.dst) for m in found.moves}
    for m in found.moves:
        out.append(
            f"{code(m.claim)} moved from {code(m.src)} to {code(m.dst)} {_where(m.map, code)}."
            + _inside(m.nested[0], counts, code)
            + _inside(m.nested[1], counts, code)
        )
    for c in found.claims:
        if (c.map, c.card) in moved and not (set(c.gained) | set(c.lost)) - _moved(found, c):
            continue
        added = f" Added: {', '.join(code(x) for x in c.gained)}." if c.gained else ""
        removed = f" Removed: {', '.join(code(x) for x in c.lost)}." if c.lost else ""
        out.append(
            f"The claims of {code(c.card)} {_where(c.map, code)} changed.{added}{removed}"
            + _inside(c.nested, counts, code)
        )
    for r in found.rules:
        fields = f" ({', '.join(r.fields)})" if r.fields else ""
        reason = f" Reason: {plain(r.reason)}" if r.reason else " The rule has no reason."
        out.append(f"{r.how} import rule {code(r.id)}{fields} {_where(r.map, code)}.{reason}")
    return out


def _moved(found: BoundaryChanges, c: ClaimChange) -> set[str]:
    """Give the claims of a claim change that a move already gives."""
    return {m.claim for m in found.moves if m.map == c.map and c.card in (m.src, m.dst)}
