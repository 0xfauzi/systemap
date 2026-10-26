"""The evidence classifier gives an evidence state for each flow claim.

An import, shared module, or mechanism word gives structural evidence. Structural
evidence does not give evidence of the flow direction, artifact, or execution. A source
record must resolve to the extracted source, and its review digest must agree with the
flow claim and the source records (`flow_review`). At least one source record must be in
a module of the source component or the target component of the flow.
"""

from __future__ import annotations

import hashlib
import pickle
import re
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from systemap import flow_review
from systemap.model import (
    Component,
    Edge,
    Flow,
    Meaning,
    Model,
    claimed,
    covers,
    is_symbol,
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
    earlier_review: bool = False

    @property
    def says(self) -> str:
        """This method gives the panel explanation for the flow evidence state."""
        if self.state == EXTERNAL:
            return "external: The endpoint is outside the source code."
        if self.state == OBSERVED and self.earlier_review:
            return (
                f"{flow_review.EARLIER_LABEL}: The source records agree with this source "
                "snapshot. The review digest does not identify the examined source."
            )
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


class ByFlow(dict[Edge | str, Evidence]):
    """The evidence of each flow.

    The key of a flow without an id is its pair `(SRC, DST)`, as before flow ids. The key
    of a flow with an id is the id. `of` gives the evidence of one flow. A pair also
    selects the evidence of a flow with an id if one flow connects the pair.
    """

    def __init__(self, flows: Iterable[Flow]) -> None:
        super().__init__()
        self.pairs: dict[Edge, list[Edge | str]] = {}
        for f in flows:
            self.pairs.setdefault(f.edge, []).append(slot(f))

    def of(self, flow: Flow) -> Evidence:
        return self[slot(flow)]

    def _pair_key(self, key: object) -> Edge | str | None:
        keys = self.pairs.get(key) if isinstance(key, tuple) else None
        return keys[0] if keys is not None and len(keys) == 1 else None

    def __missing__(self, key: object) -> Evidence:
        found = self._pair_key(key)
        if found is None or found == key:
            raise KeyError(key)
        return self[found]


def slot(flow: Flow) -> Edge | str:
    """This function gives the key of a flow in `ByFlow`: the id, or the pair without an id."""
    return flow.id or flow.edge


def _resolves(ref: str, facts: dict[str, Any]) -> bool:
    """This function resolves a module or symbol reference against the extracted source
    snapshot.
    """
    return flow_review.resolves(ref, facts)


def flow_claim_digest(flow: Flow, meaning: Meaning) -> str:
    """This function calculates the digest of the flow claim without the source records.

    A review from systemap 2.0.0 has this digest. `flow_review.digest` gives the
    current review digest."""
    return flow_review.claim_digest(flow, meaning)


def _review(
    flow: Flow, meaning: Meaning, facts: dict[str, Any], model: Model
) -> tuple[tuple[str, ...], tuple[str, ...], bool, bool]:
    refs = tuple(flow.source_refs)
    changed = bool(refs) and flow_review.form(flow, meaning) not in flow_review.REVIEWED
    ends = [c for c in model.components if c.id in flow.edge]
    unresolved, outside = check_refs(refs, ends, facts)
    no_endpoint = bool(refs) and bool(endpoint_claims(flow, model)) and outside == refs
    return refs, unresolved, changed, no_endpoint


def check_refs(
    refs: tuple[str, ...], cards: Iterable[Component], facts: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """This function examines source records against the facts and a set of components.

    It gives the records that do not resolve at this source snapshot, and the records in
    no module of the components. Flows and sequence steps use this same procedure. If no
    component has a module claim, no record is outside, because the rule does not apply.
    """
    components = facts.get("components", {})
    unresolved = tuple(ref for ref in refs if not _resolves(ref, facts))
    patterns = [p for card in cards for p in card.implemented_by]
    outside = tuple(
        ref
        for ref in refs
        if patterns and not any(_covers(p, ref_module(ref), components) for p in patterns)
    )
    return unresolved, outside


def ref_module(ref: str) -> str:
    """This function gives the module of a source record in `module[:symbol]@digest` form."""
    location = ref.rpartition("@")[0] or ref
    return location.partition(":")[0]


def _covers(pattern: str, module: str, components: Mapping[str, Any] | None) -> bool:
    """This function finds whether one implemented_by value puts the component in the module.

    The `package` fact of the module record gives its package. Without the records, the
    dotted module name gives the package."""
    if is_symbol(pattern):
        return pattern.partition(":")[0] == module
    return covers(pattern, module, components)


def endpoint_claims(flow: Flow, model: Model) -> tuple[str, ...]:
    """This function gives the implemented_by values of the two flow endpoints.

    An actor has no values, so a flow with an actor end gives the values of the other end.
    """
    return tuple(p for c in model.components if c.id in flow.edge for p in c.implemented_by)


def cites_an_endpoint(
    flow: Flow, model: Model, components: Mapping[str, Any] | None = None
) -> bool:
    """This function finds whether a source record of the flow is in a module of an endpoint.

    A symbol claim puts its component in the module of the symbol. If no endpoint has a
    module claim, no source record can be in an endpoint module, and the rule does not apply.
    """
    patterns = endpoint_claims(flow, model)
    modules = {ref_module(ref) for ref in flow.source_refs}
    return not patterns or any(_covers(p, m, components) for p in patterns for m in modules)


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
    text = f"{flow.artifact}\n{meaning.relation(flow)}"
    for name in observed_by:
        if mentioned(name, text):
            return name
    return ""


# The evidence of the last maps. One command renders the same map several times, and
# each render gives the evidence. A key is the digest of the pickle of all inputs, so a
# changed input gives a different key.
EVIDENCE_KEEP = 8
_T = TypeVar("_T")
_evidence: OrderedDict[str, ByFlow] = OrderedDict()


def remembered(
    cache: OrderedDict[str, _T], keep: int, inputs: object, calculate: Callable[[], _T]
) -> _T:
    """Give the cached result for these inputs, or calculate it and keep it.

    The key is the digest of the pickle of the inputs. If pickle cannot copy an input,
    for example a MappingProxyType field of a Meaning, the function calculates the result
    and does not keep it. The cache keeps the last `keep` results."""
    try:
        key = hashlib.blake2b(pickle.dumps(inputs, 5)).hexdigest()
    except (TypeError, AttributeError, pickle.PicklingError):
        return calculate()
    found = cache.get(key)
    if found is None:
        found = calculate()
        cache[key] = found
        while len(cache) > keep:
            cache.popitem(last=False)
    cache.move_to_end(key)
    return found


def of_model(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> ByFlow:
    """This function gives each flow evidence state by flow identifier.

    The result keeps structural facts separate from source evidence, even if the flow
    has a source review. If the inputs are equal to the inputs of an earlier call, the
    function gives a copy of the earlier result. Each Evidence record is frozen.
    """
    mechanisms = list(observed_by)
    found = remembered(
        _evidence,
        EVIDENCE_KEEP,
        (model, meaning, facts, mechanisms),
        lambda: _of_model(model, meaning, facts, mechanisms),
    )
    out = ByFlow(model.flows)
    out.update(found)
    return out


def clear_evidence() -> None:
    """Remove all entries from the cache of of_model()."""
    _evidence.clear()


def _of_model(
    model: Model, meaning: Meaning, facts: dict[str, Any], mechanisms: list[str]
) -> ByFlow:
    joined = joined_by_import(model, facts)
    shared = sharing_a_module(model, facts)
    out = ByFlow(model.flows)
    for f in model.flows:
        import_present = frozenset(f.edge) in joined
        sharing = frozenset(f.edge) in shared
        mechanism = mechanism_of(f, meaning, mechanisms)
        refs, unresolved, claim_changed, no_endpoint = _review(f, meaning, facts, model)
        earlier = bool(refs) and flow_review.form(f, meaning) == flow_review.EARLIER
        if model.kind_of(f.src) == "actor" or model.kind_of(f.dst) == "actor":
            # The state stays external. The source records and their examination stay
            # in the record for the page and for `systemap review`.
            out[slot(f)] = Evidence(
                EXTERNAL,
                source_refs=refs,
                unresolved_refs=unresolved,
                claim_changed=claim_changed,
                no_endpoint_ref=no_endpoint,
                earlier_review=earlier,
            )
        else:
            state = (
                OBSERVED
                if refs and not unresolved and not claim_changed and not no_endpoint
                else STRUCTURAL
                if import_present or sharing or mechanism
                else DECLARED
            )
            out[slot(f)] = Evidence(
                state,
                mechanism,
                sharing,
                import_present,
                refs,
                unresolved,
                claim_changed,
                no_endpoint,
                earlier,
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
    return [f for f in model.flows if states.of(f).state == DECLARED]


def structural(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[Flow]:
    """This function gives flows with structural evidence but no resolved source review."""
    states = of_model(model, meaning, facts, observed_by)
    return [f for f in model.flows if states.of(f).state == STRUCTURAL]
