"""Hash the source and map claims examined for one component, and give its review state.

The digest records a value for source review. It does not show that a maintainer
examined the source. After source examination, a maintainer writes `Component.source_review`.
Refresh does not write this value automatically.

`state` is the one procedure that compares `source_review` with the current digest.
Delta and judgement both use it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from systemap import contract, flow_review
from systemap.flow_ids import journey_record, resolve
from systemap.model import (
    Component,
    Journey,
    Meaning,
    Model,
    claimed,
    is_symbol,
    source_parsed,
)


def _source(card: Component, facts: dict[str, Any]) -> list[tuple[str, str]] | None:
    """Get parsed source for every claimed module, or None without a usable snapshot."""
    components = facts.get("components", {})
    if not isinstance(components, dict):
        return None
    explicit = {
        pattern
        for pattern in card.implemented_by
        if not pattern.endswith(".*") and not is_symbol(pattern)
    }
    if not explicit <= components.keys():
        return None
    names = source_modules(card, components)
    if not names:
        return None
    source = []
    for name in sorted(names):
        record = components.get(name)
        if not isinstance(record, dict) or not source_parsed(record):
            return None
        digest = record.get("syntax_sha")
        if not isinstance(digest, str) or not digest:
            return None
        source.append((name, digest))
    return source


def source_modules(card: Component, components: dict[str, Any]) -> set[str]:
    """Give the modules of the source digest: the claimed modules and the symbol claim modules.

    A symbol claim module is in the result also when the records do not contain it.
    Delta uses the same selection to find the components with changed source."""
    names = set(claimed(card, components))
    names.update(pattern.partition(":")[0] for pattern in card.implemented_by if is_symbol(pattern))
    return names


def touches(journey: Journey, card_id: str) -> bool:
    """Find if a sequence names this component in `starts`, actors, measures, or flow
    endpoints.

    This is the one rule that selects the sequences of a component claim. The decision
    requests and the drift questions use it also.
    """
    return journey.starts == card_id or any(
        card_id in step.acts or card_id in step.measures or card_id in step.edge
        for step in journey.steps
    )


def _location(ref: str) -> str:
    """Give a source record without its source digest: `module[:symbol]`."""
    return ref.rpartition("@")[0] or ref


def _claims(
    card: Component, model: Model, meaning: Meaning, reviews: bool = True
) -> dict[str, Any]:
    """Collect semantic claims that make a new source review necessary after changes.

    With `reviews` false, the flows have no review digest, and the source records of the
    flows have no source digest. These digests record an examination, not a claim. The
    one write of an earlier-review digest does not change the claims (`flow_review`).
    """
    meaning = resolve(model, meaning)
    # A flow without an id gives the same claim as before flow ids.
    flows = [
        (
            flow.src,
            flow.dst,
            flow.artifact,
            flow.kind,
            flow.source_refs if reviews else tuple(_location(ref) for ref in flow.source_refs),
            flow_review.recorded_value(flow, meaning) if reviews else "",
            meaning.relation(flow),
            *((flow.id,) if flow.id else ()),
        )
        for flow in model.flows
        if card.id in flow.edge
    ]
    journeys = [
        journey_record(journey) for journey in meaning.journeys if touches(journey, card.id)
    ]
    invariants = [
        contract.claim(invariant)
        for invariant in model.invariants
        if not invariant.governs or card.id in invariant.governs
    ]
    return {
        "card": (
            card.id,
            card.does,
            card.interface,
            card.implemented_by,
            card.entry,
            card.kind,
            card.note,
            card.calls_model,
            card.map,
            meaning.plain.get(card.id, ""),
        ),
        "flows": sorted(flows),
        "journeys": sorted(journeys, key=lambda journey: journey["id"]),
        "invariants": sorted(invariants, key=lambda invariant: invariant["n"]),
    }


def claims(card: Component, model: Model, meaning: Meaning) -> dict[str, Any]:
    """Give the map claims of a component without the review values.

    The claims are the component fields, its plain name, and the flows, sequences, and
    invariants that name it. A sequence also names the component in its `starts` field.
    `source_review`, the flow review digests, and the source digests in the flow source
    records are not claims.
    """
    return _claims(card, model, meaning, reviews=False)


def digest(card: Component, model: Model, meaning: Meaning, facts: dict[str, Any]) -> str | None:
    """Hash claimed parsed source and related semantic claims.

    Missing source records and source that did not parse completely prevent a digest.
    Formatting and comments do not change the parsed-source hash.
    """
    source = _source(card, facts)
    if source is None:
        return None
    material = {"source": source, "claims": _claims(card, model, meaning)}
    raw = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


MISSING = "missing"
STALE = "stale"
CURRENT = "current"
STATES = (CURRENT, STALE, MISSING)


def state(card: Component, model: Model, meaning: Meaning, facts: dict[str, Any]) -> str:
    """Give the review state of one component: missing, stale, or current.

    `missing`: the component has no `source_review` value.
    `stale`: the `source_review` value is not the current digest. A component without a
    current digest, for example after a parse error, also has this state.
    `current`: the `source_review` value is the current digest.
    """
    if not card.source_review:
        return MISSING
    return CURRENT if card.source_review == digest(card, model, meaning, facts) else STALE
