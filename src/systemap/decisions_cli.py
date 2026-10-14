"""The `systemap decisions` commands give the semantic requests to a coding agent.

- `systemap decisions pending [--json]` gives the open requests.
- `systemap decisions submit FILE` examines and records the results of the agent.
- `systemap decisions status [--json]` gives the counts, the unknown requests, and the
  history of the verdicts.

The agent operates in its current session. The commands send no request to a model and
ask no person. An unknown request is never a pass: the text does not say that its claim
is correct, `systemap decisions status` exits 1, and `systemap judgement` shows it. The
text gives the CI result: an open judgement line of the claim makes
`systemap judgement --strict` exit 1.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from systemap import (
    config,
    decisions,
    decisions_store,
    decisions_submit,
    decisions_supported,
    judgement_json,
    nest,
)
from systemap.decisions import VERDICTS, Request

# Version 2 adds `max_insufficient` and `requests[].insufficient` to `pending`. It adds
# `supported_records` and `records` to `status`, and `supported` counts only the current
# claims. Each unknown request has `insufficient`, `open_lines`, and `history`.
SCHEMA_VERSION = 2


def _attempts(snap: decisions_submit.Snapshot, request: Request) -> int:
    return decisions_store.attempts(snap.records, request)


def pending_payload(snap: decisions_submit.Snapshot) -> dict[str, Any]:
    """Give the JSON object of `decisions pending`."""
    status = snap.status()
    return {
        "schema_version": SCHEMA_VERSION,
        "verdicts": list(VERDICTS),
        "max_contradicted": snap.cfg.max_contradicted,
        "max_insufficient": decisions_store.MAX_INSUFFICIENT,
        "requests": [
            {
                **request.row(),
                "attempts": _attempts(snap, request),
                "insufficient": decisions_store.insufficient(snap.records, request),
            }
            for request in status.pending
        ],
        "unknown": len(status.unknown),
    }


def pending_text(snap: decisions_submit.Snapshot) -> list[str]:
    """Give the text of `decisions pending` for a person or an agent."""
    status = snap.status()
    limit = snap.cfg.max_contradicted
    out = [f"decisions: {len(status.pending)} pending, {len(status.unknown)} unknown"]
    for request in status.pending:
        claim = request.claim.splitlines()
        out += [f"request {request.id}", f"  type: {request.type}", f"  claim: {claim[0]}"]
        out += [f"         {row}" for row in claim[1:]]
        out.append(f"  claim digest: {request.digest or 'none'}")
        out.append(f"  contradicted verdicts: {_attempts(snap, request)} of {limit}")
        weak = decisions_store.insufficient(snap.records, request)
        out.append(
            f"  insufficient_evidence verdicts: {weak} of {decisions_store.MAX_INSUFFICIENT}"
        )
        out += [
            f"  file: {f.file} {f'refused: {f.problem}' if f.problem else f'sha256 {f.sha256}'}"
            for f in request.files
        ]
        if request.blocked:
            out.append(f"  blocked: {request.blocked}")
    if status.pending:
        out.append(f"verdicts: {', '.join(VERDICTS)}")
        out.append("Examine the source code of each decision request.")
        out.append("Then use systemap decisions submit FILE.")
    return out


def unknown_rows(
    status: decisions_store.Status, tree: nest.Tree, judged: judgement_json.Judged
) -> list[dict[str, Any]]:
    """Give one object for each unknown request, with its last verdict, its history, and
    its open judgement lines."""
    return [
        {
            "id": request.id,
            "type": request.type,
            "map": request.map,
            "target": request.target,
            "claim": request.claim,
            "claim_digest": request.digest,
            "verdict": record.get("verdict", ""),
            "attempts": record.get("attempts", 0),
            "insufficient": record.get(decisions_store.INSUFFICIENT_FIELD, 0),
            "summary": record.get("summary", ""),
            "open_lines": decisions.open_lines(request, tree, judged),
            "history": decisions_store.history(record),
        }
        for request, record in status.unknown
    ]


def record_rows(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Give one object for each target in the store, with each recorded verdict."""
    keys = ("id", "type", "map", "target", "state")
    return [
        {**{k: record.get(k, "") for k in keys}, "history": decisions_store.history(record)}
        for _key, record in sorted(records.items())
    ]


def status_payload(snap: decisions_submit.Snapshot) -> dict[str, Any]:
    status = snap.status()
    return {
        "schema_version": SCHEMA_VERSION,
        "pending": len(status.pending),
        "supported": decisions_supported.count(snap.records, snap.tree, snap.facts, snap.judged),
        "supported_records": status.supported_records,
        "unknown": len(status.unknown),
        "unknown_requests": unknown_rows(status, snap.tree, snap.judged),
        "records": record_rows(snap.records),
    }


