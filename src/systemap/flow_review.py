"""The flow review state compares the review digest of a flow with its source records.

A flow review digest contains the flow claim and the source records of the flow. Each
source record has the form `module[:symbol]@digest`, and the digest is the
`source_sha256` fact of the module. A review is current only when each record resolves
at this source snapshot. Then the digest in each record is the digest of the current
module source. Thus a change to a module in the source records makes the review stale:
the record does not resolve, and a record with the new digest gives a new review digest.

systemap 2.0.0 recorded a review digest of the claim only (`claim_digest`). Two digests
give the state `earlier`, with the label "review earlier than source tracking":

- the claim digest. This digest records no source. Only the 2.0 releases accept it
  (`claim_digest_accepted`). From 2.1.0, it is stale.
- the earlier-review digest (`earlier_digest`). `systemap refresh` and `systemap extract`
  write it one time in place of the claim digest. It records the source records at that
  time.

A review with the state `earlier` is current, but its digest does not identify the
examined source. After the one write, a change to the source records makes it stale.

This module reads only the model fields and the language-neutral `source_sha256` fact.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from systemap import __version__
from systemap.model import Flow, Meaning, source_parsed

CURRENT = "current"
EARLIER = "earlier"
STALE = "stale"
MISSING = "missing"
# The forms of a review digest that agree with the claim and the source records.
REVIEWED = (CURRENT, EARLIER)
# The label that a person reads for the state `earlier`.
EARLIER_LABEL = "review earlier than source tracking"

_DIGEST = re.compile(r"[0-9a-f]{64}")
# A claim digest from 2.0.0 is an earlier review only in the 2.0 releases. From 2.1.0, it
# is stale, because it records no source. Tests change VERSION.
CLAIM_DIGEST_LAST = (2, 0)
VERSION = __version__


def claim_digest_accepted() -> bool:
    """Tell if this version accepts a claim digest from 2.0.0 as an earlier review."""
    major, minor = (int(part) for part in VERSION.split(".")[:2])
    return (major, minor) <= CLAIM_DIGEST_LAST


def claim(flow: Flow, meaning: Meaning) -> tuple[str, ...]:
    """Give the flow claim: source, target, artifact, kind, relation, and the id if any."""
    out: tuple[str, ...] = (flow.src, flow.dst, flow.artifact, flow.kind, meaning.relation(flow))
    return out + ((flow.id,) if flow.id else ())


def claim_digest(flow: Flow, meaning: Meaning) -> str:
    """Give the digest of the flow claim only. Reviews before source tracking have it.

    The claim contains the id only for a flow with an id. Thus a flow without an id keeps
    the digest that it had before flow ids."""
    data = json.dumps(claim(flow, meaning), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _hash(flow: Flow, meaning: Meaning, earlier: bool) -> str:
    material: dict[str, Any] = {
        "claim": claim(flow, meaning),
        "source": sorted(flow.source_refs),
    }
    if earlier:
        material["earlier"] = EARLIER_LABEL
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def earlier_digest(flow: Flow, meaning: Meaning) -> str:
    """Give the earlier-review digest: the claim and the source records as written."""
    return _hash(flow, meaning, True)


def resolves(ref: str, facts: dict[str, Any]) -> bool:
    """Find if a source record agrees with the facts.

    The module must have a parsed record, and its `source_sha256` fact must be the digest
    of the record. A symbol must be a name of the module record.
    """
    location, marker, digest = ref.rpartition("@")
    if not marker or not _DIGEST.fullmatch(digest):
        return False
    module, colon, symbol = location.partition(":")
    record = facts.get("components", {}).get(module)
    if not isinstance(record, dict) or not source_parsed(record):
        return False
    if record.get("source_sha256") != digest:
        return False
    if not colon:
        return True
    names: Iterable[Any] = record.get("names", [])
    return bool(symbol) and any(
        item.get("name") == symbol for item in names if isinstance(item, dict)
    )


def digest(flow: Flow, meaning: Meaning, facts: dict[str, Any]) -> str | None:
    """Give the current review digest of a flow, or None.

    The result is None for a flow without source records, and for a flow with a source
    record that does not agree with the facts. Such a flow has no current review.
    """
    refs = flow.source_refs
    if not refs or not all(resolves(ref, facts) for ref in refs):
        return None
    return _hash(flow, meaning, False)


def form(flow: Flow, meaning: Meaning) -> str:
    """Give the state of the review digest against the claim and the source records as
    written. The facts are not used. `state` adds the examination against the facts.
    """
    if not flow.source_refs or not flow.review_digest:
        return MISSING
    if flow.review_digest == _hash(flow, meaning, False):
        return CURRENT
    if flow.review_digest == earlier_digest(flow, meaning):
        return EARLIER
    if claim_digest_accepted() and flow.review_digest == claim_digest(flow, meaning):
        return EARLIER
    return STALE


def state(flow: Flow, meaning: Meaning, facts: dict[str, Any]) -> str:
    """Give the review state of a flow: current, earlier, stale, or missing.

    `missing`: the flow has no source records or no review digest.
    `current`: the review digest is the current digest.
    `earlier`: the source records agree with the facts, and the review digest has a form
    from before source tracking.
    `stale`: all other cases, also a source record that does not agree with the facts.
    """
    found = form(flow, meaning)
    if found in REVIEWED and digest(flow, meaning, facts) is None:
        return STALE
    return found


def recorded_value(flow: Flow, meaning: Meaning) -> str:
    """Give the review digest as a component claim uses it.

    The one write of the earlier-review digest must not change a component digest. Thus
    an earlier-review digest gives the claim digest that it replaced.
    """
    if flow.review_digest and flow.review_digest == earlier_digest(flow, meaning):
        return claim_digest(flow, meaning)
    return flow.review_digest


def needs_record(flow: Flow, meaning: Meaning) -> bool:
    """Find if the review digest of a flow is a claim digest without the source records."""
    if not claim_digest_accepted():
        return False
    return bool(flow.source_refs) and flow.review_digest == claim_digest(flow, meaning)
