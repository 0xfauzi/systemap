"""Classify what supports each authored flow claim.

An import, shared module, or configured mechanism word shows a possible
connection. It does not establish direction, artifact, or execution. A
source-reviewed claim cites extracted modules at their source digests.
Reference resolution establishes that the cited source is present at that
snapshot. The reviewer remains responsible for judging its meaning.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from systemap.model import Edge, Flow, Meaning, Model, claimed, symbol_claims

OBSERVED = "observed"
STRUCTURAL = "structural"
EXTERNAL = "external"
DECLARED = "declared"
STATES = (OBSERVED, STRUCTURAL, EXTERNAL, DECLARED)


@dataclass(frozen=True)
class Evidence:
    """One flow's evidence state and the independently available evidence."""

    state: str
    mechanism: str = ""
    shared: bool = False
    import_present: bool = False
    source_refs: tuple[str, ...] = ()
    unresolved_refs: tuple[str, ...] = ()
    claim_changed: bool = False

    @property
    def says(self) -> str:
        """The line the panel prints beside the flow's sentence."""
        if self.state == EXTERNAL:
            return "external: outside the code"
        if self.state == OBSERVED:
            return "source reviewed: references resolve at this source snapshot"
        if self.claim_changed:
            return "source review pending: flow review digest is missing or changed"
        if self.unresolved_refs:
            return "source review pending: references do not resolve at this source snapshot"
        if self.import_present:
            return "import present: flow direction and artifact unreviewed"
        if self.shared:
            return "shared module: flow direction and artifact unreviewed"
        if self.mechanism:
            return f"mechanism declared: {self.mechanism}; flow unreviewed"
        return "declared: no import behind it"


def _resolves(ref: str, facts: dict[str, Any]) -> bool:
    """Does a module or symbol reference match this exact extracted source?"""
    location, marker, digest = ref.rpartition("@")
    if not marker or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    module, colon, symbol = location.partition(":")
    record = facts.get("components", {}).get(module)
    if not isinstance(record, dict) or record.get("parse_error"):
        return False
    source_hash = record.get("source_sha256")
    if source_hash != digest:
        return False
    if not colon:
        return True
    return bool(symbol) and any(
        item.get("name") == symbol for item in record.get("names", []) if isinstance(item, dict)
    )


def flow_claim_digest(flow: Flow, meaning: Meaning) -> str:
    """The digest a reviewer records for this flow's exact semantic claim."""
    claim = (flow.src, flow.dst, flow.artifact, flow.kind, meaning.relations.get(flow.edge, ""))
    data = json.dumps(claim, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _review(
    flow: Flow, meaning: Meaning, facts: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    refs = tuple(flow.source_refs)
    changed = bool(refs) and flow.review_digest != flow_claim_digest(flow, meaning)
    return refs, tuple(ref for ref in refs if not _resolves(ref, facts)), changed


def mentioned(name: str, text: str) -> bool:
    """Is `name` in `text` as a whole word, case blind?"""
    return re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", text.lower()) is not None


def owners(model: Model, facts: dict[str, Any]) -> dict[str, str]:
    """module -> the id of the component that claims it, for every claimed module."""
    components = facts.get("components", {})
    out: dict[str, str] = {}
    for c in model.components:
        for module in claimed(c, components):
            out.setdefault(module, c.id)
    return out


def joined_by_import(model: Model, facts: dict[str, Any]) -> set[frozenset[str]]:
    """Every pair of components an import joins, in either direction."""
    components = facts.get("components", {})
    owner = owners(model, facts)
    out: set[frozenset[str]] = set()
    for module, p in owner.items():
        for target in components.get(module, {}).get("uses", {}):
            q = owner.get(target)
            if q and q != p:
                out.add(frozenset((p, q)))
    return out


def sharing_a_module(model: Model, facts: dict[str, Any]) -> set[frozenset[str]]:
    """Every pair of components with a module in common.

    A symbol claim (`pkg.mod:name`) puts a card inside a module another
    card owns: a tool defined beside its agent, a part that lives in a
    neighbour's file. No import can join two cards in one module, so
    the shared module is the evidence.
    """
    owner = owners(model, facts)
    out: set[frozenset[str]] = set()
    for c in model.components:
        for module, _name in symbol_claims(c):
            p = owner.get(module)
            if p and p != c.id:
                out.add(frozenset((p, c.id)))
    return out


def mechanism_of(flow: Flow, meaning: Meaning, observed_by: Iterable[str]) -> str:
    """The first configured mechanism the flow's sentence or artifact names, or empty."""
    text = f"{flow.artifact}\n{meaning.relations.get(flow.edge, '')}"
    for name in observed_by:
        if mentioned(name, text):
            return name
    return ""


def of_model(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> dict[Edge, Evidence]:
    """The evidence state of every flow, by edge.

    Structural facts are kept even when a source review is present, so a
    caller can inspect them without mistaking them for semantic proof.
    """
    joined = joined_by_import(model, facts)
    shared = sharing_a_module(model, facts)
    mechanisms = list(observed_by)
    out: dict[Edge, Evidence] = {}
    for f in model.flows:
        import_present = frozenset(f.edge) in joined
        sharing = frozenset(f.edge) in shared
        mechanism = mechanism_of(f, meaning, mechanisms)
        refs, unresolved, claim_changed = _review(f, meaning, facts)
        if model.kind_of(f.src) == "actor" or model.kind_of(f.dst) == "actor":
            out[f.edge] = Evidence(EXTERNAL)
        else:
            state = (
                OBSERVED
                if refs and not unresolved and not claim_changed
                else STRUCTURAL
                if import_present or sharing or mechanism
                else DECLARED
            )
            out[f.edge] = Evidence(
                state, mechanism, sharing, import_present, refs, unresolved, claim_changed
            )
    return out


def declared(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[Flow]:
    """Every flow with no source review or structural evidence, in model order."""
    states = of_model(model, meaning, facts, observed_by)
    return [f for f in model.flows if states[f.edge].state == DECLARED]


def structural(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[Flow]:
    """Every flow with structural evidence but no resolved source review."""
    states = of_model(model, meaning, facts, observed_by)
    return [f for f in model.flows if states[f.edge].state == STRUCTURAL]
