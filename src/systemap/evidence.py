"""The evidence classifier gives an evidence state for each flow claim.

An import, shared module, or mechanism word gives structural evidence. Structural
evidence does not give evidence of the flow direction, artifact, or execution. A source
record must resolve to the extracted source, and its review digest must agree with the
flow claim. At least one source record must be in a module of the source component or
the target component of the flow.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from systemap.model import (
    Edge,
    Flow,
    Meaning,
    Model,
    claimed,
    is_symbol,
    module_matches,
    source_parsed,
    symbol_claims,
)

OBSERVED = "observed"
STRUCTURAL = "structural"
EXTERNAL = "external"
DECLARED = "declared"
STATES = (OBSERVED, STRUCTURAL, EXTERNAL, DECLARED)
# The words that a person reads for each stored state. The stored values are identifiers.
# Readers can take "observed" to mean runtime observation, so the text does not use it.
READER_TEXT = {
    OBSERVED: "current source review",
    STRUCTURAL: "an import, a shared module, or a configured mechanism",
    EXTERNAL: "an actor endpoint",
    DECLARED: "no source review or structural evidence",
}


@dataclass(frozen=True)
class Evidence:
    """This record contains the flow evidence state and available structural and source
    evidence.
    """

    state: str
    mechanism: str = ""
    shared: bool = False
    import_present: bool = False
    source_refs: tuple[str, ...] = ()
    unresolved_refs: tuple[str, ...] = ()
    claim_changed: bool = False
    no_endpoint_ref: bool = False

    @property
    def says(self) -> str:
        """This method gives the panel explanation for the flow evidence state."""
        if self.state == EXTERNAL:
            return "external: The endpoint is outside the source code."
        if self.state == OBSERVED:
            return "current source review: The source records agree with this source snapshot."
        if self.pending:
            return f"source review pending: {self.pending}"
        if self.import_present:
            return "import present: The flow direction and artifact have no source review."
        if self.shared:
            return "shared module: The flow direction and artifact have no source review."
        if self.mechanism:
            return f"mechanism declared: {self.mechanism}. The flow has no source review."
        return "declared: The flow has no import evidence."

    @property
    def pending(self) -> str:
        """This property gives the first reason that the source records do not give evidence.

        It gives an empty string for a flow without this problem.
        """
        reasons = (
            (self.claim_changed, "The flow review digest is missing or different."),
            (bool(self.unresolved_refs), "The references do not resolve at this source snapshot."),
            (self.no_endpoint_ref, "No source record is in a module of a flow endpoint."),
        )
        return next((text for found, text in reasons if found), "")


def _resolves(ref: str, facts: dict[str, Any]) -> bool:
    """This function resolves a module or symbol reference against the extracted source
    snapshot.
    """
    location, marker, digest = ref.rpartition("@")
    if not marker or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    module, colon, symbol = location.partition(":")
    record = facts.get("components", {}).get(module)
    if not isinstance(record, dict) or not source_parsed(record):
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
    """This function calculates the digest for the exact flow claim."""
    claim = (flow.src, flow.dst, flow.artifact, flow.kind, meaning.relations.get(flow.edge, ""))
    data = json.dumps(claim, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _review(
    flow: Flow, meaning: Meaning, facts: dict[str, Any], model: Model
) -> tuple[tuple[str, ...], tuple[str, ...], bool, bool]:
    refs = tuple(flow.source_refs)
    changed = bool(refs) and flow.review_digest != flow_claim_digest(flow, meaning)
    unresolved = tuple(ref for ref in refs if not _resolves(ref, facts))
    return refs, unresolved, changed, bool(refs) and not cites_an_endpoint(flow, model)


def ref_module(ref: str) -> str:
    """This function gives the module of a source record in `module[:symbol]@digest` form."""
    location = ref.rpartition("@")[0] or ref
    return location.partition(":")[0]


def _covers(pattern: str, module: str) -> bool:
    """This function finds whether one implemented_by value puts the component in the module."""
    if is_symbol(pattern):
        return pattern.partition(":")[0] == module
    return module_matches(pattern, module)


def endpoint_claims(flow: Flow, model: Model) -> tuple[str, ...]:
    """This function gives the implemented_by values of the two flow endpoints.

    An actor has no values, so a flow with an actor end gives the values of the other end.
    """
    return tuple(p for c in model.components if c.id in flow.edge for p in c.implemented_by)


def cites_an_endpoint(flow: Flow, model: Model) -> bool:
    """This function finds whether a source record of the flow is in a module of an endpoint.

    A symbol claim puts its component in the module of the symbol. If no endpoint has a
    module claim, no source record can be in an endpoint module, and the rule does not apply.
    """
    patterns = endpoint_claims(flow, model)
    modules = {ref_module(ref) for ref in flow.source_refs}
    return not patterns or any(_covers(p, m) for p in patterns for m in modules)


def mentioned(name: str, text: str) -> bool:
    """This function finds a full word in the text without case distinctions."""
    return re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", text.lower()) is not None


def owners(model: Model, facts: dict[str, Any]) -> dict[str, str]:
    """This function assigns each claimed module to its component ID."""
    components = facts.get("components", {})
    out: dict[str, str] = {}
    for c in model.components:
        for module in claimed(c, components):
            out.setdefault(module, c.id)
    return out


def joined_by_import(model: Model, facts: dict[str, Any]) -> set[frozenset[str]]:
    """This function gives pairs of components with imports in either direction."""
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
    """This function gives pairs of components with a shared module.

    A symbol claim can put one component inside a module that another component owns.
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
    """This function finds the initial configured mechanism in the flow description or
    artifact.
    """
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
    """This function gives each flow evidence state by edge.

    The result keeps structural facts separate from source evidence, even if the flow
    has a source review.
    """
    joined = joined_by_import(model, facts)
    shared = sharing_a_module(model, facts)
    mechanisms = list(observed_by)
    out: dict[Edge, Evidence] = {}
    for f in model.flows:
        import_present = frozenset(f.edge) in joined
        sharing = frozenset(f.edge) in shared
        mechanism = mechanism_of(f, meaning, mechanisms)
        refs, unresolved, claim_changed, no_endpoint = _review(f, meaning, facts, model)
        if model.kind_of(f.src) == "actor" or model.kind_of(f.dst) == "actor":
            out[f.edge] = Evidence(EXTERNAL)
        else:
            state = (
                OBSERVED
                if refs and not unresolved and not claim_changed and not no_endpoint
                else STRUCTURAL
                if import_present or sharing or mechanism
                else DECLARED
            )
            out[f.edge] = Evidence(
                state,
                mechanism,
                sharing,
                import_present,
                refs,
                unresolved,
                claim_changed,
                no_endpoint,
            )
    return out


def declared(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[Flow]:
    """This function gives flows without source reviews or structural evidence in model
    order.
    """
    states = of_model(model, meaning, facts, observed_by)
    return [f for f in model.flows if states[f.edge].state == DECLARED]


def structural(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[Flow]:
    """This function gives flows with structural evidence but no resolved source review."""
    states = of_model(model, meaning, facts, observed_by)
    return [f for f in model.flows if states[f.edge].state == STRUCTURAL]
