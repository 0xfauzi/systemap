"""Hash the source and map claims examined for one component.

The digest records a value for source review. It does not show that a maintainer
examined the source. After source examination, a maintainer writes `Component.source_review`.
Refresh does not write this value automatically.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from systemap.model import Component, Journey, Meaning, Model, claimed, is_symbol


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
    names = set(claimed(card, components))
    names.update(pattern.partition(":")[0] for pattern in card.implemented_by if is_symbol(pattern))
    if not names:
        return None
    source = []
    for name in sorted(names):
        record = components.get(name)
        if not isinstance(record, dict) or record.get("parse_error"):
            return None
        digest = record.get("syntax_sha")
        if not isinstance(digest, str) or not digest:
            return None
        source.append((name, digest))
    return source


def _touches(journey: Journey, card_id: str) -> bool:
    """Find whether a sequence names this component in actors, measures, or flow endpoints."""
    return any(
        card_id in step.acts or card_id in step.measures or card_id in step.edge
        for step in journey.steps
    )


def _claims(card: Component, model: Model, meaning: Meaning) -> dict[str, Any]:
    """Collect semantic claims that make a new source review necessary after changes."""
    flows = [
        (
            flow.src,
            flow.dst,
            flow.artifact,
            flow.kind,
            flow.source_refs,
            flow.review_digest,
            meaning.relations.get(flow.edge, ""),
        )
        for flow in model.flows
        if card.id in flow.edge
    ]
    journeys = [
        dataclasses.asdict(journey) for journey in meaning.journeys if _touches(journey, card.id)
    ]
    invariants = [
        dataclasses.asdict(invariant)
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


def digest(card: Component, model: Model, meaning: Meaning, facts: dict[str, Any]) -> str | None:
    """Hash claimed parsed source and related semantic claims.

    Missing source records and parse errors prevent a digest.
    Formatting and comments do not change the parsed-source hash.
    """
    source = _source(card, facts)
    if source is None:
        return None
    material = {"source": source, "claims": _claims(card, model, meaning)}
    raw = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
