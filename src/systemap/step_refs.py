"""The source records of sequence steps.

A step can have `source_refs` in the same `module[:symbol]@digest` form as a flow. The
flow procedure `evidence.check_refs` examines them. Each record must resolve at the
current source snapshot. Each record must also be in a module of an acting or measured
component of the step. A flow must have one record in an endpoint module, but a step
must have each record in a module of its components. If no acting or measured component
has a module claim, each record is in no module of the step components.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from systemap import evidence
from systemap.model import Component, Meaning, Model

KIND = "step source"


def reasons(refs: tuple[str, ...], cards: Iterable[Component], facts: dict[str, Any]) -> list[str]:
    """Give one reason for each record that does not resolve or is outside the components."""
    members = list(cards)
    unresolved, outside = evidence.check_refs(refs, members, facts)
    named = ", ".join(c.id for c in members if c.implemented_by)
    out = [
        f"cites {_location(ref)}, which does not resolve in the current source"
        for ref in unresolved
    ]
    if not named:
        return out + [
            f"cites {_location(ref)}, but no acting or measured component has a module claim"
            for ref in refs
        ]
    out += [f"cites {_location(ref)}, which is in no module of {named}" for ref in outside]
    return out


def problems(model: Model, meaning: Meaning, facts: dict[str, Any]) -> list[str]:
    """Give one judgement line for each step record that does not agree with the rule.

    Without facts, the report gives no line, because no record can resolve.
    """
    if not facts.get("components"):
        return []
    cards = {c.id: c for c in model.components}
    out: list[str] = []
    for journey in meaning.journeys:
        for k, step in enumerate(journey.steps, start=1):
            members = [cards[c] for c in dict.fromkeys((*step.acts, *step.measures)) if c in cards]
            out += [
                f"{KIND}: journey {journey.id} step {k} {reason}. Cite a current record in a "
                "module of an acting or measured component, or change the step."
                for reason in reasons(step.source_refs, members, facts)
            ]
    return out


def _location(ref: str) -> str:
    """Give the record without its source digest: `module[:symbol]`."""
    return ref.rpartition("@")[0] or ref
