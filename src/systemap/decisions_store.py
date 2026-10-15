"""The decision store records the verdicts of a coding agent in `.systemap/decisions.json`.

The store is local to one working copy, and Git does not record it. It keeps one record
for each target: the request type, the map, and the identity of the target (the component
ID, the flow, or the finding kind and the names of a judgement line). The record has the
claim digest, the digests of the source files, the last verdict, the quantity of
`contradicted` results, the quantity of `insufficient_evidence` results, the last
summary, and the history of all results for the target.

- `supported` records the result. The model or the configuration gets the review or the
  answer. The two counts go back to zero.
- `contradicted` adds one attempt. The agent must correct the map and submit again.
  At `[decisions] max_contradicted` attempts, the request becomes unknown.
- `insufficient_evidence` adds one to its count. The agent can examine more of the
  source and submit again. At `MAX_INSUFFICIENT` results, the request becomes unknown.

The limits stop work that occurs again and again. They do not stop an agent that sends
`supported` for a claim that it wrote. Thus the history keeps each result, and
`systemap decisions status` gives each result.

A change of the map claim does not reset the counts, so a repair loop stops at the limit.
A change of a source file of the target resets the counts. A file that only the record or
only the current request has is a change of the map claim, not a change of the source.
An unknown request is not a pass. It stays unknown until the source of its target changes.
Delete the store to start a new session. The counts and the history then start again.
A store that does not contain correct JSON, or that has a different version or form, gives
`file_write.RefusedFile`. It is not read as an empty store.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import file_write
from systemap.decisions import CONTRADICTED, INSUFFICIENT, SUPPORTED, Request

STORE = ".systemap/decisions.json"
VERSION = 1
PENDING = "pending"
UNKNOWN = "unknown"
# A limit on the work, not a measured value: the quantity of `insufficient_evidence`
# results for one target and source before the request becomes unknown. The agent can
# send one more result after the first result.
MAX_INSUFFICIENT = 2
INSUFFICIENT_FIELD = "insufficient"


def path(root: Path) -> Path:
    return root / STORE


def load(root: Path) -> dict[str, dict[str, Any]]:
    """Read the records by request key. A missing store gives no records.

    A link out of the repository (at the file or at a folder), a FIFO, a device, a read
    error, a file that is not UTF-8 text, a file without correct JSON, and a file with a
    different version or form give `file_write.RefusedFile` with the cause. They do not give an
    empty store, because the counts would then start at zero.
    """
    try:
        text = file_write.read_text(root, path(root))
        data = json.loads(text) if text is not None else {"version": VERSION, "records": {}}
    except UnicodeError as exc:
        raise file_write.RefusedFile(path(root), f"it is not UTF-8 text: {exc}") from exc
    except json.JSONDecodeError as exc:
        cause = f"it does not contain correct JSON: {exc}"
        raise file_write.RefusedFile(path(root), cause) from exc
    except OSError as exc:
        raise file_write.RefusedFile(path(root), f"the command cannot read it: {exc}") from exc
    records = data.get("records") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("version") != VERSION
        or not isinstance(records, dict)
    ):
        raise file_write.RefusedFile(
            path(root), f"it has a different version or form. The version must be {VERSION}"
        )
    return {k: v for k, v in records.items() if isinstance(v, dict)}


def save(root: Path, records: dict[str, dict[str, Any]]) -> None:
    """Write the store in one replacement, so that a stopped command leaves a complete file.

    The store and its folder must be in the repository (`file_write`)."""
    text = json.dumps({"version": VERSION, "records": records}, indent=2, sort_keys=True)
    file_write.write_atomic(root, path(root), text + "\n")


def _same_source(record: dict[str, Any], request: Request) -> bool:
    """Find if each source file of the request that the record has keeps its digest."""
    recorded = record.get("files")
    if not isinstance(recorded, dict):
        return False
    return all(recorded.get(f.file, f.sha256) == f.sha256 for f in request.files)


def current(records: dict[str, dict[str, Any]], request: Request) -> dict[str, Any] | None:
    """Give the record of the target of a request if the source of the target did not change."""
    record = records.get(request.key)
    if record is None or not _same_source(record, request):
        return None
    return record


def _count(records: dict[str, dict[str, Any]], request: Request, field: str) -> int:
    record = current(records, request)
    value = record.get(field, 0) if record else 0
    return value if isinstance(value, int) else 0


def attempts(records: dict[str, dict[str, Any]], request: Request) -> int:
    """Give the quantity of `contradicted` results for the current source of the target."""
    return _count(records, request, "attempts")


def insufficient(records: dict[str, dict[str, Any]], request: Request) -> int:
    """Give the quantity of `insufficient_evidence` results for the current source."""
    return _count(records, request, INSUFFICIENT_FIELD)


def state(records: dict[str, dict[str, Any]], request: Request) -> str:
    """Give `unknown` for a request with an unknown record at the current source, or `pending`."""
    record = current(records, request)
    return UNKNOWN if record and record.get("state") == UNKNOWN else PENDING


def verdict(records: dict[str, dict[str, Any]], request: Request) -> str:
    """Give `unknown`, the recorded state of the current claim, or an empty string."""
    record = current(records, request)
    if record is None:
        return ""
    if record.get("state") == UNKNOWN or record.get("digest") == request.digest:
        return str(record.get("state", ""))
    return ""


def history(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Give the recorded results of a target. A record of systemap 2.0.0 has no history."""
    value = record.get("history")
    return [entry for entry in value if isinstance(entry, dict)] if isinstance(value, list) else []


def _new_state(verdict: str, contradicted: int, insufficient: int, limit: int) -> str:
    if verdict == CONTRADICTED and contradicted >= limit:
        return UNKNOWN
    if verdict == INSUFFICIENT and insufficient >= MAX_INSUFFICIENT:
        return UNKNOWN
    return verdict


def record(
    records: dict[str, dict[str, Any]],
    request: Request,
    verdict: str,
    summary: str,
    limit: int,
    citations: list[dict[str, Any]] | None = None,
) -> str:
    """Record one valid result. Give the new state of the request: its verdict, or `unknown`.

    The history keeps each result, also after a change of the source of the target."""
    supported = verdict == SUPPORTED
    contradicted = 0 if supported else attempts(records, request) + int(verdict == CONTRADICTED)
    weak = 0 if supported else insufficient(records, request) + int(verdict == INSUFFICIENT)
    new = _new_state(verdict, contradicted, weak, limit)
    entry = {
        "claim_digest": request.digest,
        "verdict": verdict,
        "summary": summary,
        "citations": citations or [],
    }
    records[request.key] = {
        "id": request.id,
        "type": request.type,
        "map": request.map,
        "target": request.target,
        "claim": request.claim,
        "digest": request.digest,
        "files": {f.file: f.sha256 for f in request.files},
        "verdict": verdict,
        "attempts": contradicted,
        INSUFFICIENT_FIELD: weak,
        "state": new,
        "summary": summary,
        "history": [*history(records.get(request.key, {})), entry],
    }
    return new


@dataclass(frozen=True)
class Status:
    """The pending requests, the unknown requests with their records, and the quantity of
    `supported` records in the store, also for claims that are not current."""

    pending: list[Request]
    unknown: list[tuple[Request, dict[str, Any]]]
    supported_records: int


def status(records: dict[str, dict[str, Any]], requests: list[Request]) -> Status:
    """Separate the current requests into pending and unknown requests.

    `supported_records` counts the supported results in the store, also for claims that a
    later change opened again. `decisions_supported.count` counts only the current claims.
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
