"""The `systemap decisions` commands give the semantic requests to a coding agent.

- `systemap decisions pending [--json]` gives the open requests.
- `systemap decisions submit FILE` examines and records the results of the agent.
- `systemap decisions status [--json]` gives the counts and the unknown requests.

The agent operates in its current session. The commands send no request to a model and
ask no person. An unknown request is never a pass: the text does not say that its claim
is correct, and `systemap judgement` shows it.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from systemap import config, decisions, decisions_store, decisions_submit, judgement_json, nest
from systemap.decisions import VERDICTS, Request

SCHEMA_VERSION = 1


def _attempts(snap: decisions_submit.Snapshot, request: Request) -> int:
    return decisions_store.attempts(snap.records, request)


def pending_payload(snap: decisions_submit.Snapshot) -> dict[str, Any]:
    """Give the JSON object of `decisions pending`."""
    status = snap.status()
    return {
        "schema_version": SCHEMA_VERSION,
        "verdicts": list(VERDICTS),
        "max_contradicted": snap.cfg.max_contradicted,
        "requests": [
            {**request.row(), "attempts": _attempts(snap, request)} for request in status.pending
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
        out.append(f"  attempts: {_attempts(snap, request)} of {limit}")
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


def unknown_rows(status: decisions_store.Status) -> list[dict[str, Any]]:
    """Give one object for each unknown request, with its last verdict and summary."""
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
            "summary": record.get("summary", ""),
        }
        for request, record in status.unknown
    ]


def status_payload(snap: decisions_submit.Snapshot) -> dict[str, Any]:
    status = snap.status()
    return {
        "schema_version": SCHEMA_VERSION,
        "pending": len(status.pending),
        "supported": status.supported,
        "unknown": len(status.unknown),
        "unknown_requests": unknown_rows(status),
    }


def unknown_text(rows: list[dict[str, Any]]) -> list[str]:
    """Give the text rows for unknown requests. The text never says that a claim is correct."""
    out = []
    for row in rows:
        out.append(f"unknown request {row['id']}: {row['claim'].splitlines()[0]}")
        out.append(f"  last verdict: {row['verdict']}. Last summary: {row['summary']}")
    if rows:
        out.append("These claims have no decision. A person must examine them.")
    return out


def status_text(snap: decisions_submit.Snapshot) -> list[str]:
    data = status_payload(snap)
    head = (
        f"decisions: {data['pending']} pending, {data['supported']} supported, "
        f"{data['unknown']} unknown"
    )
    return [head, *unknown_text(data["unknown_requests"])]


def judgement_unknown(
    cfg: config.Config, tree: nest.Tree, facts: dict[str, Any], judged: judgement_json.Judged
) -> list[dict[str, Any]]:
    """Give the unknown requests for the judgement report. Without a store, give none."""
    records = decisions_store.load(cfg.root)
    if not records:
        return []
    found = decisions.requests(tree, facts, cfg.root, judged)
    return unknown_rows(decisions_store.status(records, found))


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
        ("status", "Give the counts and the unknown decision requests. Exit 1 if one is open."),
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