REVIEW_POLICY = (
    "  With [judgement] require_reviews = true, a component without a source review "
    "gives an open judgement line."
)


def unknown_text(rows: list[dict[str, Any]]) -> list[str]:
    """Give the text rows for unknown requests. The text never says that a claim is correct.

    Each request gives its CI result: an open judgement line of the claim makes
    `judgement --strict` exit 1. A claim without an open line does not.
    """
    out = []
    for row in rows:
        out.append(f"unknown request {row['id']}: {row['claim'].splitlines()[0]}")
        out.append(f"  last verdict: {row['verdict']}. Last summary: {row['summary']}")
        out += [f"  open line: {line}" for line in row["open_lines"]]
        out.append(f"  CI: {decisions_submit.ci_result(row['open_lines'])}")
        if row["type"] == decisions.SOURCE_REVIEW and not row["open_lines"]:
            out.append(REVIEW_POLICY)
    if rows:
        out.append(
            "These claims have no decision. systemap decisions status exits 1 while a "
            "decision request is unknown."
        )
    return out


def _cited(citations: Any) -> str:
    rows = [c for c in citations if isinstance(c, dict)] if isinstance(citations, list) else []
    found = [f"{c.get('file')}:{c.get('start_line')}-{c.get('end_line')}" for c in rows]
    return ", ".join(found) or "none"


def history_text(rows: list[dict[str, Any]]) -> list[str]:
    """Give each recorded verdict of each target in the store."""
    out = []
    for row in rows:
        if not row["history"]:
            continue
        out.append(f"  {row['id']} (state: {row['state']})")
        out += [
            f"    {n}. {entry.get('verdict', '')}: {entry.get('summary', '')} "
            f"Citations: {_cited(entry.get('citations'))}."
            for n, entry in enumerate(row["history"], 1)
        ]
    return ["recorded verdicts:", *out] if out else []


def status_text(snap: decisions_submit.Snapshot) -> list[str]:
    data = status_payload(snap)
    head = (
        f"decisions: {data['pending']} pending, {data['supported']} supported, "
        f"{data['unknown']} unknown"
    )
    store = (
        f"decision store: {data['supported_records']} supported verdicts, "
        "also for claims that are not current"
    )
    return [
        head,
        store,
        *unknown_text(data["unknown_requests"]),
        *history_text(data["records"]),
    ]


def judgement_unknown(
    cfg: config.Config, tree: nest.Tree, facts: dict[str, Any], judged: judgement_json.Judged
) -> list[dict[str, Any]]:
    """Give the unknown requests for the judgement report. Without a store, give none."""
    records = decisions_store.load(cfg.root)
    if not records:
        return []
    found = decisions.requests(tree, facts, cfg.root, judged)
    return unknown_rows(decisions_store.status(records, found), tree, judged)


def cmd_decisions(args: argparse.Namespace) -> int:
    from systemap.cli import _root, say

    cfg = config.load(_root(args))
    if args.action == "submit":
        say(*decisions_submit.submit(cfg, args.file))
        return 0
    snap = decisions_submit.snapshot(cfg)
    if args.action == "pending":
        say(
            json.dumps(pending_payload(snap), indent=2)
            if args.json
            else "\n".join(pending_text(snap))
        )
        return 0
    say(json.dumps(status_payload(snap), indent=2) if args.json else "\n".join(status_text(snap)))
    status = snap.status()
    return 1 if status.pending or status.unknown else 0


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "decisions",
        help="Give the decision requests to a coding agent and record its verdicts.",
        description=(
            "A coding agent examines the claims of the map against the source code. "
            "pending gives the open decision requests. submit examines the verdicts of the "
            "agent and records the correct verdicts. status gives the counts and the unknown "
            "decision requests. The commands do not call a model."
        ),
    )
    actions = s.add_subparsers(dest="action", required=True, metavar="ACTION")
    for name, text in (
        ("pending", "Give the open decision requests with their claims and source files."),
        (
            "status",
            "Give the counts, the unknown decision requests, and the verdict history. "
            "Exit 1 if one is open.",
        ),
    ):
        a = actions.add_parser(name, help=text, description=text)
        add_root(a)
        a.add_argument("--json", action="store_true", help="Write one JSON object.")
    a = actions.add_parser(
        "submit",
        help="Examine and record a JSON list of verdicts.",
        description=(
            "Read a JSON list of verdicts. Each verdict has request_id, verdict, citations, "
            "and summary. If one verdict is incorrect, the command writes no file."
        ),
    )
    add_root(a)
    a.add_argument("file", metavar="FILE", help="Give the file of verdicts, or - for stdin.")
    s.set_defaults(func=cmd_decisions)
