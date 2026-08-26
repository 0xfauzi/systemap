"""What the facts say about each flow: observed, external or declared.

The check verifies entries and interfaces against the code. It cannot
verify that an edge exists: a flow is a claim the agent wrote, and the
only record of which claims were read from the code and which were
inferred used to be a list in a chat. So every flow carries an evidence
state, computed here from the facts and never authored:

    observed ..... an import joins the two components' modules, in either
                   direction; or the flow's sentence or artifact names a
                   mechanism the repository lists under `[flows]
                   observed_by` (a subprocess, a queue, a file), and then
                   the state carries the mechanism's name
    external ..... an actor at either end: the edge is outside the code,
                   and the facts have nothing to say about it
    declared ..... nothing in the facts joins them: the map says so, the
                   code does not

A declared edge draws dashed on the page and in every figure, the panel
says so beside its sentence, and `systemap judgement` prints one line per
declared edge so the agent finds the evidence, names the mechanism in the
sentence, or removes the edge. The state is read at render and at check
time from the same function, so the drawing and the report cannot
disagree.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from systemap.model import Edge, Flow, Meaning, Model, claimed

OBSERVED = "observed"
EXTERNAL = "external"
DECLARED = "declared"
STATES = (OBSERVED, EXTERNAL, DECLARED)


@dataclass(frozen=True)
class Evidence:
    """One flow's evidence state, and the mechanism that observed it if one did."""

    state: str
    mechanism: str = ""

    @property
    def says(self) -> str:
        """The line the panel prints beside the flow's sentence."""
        if self.state == EXTERNAL:
            return "external: outside the code"
        if self.mechanism:
            return f"observed by: {self.mechanism}"
        if self.state == OBSERVED:
            return "observed: an import joins them"
        return "declared: no import behind it"


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
    """The evidence state of every flow, by edge."""
    joined = joined_by_import(model, facts)
    mechanisms = list(observed_by)
    out: dict[Edge, Evidence] = {}
    for f in model.flows:
        if model.kind_of(f.src) == "actor" or model.kind_of(f.dst) == "actor":
            out[f.edge] = Evidence(EXTERNAL)
        elif frozenset(f.edge) in joined:
            out[f.edge] = Evidence(OBSERVED)
        else:
            mechanism = mechanism_of(f, meaning, mechanisms)
            out[f.edge] = Evidence(OBSERVED, mechanism) if mechanism else Evidence(DECLARED)
    return out


def declared(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[Flow]:
    """Every flow the facts do not back, in model order."""
    states = of_model(model, meaning, facts, observed_by)
    return [f for f in model.flows if states[f.edge].state == DECLARED]
