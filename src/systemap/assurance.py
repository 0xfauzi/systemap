"""Give the assurance level and the freshness of each claim of a map.

The level tells how strong the evidence for the full claim is:

- `established`: the facts of this source snapshot show the full claim. Only an import
  rule with the result `pass` gets this level. Imports and call sites do not show the
  direction or the artifact of a flow. They also do not show the text of a component or
  of an invariant.
- `examined`: a current review records that an agent or a person examined the claim
  against cited source. This is support for the claim. The facts do not show it.
- `unknown`: the facts and the reviews do not show the claim. A rule with the result
  `fail` or `unknown` also gets this level. An `unknown` level is never a pass.

The freshness is a separate value. It tells if the record behind the level agrees with
the current source: `current`, `earlier` (a flow review earlier than source tracking),
`stale`, or `missing` (no record). A stale record never gives `examined`.

This module reads only the states that other modules calculate: the source review state
(`card_review`), the flow evidence and the flow review state (`evidence`, `flow_review`),
and the import rule results (`import_rules`). These read only the model fields and the
language-neutral facts. A supported decision writes a review digest, so the review state
includes it. This module does not read the local decision store.

To add a claim type, add one function to `_TYPES` and its basis texts to `BASIS_TEXT`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from systemap import card_review, evidence, flow_review, import_rules, nest
from systemap.model import Component, Invariant, Meaning, Model

ESTABLISHED, EXAMINED, UNKNOWN = "established", "examined", "unknown"
LEVELS = (ESTABLISHED, EXAMINED, UNKNOWN)
CURRENT, EARLIER, STALE, MISSING = "current", "earlier", "stale", "missing"

COMPONENT, FLOW, INVARIANT, IMPORT_RULE = "component", "flow", "invariant", "import_rule"

# The text for a person about each level. The page gives it.
LEVEL_TEXT = {
    ESTABLISHED: "The facts of this source snapshot show the full claim.",
    EXAMINED: "An agent or a person examined the claim against the cited source. "
    "The facts do not show the claim.",
    UNKNOWN: "The facts and the source reviews do not show the claim.",
}

# The basis is the existing state that gives the level. It is a stable identifier.
# The text for a person tells about each basis.
BASIS_TEXT = {
    "rule_pass": "The import facts show no import against the rule.",
    "rule_fail": "The import facts show an import against the rule.",
    "rule_unknown": "The import facts are not full for this rule.",
    "source_review_current": "The source review agrees with the current source and claims.",
    "source_review_stale": "The source or the claims changed after the source review.",
    "source_review_missing": "The map has no source review for the applicable components.",
    "flow_review_current": "The flow review agrees with the current cited source.",
    "flow_review_earlier": "The flow review is earlier than source tracking. "
    "Its digest does not identify the examined source.",
    "flow_review_stale": "The cited source or the flow changed after the flow review.",
    "flow_review_missing": "The flow has no flow review with source records.",
    "citation_outside_endpoints": "No source record of the flow review is in a module of "
    "a flow endpoint.",
    "no_source_component": "The invariant applies to no source component.",
}
BASES = tuple(BASIS_TEXT)


@dataclass(frozen=True)
class Claim:
    """The level, the freshness, and the basis of one claim of one map.

    `id` is the component ID, the flow identifier, the invariant number, or the import
    rule id."""

    map: str
    type: str
    id: str
    level: str
    freshness: str
    basis: str

    def row(self) -> dict[str, str]:
        """Give the JSON object of the claim for a program. It has no text for a person."""
        return {
            "map": self.map,
            "type": self.type,
            "id": self.id,
            "level": self.level,
            "freshness": self.freshness,
            "basis": self.basis,
        }

    def panel(self) -> dict[str, str]:
        """Give the values that the page gives for the claim. `texts` gives the text."""
        return {"level": self.level, "freshness": self.freshness, "basis": self.basis}


@dataclass(frozen=True)
class _Context:
    """The model of one map and the states that the claim types read."""

    map_id: str
    model: Model
    meaning: Meaning
    facts: dict[str, Any]
    outcomes: dict[str, import_rules.Outcome]


def _component_claim(ctx: _Context, card: Component) -> tuple[str, str, str]:
    state = card_review.state(card, ctx.model, ctx.meaning, ctx.facts)
    return (EXAMINED if state == card_review.CURRENT else UNKNOWN), state, f"source_review_{state}"


def _components(ctx: _Context) -> list[Claim]:
    """A source component is `examined` only with a current source review. An actor is
    outside the source, and it has no level."""
    return [
        Claim(ctx.map_id, COMPONENT, card.id, *_component_claim(ctx, card))
        for card in ctx.model.components
        if card.kind != "actor"
    ]


def _flows(ctx: _Context) -> list[Claim]:
    """A flow is `examined` when its review agrees with the claim and the source records,
    and a source record is in a module of an endpoint. The flow evidence gives these
    conditions also for a flow with an actor endpoint."""
    found = evidence.of_model(ctx.model, ctx.meaning, ctx.facts)
    out = []
    for flow in ctx.model.flows:
        state = flow_review.state(flow, ctx.meaning, ctx.facts)
        ev = found.of(flow)
        level, basis = UNKNOWN, f"flow_review_{state}"
        if state in flow_review.REVIEWED and ev.no_endpoint_ref:
            basis = "citation_outside_endpoints"
        elif state in flow_review.REVIEWED:
            level = EXAMINED
        out.append(Claim(ctx.map_id, FLOW, flow.key, level, state, basis))
    return out


def _freshness(states: Iterable[str]) -> str:
    """Give the freshness of a group of source reviews: `stale` if one review is stale,
    then `missing` if one review is missing, and `current` if all reviews are current."""
    found = set(states)
    return STALE if STALE in found else MISSING if MISSING in found else CURRENT


def _invariant_claim(ctx: _Context, invariant: Invariant) -> Claim:
    """An invariant is a claim of each component that it applies to. Thus a current source
    review of each applicable component makes it `examined`. A linked import rule with the
    result `fail` makes it `unknown`. A result `pass` examines only the imports, not the
    text, so it does not make the invariant `established`."""
    cards = [
        card
        for card in ctx.model.components
        if card.kind != "actor" and (not invariant.governs or card.id in invariant.governs)
    ]
    if not cards:
        return Claim(
            ctx.map_id, INVARIANT, str(invariant.n), UNKNOWN, MISSING, "no_source_component"
        )
    states = [card_review.state(card, ctx.model, ctx.meaning, ctx.facts) for card in cards]
    freshness = _freshness(states)
    failed = any(
        o.result == import_rules.FAIL and o.rule.invariant == invariant.n
        for o in ctx.outcomes.values()
    )
    if failed:
        return Claim(ctx.map_id, INVARIANT, str(invariant.n), UNKNOWN, freshness, "rule_fail")
    level = EXAMINED if freshness == CURRENT else UNKNOWN
    basis = f"source_review_{freshness}"
    return Claim(ctx.map_id, INVARIANT, str(invariant.n), level, freshness, basis)


def _invariants(ctx: _Context) -> list[Claim]:
    ordered = sorted(ctx.model.invariants, key=lambda invariant: invariant.n)
    return [_invariant_claim(ctx, invariant) for invariant in ordered]


_RULE_LEVEL = {
    import_rules.PASS: (ESTABLISHED, "rule_pass"),
    import_rules.FAIL: (UNKNOWN, "rule_fail"),
    import_rules.UNKNOWN: (UNKNOWN, "rule_unknown"),
}


def _import_rules(ctx: _Context) -> list[Claim]:
    """An import rule is `established` only with the result `pass`. The result comes from
    the facts of this snapshot, so the freshness is `current`, or `missing` without facts.
    A rule without a result, because the model check refuses a rule, is `unknown`."""
    freshness = CURRENT if ctx.facts.get("components") else MISSING
    out = []
    for rule in ctx.model.import_rules:
        found = ctx.outcomes.get(rule.id)
        level, basis = _RULE_LEVEL[found.result if found else import_rules.UNKNOWN]
        out.append(Claim(ctx.map_id, IMPORT_RULE, rule.id, level, freshness, basis))
    return out


_TYPES: tuple[Callable[[_Context], list[Claim]], ...] = (
    _components,
    _flows,
    _invariants,
    _import_rules,
)
TYPES = (COMPONENT, FLOW, INVARIANT, IMPORT_RULE)


def of_model(
    model: Model, meaning: Meaning, facts: dict[str, Any], map_id: str = ""
) -> list[Claim]:
    """Give the claims of one map in this sequence: the components, the flows, the
    invariants, and the import rules. Each group is in model order. The invariants are in
    number order."""
    outcomes = {o.rule.id: o for o in import_rules.evaluate(model, facts)}
    ctx = _Context(map_id, model, meaning, facts, outcomes)
    return [claim for each in _TYPES for claim in each(ctx)]


def of_tree(tree: nest.Tree, facts: dict[str, Any]) -> list[Claim]:
    """Give the claims of each map in tree order. `judgement --json` and the PR summary
    use this function."""
    return [claim for m in tree.maps for claim in of_model(m.model, m.meaning, facts, m.id)]


def counts(claims: Iterable[Claim]) -> dict[str, int]:
    """Count the claims of each level. No key counts a pass. An `unknown` claim counts
    only as `unknown`."""
    found = [claim.level for claim in claims]
    return {level: found.count(level) for level in LEVELS}


def payload(claims: Iterable[Claim]) -> dict[str, Any]:
    """Give the `assurance` object of `judgement --json`."""
    listed = list(claims)
    return {"counts": counts(listed), "claims": [claim.row() for claim in listed]}


def by_type(claims: Iterable[Claim], kind: str) -> dict[str, Claim]:
    """Give the claims of one type by identifier, for the page."""
    return {claim.id: claim for claim in claims if claim.type == kind}


def texts(claims: Iterable[Claim]) -> dict[str, str]:
    """Give the text of each level and each basis of the claims, one time for the page."""
    listed = list(claims)
    out = {claim.level: LEVEL_TEXT[claim.level] for claim in listed}
    return out | {claim.basis: BASIS_TEXT[claim.basis] for claim in listed}


def panel_field(claims: Iterable[Claim], kind: str, claim_id: str) -> dict[str, Any]:
    """Give the `assurance` field of a page record, or no field for a claim without a level,
    such as an actor."""
    found = by_type(claims, kind).get(claim_id)
    return {"assurance": found.panel()} if found else {}
