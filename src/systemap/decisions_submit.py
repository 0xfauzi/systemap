"""The submit step validates the results of a coding agent and records the valid results.

A result has `request_id`, `verdict`, `citations`, and `summary`. Each citation has `file`,
`start_line`, `end_line`, and `sha256`, the digest of the full file. The command first
examines all results. If one result is incorrect, it writes nothing and tells each error.

- The request ID must be a current request, and the request must not be unknown.
- Each cited file must be a source file in the facts, inside the repository.
- Each line span must be in the file, and each digest must agree with the current file.
- `supported` must cite a file of the claim. For a flow, the files of the claim are the
  files of the two endpoints.

Then the command writes, in this sequence: the flow review digests, the component review
digests, the exact answers, and the store. A flow digest is one of the claims of its
endpoint components, so the flow digests come first. A review can close a judgement line.
Thus the command calculates the open lines and their evidence digests after the review
writes.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import (
    answer_write,
    config,
    config_decisions,
    decisions,
    decisions_store,
    extraction,
    facts_file,
    judgement_json,
    nest,
    review,
)
from systemap.config_decisions import Citation
from systemap.decisions import (
    CONTRADICTED,
    FLOW_REVIEW,
    JUDGEMENT,
    SOURCE_REVIEW,
    SUPPORTED,
    VERDICTS,
    Request,
)

RESULT_KEYS = ("request_id", "verdict", "citations", "summary")


class DecisionError(Exception):
    """The command cannot use the results or the facts. The message gives the cause."""


@dataclass(frozen=True)
class Snapshot:
    """The current map, facts, judgement result, requests, and store records."""

    cfg: config.Config
    tree: nest.Tree
    facts: dict[str, Any]
    judged: judgement_json.Judged
    requests: dict[str, Request]
    records: dict[str, dict[str, Any]]

    def status(self) -> decisions_store.Status:
        return decisions_store.status(self.records, list(self.requests.values()))


def snapshot(cfg: config.Config) -> Snapshot:
    """Read the map, the facts, and the store. The stored facts must agree with the source."""
    tree = nest.load(cfg)
    saved = facts_file.read_facts(cfg.facts_path)
    if not saved:
        raise DecisionError(
            f"No facts are available at {cfg.rel(cfg.facts_path)}. Do systemap refresh. "
            "Then do this command again."
        )
    drift = extraction.drift(extraction.build(cfg), saved)
    if drift:
        raise DecisionError(
            f"The facts at {cfg.rel(cfg.facts_path)} do not agree with the source: "
            f"{drift[0]}. Do systemap refresh. Then do this command again."
        )
    judged = judgement_json.evaluate(tree, saved, cfg)
    found = decisions.requests(tree, saved, cfg.root, judged)
    return Snapshot(
        cfg, tree, saved, judged, {r.id: r for r in found}, decisions_store.load(cfg.root)
    )


@dataclass(frozen=True)
class Result:
    """One valid result of the agent."""

    request: Request
    verdict: str
    citations: tuple[Citation, ...]
    summary: str


def read_results(name: str) -> list[Any]:
    """Read the JSON list of results from a file, or from stdin for `-`."""
    try:
        text = sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8")
        data = json.loads(text)
    except OSError as exc:
        raise DecisionError(f"{name}: the command cannot read the file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DecisionError(f"{name}: the file is not JSON: {exc}") from exc
    if not isinstance(data, list):
        raise DecisionError(f"{name}: the file must contain a JSON list of results.")
    return data


def _citation_errors(root: Path, files: dict[str, str], cited: Citation, where: str) -> list[str]:
    """Examine one citation against the repository and the current file content."""
    name, start, end, digest = cited
    full, cause = decisions.confined(root, name)
    if full is None:
        return [f"{where}: {name} {cause}."]
    if PurePosixPath(name).as_posix() not in files:
        return [f"{where}: {name} is not a source file in the facts."]
    content = full.read_bytes()
    count = len(content.splitlines())
    errors = []
    if end > count:
        errors.append(
            f"{where}: the lines {start} to {end} are not in {name}. The file has {count} lines."
        )
    actual = decisions.file_digest(full)
    if digest != actual:
        errors.append(
            f"{where}: sha256 is not the digest of the current {name}. The current digest is "
            f"{actual}. Read the file again."
        )
    return errors


def _citations(
    item: dict[str, Any], snap: Snapshot, where: str
) -> tuple[list[Citation], list[str]]:
    value = item.get("citations")
    if not isinstance(value, list):
        return [], [f"{where}: citations must be a list."]
    files = decisions.source_files(snap.cfg.root, snap.facts)
    found: list[Citation] = []
    errors: list[str] = []
    for k, entry in enumerate(value, 1):
        location = f"{where} citations[{k}]"
        try:
            cited = config_decisions.citation(entry, location)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        problems = _citation_errors(snap.cfg.root, files, cited, location)
        errors += problems
        if not problems:
            found.append(cited)
    return found, errors


def _request(item: dict[str, Any], snap: Snapshot, where: str) -> tuple[Request | None, list[str]]:
    rid = item.get("request_id")
    request = snap.requests.get(rid) if isinstance(rid, str) else None
    if request is None:
        return None, [
            f"{where}: {rid} is not a current decision request. The claim changed, or the ID is "
            "incorrect. Use systemap decisions pending."
        ]
    if decisions_store.state(snap.records, request) == decisions_store.UNKNOWN:
        return None, [
            f"{where}: {rid} is unknown. A person must examine the claim. "
            "A change of the source of the target makes the request pending again."
        ]
    return request, []


def _supported_errors(
    request: Request, cited: list[Citation], where: str, verdicts: dict[str, str], snap: Snapshot
) -> list[str]:
    """Examine the conditions that only a supported result has."""
    if request.blocked:
        return [f"{where}: the command cannot record supported for {request.id}. {request.blocked}"]
    claim_files = {f.file for f in request.files}
    if not cited:
        return [f"{where}: a supported result must have one or more citations."]
    if claim_files and not any(PurePosixPath(c[0]).as_posix() in claim_files for c in cited):
        return [
            f"{where}: a supported result must refer to a file of the claim: "
            f"{', '.join(sorted(claim_files))}."
        ]
    if request.type == SOURCE_REVIEW:
        return _open_flows(request, where, verdicts, snap)
    return []


def _open_flows(
    request: Request, where: str, verdicts: dict[str, str], snap: Snapshot
) -> list[str]:
    """Refuse a component review while a flow of the component has an open verdict."""
    errors = []
    flows = snap.tree.get(request.map).model.flows
    for flow in snap.requests.values():
        if flow.type != FLOW_REVIEW or flow.map != request.map:
            continue
        ends = next((f.edge for f in flows if f.key == flow.target), ())
        if request.target not in ends:
            continue
        verdict = verdicts.get(flow.id) or decisions_store.verdict(snap.records, flow)
        if verdict and verdict != SUPPORTED:
            errors.append(
                f"{where}: the claims of {request.target} include the flow {flow.target}, "
                f"which has the verdict {verdict}. Correct the flow first."
            )
    return errors


def _check(
    item: Any, where: str, snap: Snapshot, verdicts: dict[str, str]
) -> tuple[Result | None, list[str]]:
    """Examine one result. Give the valid result, or the errors."""
    if not isinstance(item, dict) or set(item) != set(RESULT_KEYS):
        return None, [
            f"{where}: a result must be an object with the keys {', '.join(RESULT_KEYS)}."
        ]
    request, errors = _request(item, snap, where)
    verdict, summary = item["verdict"], item["summary"]
    if verdict not in VERDICTS:
        errors.append(f"{where}: the verdict must be one of {', '.join(VERDICTS)}.")
    if not isinstance(summary, str) or not summary.strip():
        errors.append(f"{where}: the summary must be a sentence about the examined source.")
    cited, problems = _citations(item, snap, where)
    errors += problems
    if request is None or errors:
        return None, errors
    if verdict == SUPPORTED:
        errors += _supported_errors(request, cited, where, verdicts, snap)
        errors += _dry_run(request, snap, where)
    return (None if errors else Result(request, verdict, tuple(cited), summary.strip())), errors


def _target(request: Request) -> review.Target:
    if request.type == FLOW_REVIEW:
        return review.flow_target(request.target)
    return review.Target(request.target)


def _dry_run(request: Request, snap: Snapshot, where: str) -> list[str]:
    """Find a review error before any file changes."""
    if request.type == JUDGEMENT:
        return []
    try:
        review.review(snap.cfg, request.map, _target(request), True, snap.facts)
    except review.ReviewError as exc:
        return [f"{where}: {exc}"]
    return []


def validate(snap: Snapshot, items: list[Any]) -> list[Result]:
    """Examine all results. If a result is incorrect, give all errors and write nothing."""
    verdicts = {
        item["request_id"]: item.get("verdict", "")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("request_id"), str)
    }
    results: list[Result] = []
    errors: list[str] = []
    seen: set[str] = set()
    for k, item in enumerate(items, 1):
        where = f"result {k}"
        rid = item.get("request_id") if isinstance(item, dict) else None
        if isinstance(rid, str) and rid in seen:
            errors.append(f"{where}: the file has more than one result for {rid}.")
            continue
        if isinstance(rid, str):
            seen.add(rid)
        result, problems = _check(item, where, snap, verdicts)
        errors += problems
        if result:
            results.append(result)
    if errors:
        raise DecisionError("\n".join([*errors, "The command wrote nothing."]))
    return results


def _answers(snap: Snapshot, results: list[Result]) -> list[str]:
    """Add one exact answer for each supported judgement line that is still open."""
    chosen = [r for r in results if r.request.type == JUDGEMENT and r.verdict == SUPPORTED]
    if not chosen:
        return []
    judged = judgement_json.evaluate(nest.load(snap.cfg), snap.facts, snap.cfg)
    out: list[str] = []
    entries: list[dict[str, Any]] = []
    for result in chosen:
        line = result.request.target
        digest = judgement_json.digest(line, judged.evidence)
        if line not in judged.result.open or digest is None:
            out.append(f"supported: {result.request.id}: the new review digests closed the line.")
            continue
        entries.append(
            {
                "item": line,
                "evidence": digest,
                "reason": result.summary,
                "citations": [_cited(c) for c in result.citations],
            }
        )
        out.append(f"supported: {result.request.id}: the command added an exact answer.")
    if entries:
        _write_answers(snap.cfg, entries)
    return out


def _cited(cited: Citation) -> dict[str, Any]:
    return dict(zip(config_decisions.CITATION_KEYS, cited, strict=True))


def _write_answers(cfg: config.Config, entries: list[dict[str, Any]]) -> None:
    """Write the answers. If the configuration does not load after the write, restore it."""
    target = answer_write.path(cfg.root, cfg.source)
    before = target.read_bytes() if target.is_file() else None
    answer_write.add(cfg.root, cfg.source, entries)
    try:
        config.load(cfg.root)
    except config.ConfigError as exc:
        if before is not None:
            target.write_bytes(before)
        raise DecisionError(f"{exc}\nThe command restored {target.name}.") from exc


def _record(snap: Snapshot, results: list[Result]) -> list[str]:
    out = []
    limit = snap.cfg.max_contradicted
    for result in results:
        request = result.request
        new = decisions_store.record(snap.records, request, result.verdict, result.summary, limit)
        count = decisions_store.attempts(snap.records, request)
        if new == CONTRADICTED:
            out.append(
                f"contradicted: {request.id}: contradicted verdict {count} of {limit}. Correct "
                "the map. Then send a new verdict with systemap decisions submit."
            )
        elif new == decisions_store.UNKNOWN:
            out.append(
                f"unknown: {request.id}: the claim has no decision. A person must examine it."
            )
    decisions_store.save(snap.cfg.root, snap.records)
    return out


def apply(snap: Snapshot, results: list[Result]) -> list[str]:
    """Write the valid results. Give the lines for the person."""
    out: list[str] = []
    for kind in (FLOW_REVIEW, SOURCE_REVIEW):
        for result in results:
            if result.request.type == kind and result.verdict == SUPPORTED:
                target = _target(result.request)
                out += review.review(snap.cfg, result.request.map, target, False, snap.facts)
    out += _answers(snap, results)
    return out + _record(snap, results)


def submit(cfg: config.Config, name: str) -> list[str]:
    """Read, examine, and record the results in a file. Give the lines for the person."""
    items = read_results(name)
    snap = snapshot(cfg)
    results = validate(snap, items)
    return [*apply(snap, results), f"decisions: the command recorded {len(results)} results."]
