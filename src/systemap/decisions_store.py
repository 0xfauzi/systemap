"""The decision store records the verdicts of a coding agent in `.systemap/decisions.json`.

The store is local to one working copy, and Git does not record it. It keeps one record
for each request key: the claim digest, the last verdict, the quantity of `contradicted`
results, and the last summary. A different claim digest resets the record.

- `supported` records the result. The model or the configuration gets the review or the answer.
- `contradicted` adds one attempt. The agent must correct the map and submit again.
  At `[decisions] max_contradicted` attempts, the request becomes unknown.
- `insufficient_evidence` makes the request unknown at once.

An unknown request is not a pass. It stays unknown until its claim digest changes.
Delete the store to start a new session. The `supported` count then starts at zero.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap.decisions import CONTRADICTED, INSUFFICIENT, SUPPORTED, Request

STORE = ".systemap/decisions.json"
VERSION = 1
PENDING = "pending"
UNKNOWN = "unknown"


def path(root: Path) -> Path:
    return root / STORE


def load(root: Path) -> dict[str, dict[str, Any]]:
    """Read the records by request key. A missing or unreadable store gives no records."""
    try:
        data = json.loads(path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return {}
    records = data.get("records", {})
    if not isinstance(records, dict):
        return {}
    return {k: v for k, v in records.items() if isinstance(v, dict)}


def save(root: Path, records: dict[str, dict[str, Any]]) -> None:
    """Write the store in one replacement, so that a stopped command leaves a complete file."""
    target = path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"version": VERSION, "records": records}, indent=2, sort_keys=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".decisions-", suffix=".json")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(text + "\n")
    os.replace(temporary, target)


def current(records: dict[str, dict[str, Any]], request: Request) -> dict[str, Any] | None:
    """Give the record of a request if its claim digest is the current digest."""
    record = records.get(request.key)
    if record is None or record.get("digest") != request.digest:
        return None
    return record


def attempts(records: dict[str, dict[str, Any]], request: Request) -> int:
    record = current(records, request)
    value = record.get("attempts", 0) if record else 0
    return value if isinstance(value, int) else 0


def state(records: dict[str, dict[str, Any]], request: Request) -> str:
    """Give `unknown` for a request with an unknown record at the current digest, or `pending`."""
    record = current(records, request)
    return UNKNOWN if record and record.get("state") == UNKNOWN else PENDING


def record(
    records: dict[str, dict[str, Any]],
    request: Request,
    verdict: str,
    summary: str,
    limit: int,
) -> str:
    """Record one valid result. Give the new state of the request: its verdict, or `unknown`."""
    count = attempts(records, request)
    if verdict == CONTRADICTED:
        count += 1
    new = (
        UNKNOWN
        if verdict == INSUFFICIENT or (verdict == CONTRADICTED and count >= limit)
        else verdict
    )
    records[request.key] = {
        "id": request.id,
        "type": request.type,
        "map": request.map,
        "target": request.target,
        "claim": request.claim,
        "digest": request.digest,
        "verdict": verdict,
        "attempts": count,
        "state": new,
        "summary": summary,
    }
    return new


@dataclass(frozen=True)
class Status:
    """The pending requests, the unknown requests with their records, and the supported count."""

    pending: list[Request]
    unknown: list[tuple[Request, dict[str, Any]]]
    supported: int


def status(records: dict[str, dict[str, Any]], requests: list[Request]) -> Status:
    """Separate the current requests into pending and unknown requests.

    `supported` counts the supported results in the store, also for claims that a later
    change opened again.
    """
    pending: list[Request] = []
    unknown: list[tuple[Request, dict[str, Any]]] = []
    for request in requests:
        found = current(records, request)
        if found and found.get("state") == UNKNOWN:
            unknown.append((request, found))
        else:
            pending.append(request)
    supported = sum(1 for r in records.values() if r.get("verdict") == SUPPORTED)
    return Status(pending, unknown, supported)
