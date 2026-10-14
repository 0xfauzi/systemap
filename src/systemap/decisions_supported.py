"""The `supported` count of `systemap decisions status` counts only the current claims.

A store record with the verdict `supported` counts if its claim digest is the current
claim digest of its target, and the claim is closed:

- `source_review`: the component has a current source review, and its review digest is
  the recorded digest.
- `flow_review`: the flow has a current review, and its claim digest is the recorded digest.
- `judgement`: the line is a current judgement line, and it is not open.

A map change or a source change gives a different digest or opens the claim again. The
record then does not count. `decisions_store.Status.supported_records` gives the full
quantity of `supported` records, also for claims that are not current.

This module uses only the map claims, the language-neutral facts, and the judgement lines.
"""

from __future__ import annotations

import hashlib
from typing import Any

from systemap import card_review, flow_review, judgement_json, nest
from systemap.decisions import FLOW_REVIEW, JUDGEMENT, SOURCE_REVIEW, SUPPORTED
from systemap.flow_review import REVIEWED


def _card_digest(m: nest.Map, target: str, facts: dict[str, Any]) -> str | None:
    card = m.model.component(target)
    if card is None or card_review.state(card, m.model, m.meaning, facts) != card_review.CURRENT:
        return None
    return card_review.digest(card, m.model, m.meaning, facts)


def _flow_digest(m: nest.Map, target: str, facts: dict[str, Any]) -> str | None:
    flow = next((f for f in m.model.flows if f.key == target), None)
    if flow is None or flow_review.state(flow, m.meaning, facts) not in REVIEWED:
        return None
    return flow_review.digest(flow, m.meaning, facts)


def closed_digest(
    record: dict[str, Any], tree: nest.Tree, facts: dict[str, Any], judged: judgement_json.Judged
) -> str | None:
    """Give the current claim digest of the target of a record if the claim is closed."""
    kind, target, map_id = record.get("type"), record.get("target"), record.get("map")
    if not isinstance(target, str) or not isinstance(map_id, str):
        return None
    if kind == JUDGEMENT:
        closed = target in judged.lines and target not in judged.result.open
        return hashlib.sha256(target.encode("utf-8")).hexdigest() if closed else None
    if not tree.has(map_id):
        return None
    if kind == SOURCE_REVIEW:
        return _card_digest(tree.get(map_id), target, facts)
    if kind == FLOW_REVIEW:
        return _flow_digest(tree.get(map_id), target, facts)
    return None


def count(
    records: dict[str, dict[str, Any]],
    tree: nest.Tree,
    facts: dict[str, Any],
    judged: judgement_json.Judged,
) -> int:
    """Give the quantity of `supported` records whose claim is the current, closed claim."""
    return sum(
        1
        for record in records.values()
        if record.get("verdict") == SUPPORTED
        and record.get("digest") is not None
        and record.get("digest") == closed_digest(record, tree, facts, judged)
    )
