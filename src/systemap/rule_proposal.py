"""Propose an import rule from the text of an invariant. Never enforce a proposal.

For each invariant without a linked import rule (`ImportRule.invariant`), this module
reads the text clause by clause. A clause has a dependency form when it agrees with one
of the patterns below. The parts of the clause before and after the verb must contain
only component ids of the map, list words, and fill words. Thus "Core must not import
Store unless ..." gives no proposal: "unless" is not a fill word.

| pattern | example | rule |
|---|---|---|
| forbid | "Core must not import Store" | forbid_import, src Core, dst Store |
| allow | "Api imports only Core" | allow_imports, src Api, dst Core |
| only | "Only Core calls Store" | forbid_import, src each other component, dst Store |
| cycle | "No import cycle connects A, B and C" | forbid_cycle, src A, B, C |

The verbs are "import", "depend on", and "call". The patterns accept the forms of the
two writing profiles. A component id must be in the text exactly. A plain name or a
lower-case form is not an id. An actor has no modules, so the `only` pattern does not
put an actor in `src`.

The `only` rule names the components of the map at this time. A component that the
author adds later is not in the rule.

The result is a judgement line with the rule text that the author can copy into the
model. The line has no effect on `systemap check`. This module reads only the model.
It reads no source and no language-specific fact.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from systemap import nest
from systemap.model import ImportRule, Invariant, Model

KIND = "rule proposal"

_NEG = (
    r"(?:must not|must never|does not|do not|did not|never|cannot|can not|can never|"
    r"shall not|should not|may not|will not|is not allowed to|are not allowed to)"
)
_VERB = r"(?:imports?|depends?|calls?)(?:\s+(?:on|upon|from))?"
_MODAL = r"(?:(?:must|can|may|should|shall|will)\s+)?"
PATTERNS: dict[str, re.Pattern[str]] = {
    "only": re.compile(rf"^only\s+(?P<src>.+?)\s+{_MODAL}{_VERB}\s+(?P<dst>.+)$", re.I),
    "forbid": re.compile(rf"^(?P<src>.+?)\s+{_NEG}\s+(?:directly\s+)?{_VERB}\s+(?P<dst>.+)$", re.I),
    "allow": re.compile(
        rf"^(?P<src>.+?)\s+{_MODAL}(?:only\s+{_VERB}|(?:imports?|depends?|calls?)\s+only"
        rf"(?:\s+(?:on|upon|from))?)\s+(?P<dst>.+)$",
        re.I,
    ),
    "cycle": re.compile(
        r"^(?:there is\s+)?no\s+(?:import\s+)?cycle\s+(?:connects|between|among|of)\s+(?P<src>.+)$",
        re.I,
    ),
}
_KINDS = {
    "only": "forbid_import",
    "forbid": "forbid_import",
    "allow": "allow_imports",
    "cycle": "forbid_cycle",
}
# Words that can be in a list of components without a change to its meaning.
FILL = frozenset(
    {"the", "a", "an", "and", "or", "nor", "any", "of", "in", "component", "components"}
    | {"module", "modules", "code"}
)
_CLAUSE = re.compile(r"[.;:!?()\[\]]")
_TOKEN = re.compile(r"[\w-]+|,|&")


@dataclass(frozen=True)
class Proposal:
    """One import rule that the text of an invariant states, and the pattern that found it."""

    invariant: int
    rule: ImportRule
    pattern: str


@dataclass(frozen=True)
class Found:
    """The proposals of one map in the map tree."""

    map: nest.Map
    proposal: Proposal

    @property
    def line(self) -> str:
        return self.map.prefix + line(self.proposal)


def linked(model: Model) -> set[int]:
    """Give the numbers of the invariants that an import rule of the model names."""
    return {r.invariant for r in model.import_rules if r.invariant is not None}


def proposals(model: Model) -> list[Proposal]:
    """Give the proposals of the invariants without a linked rule, in model order."""
    done = linked(model)
    taken = {r.id for r in model.import_rules}
    out: list[Proposal] = []
    for inv in model.invariants:
        if inv.n in done:
            continue
        for pattern, kind, src, dst in _forms(inv, model):
            rule_id = _free(f"invariant-{inv.n}", taken)
            taken.add(rule_id)
            out.append(
                Proposal(inv.n, ImportRule(rule_id, kind, src, dst, invariant=inv.n), pattern)
            )
    return out


def run_tree(tree: nest.Tree) -> list[Found]:
    """Give the proposals of each map in tree order."""
    return [Found(m, p) for m in tree.maps for p in proposals(m.model)]


def rule_text(rule: ImportRule) -> str:
    """Give the Python text of the rule for the model file."""
    return (
        f"ImportRule({json.dumps(rule.id)}, {json.dumps(rule.kind)}, {_ids(rule.src)}, "
        f"{_ids(rule.dst)}, invariant={rule.invariant})"
    )


def line(proposal: Proposal) -> str:
    """Give the judgement line of one proposal. The line is an identifier for answers."""
    return f"{KIND}: invariant {proposal.invariant} can be {rule_text(proposal.rule)}"


def record(found: Found, open_lines: Iterable[str]) -> dict[str, Any]:
    """Give the JSON object of one proposal."""
    rule = found.proposal.rule
    return {
        "map": found.map.id,
        "invariant": found.proposal.invariant,
        "line": found.line,
        "rule": {
            "id": rule.id,
            "kind": rule.kind,
            "src": list(rule.src),
            "dst": list(rule.dst),
            "invariant": rule.invariant,
        },
        "text": rule_text(rule),
        "pattern": found.proposal.pattern,
        "open": found.line in set(open_lines),
    }


_LINE = re.compile(rf"^{KIND}: invariant (\d+) can be ")


def evidence(m: nest.Map, bare: str) -> Any | None:
    """Give the evidence of a proposal line, or None for a line of a different kind.

    The evidence is the invariant, the import rules, and the components of the map.
    A change to the source does not change it.
    """
    found = _LINE.match(bare)
    if found is None:
        return None
    n = int(found[1])
    return {
        "invariant": [dataclasses.asdict(i) for i in m.model.invariants if i.n == n],
        "rules": [dataclasses.asdict(r) for r in m.model.import_rules],
        "components": [(c.id, c.kind) for c in m.model.components],
    }


# ---- the patterns ----------------------------------------------------------------------


def _forms(inv: Invariant, model: Model) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    """Give the pattern, kind, src, and dst of each clause with a dependency form."""
    ids = {c.id for c in model.components}
    out = []
    for clause in _CLAUSE.split(inv.text):
        found = _form(clause.strip(), ids, model)
        if found is not None and found not in out:
            out.append(found)
    return out


def _form(
    clause: str, ids: set[str], model: Model
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]] | None:
    for pattern, regex in PATTERNS.items():
        match = regex.match(clause)
        if match is None:
            continue
        src = _named(match["src"], ids)
        dst = _named(match["dst"], ids) if pattern != "cycle" else ()
        if not _valid(pattern, src, dst):
            return None
        if pattern == "only":
            src, dst = _others(model, src, dst), dst
            if not src:
                return None
        return pattern, _KINDS[pattern], src, dst
    return None


def _valid(pattern: str, src: tuple[str, ...] | None, dst: tuple[str, ...] | None) -> bool:
    if not src or dst is None:
        return False
    if pattern == "cycle":
        return len(src) >= 2
    return bool(dst) and not set(src) & set(dst)


def _named(part: str, ids: set[str]) -> tuple[str, ...] | None:
    """Give the component ids of a list, or None if the list has a different word."""
    out: list[str] = []
    for token in _TOKEN.findall(part):
        if token in ids:
            if token not in out:
                out.append(token)
        elif token.lower() not in FILL and token not in {",", "&"}:
            return None
    return tuple(out)


def _others(model: Model, src: Sequence[str], dst: Sequence[str]) -> tuple[str, ...]:
    """Give the components that are not actors and are not in src or dst, in model order."""
    named = set(src) | set(dst)
    return tuple(c.id for c in model.components if c.kind != "actor" and c.id not in named)


def _ids(values: Sequence[str]) -> str:
    if not values:
        return "()"
    inside = ", ".join(json.dumps(v) for v in values)
    return f"({inside},)" if len(values) == 1 else f"({inside})"


def _free(base: str, taken: set[str]) -> str:
    """Give the base id, or the base id with the lowest free number from 2."""
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"
