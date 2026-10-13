"""The decision requests are the semantic claims of the map that a coding agent examines.

There are three request types:

- `judgement`: an open judgement line. The claim is the line.
- `source_review`: a source component with a missing or stale source review. The claim is
  the component text, with the flows, sequences, and invariants that name it.
- `flow_review`: a flow with source records and a review digest that is not current.

Each request has a stable ID. The ID comes from the request type, the target, and the claim
digest, so the same claim gives the same ID in a different session. The store identity of
a request does not contain the claim digest: it is the component ID, the flow, or the
finding kind and the names in a judgement line. The digest of a
judgement request is the digest of its line. A source change that does not change the line
does not change the ID. The answer gets the evidence digest at the time of the write.

A judgement line that a review request also closes is not a separate request. These lines
are the `stale source review` and `missing source review` lines of a component with a
review request, and the `flow review` and `declared flow` lines of a flow with a review
request. A review digest closes these lines, and an exact answer must not replace it.

This module uses only language-neutral facts: the module records, their `file` fields, and
the model claims.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import (
    card_review,
    evidence,
    judgement,
    judgement_evidence,
    judgement_json,
    nest,
    repo_files,
    review_policy,
)
from systemap.judgement_evidence import card_modules
from systemap.model import Component, Flow, Meaning, Model

JUDGEMENT = "judgement"
SOURCE_REVIEW = "source_review"
FLOW_REVIEW = "flow_review"
TYPES = (JUDGEMENT, SOURCE_REVIEW, FLOW_REVIEW)
SUPPORTED = "supported"
CONTRADICTED = "contradicted"
INSUFFICIENT = "insufficient_evidence"
VERDICTS = (SUPPORTED, CONTRADICTED, INSUFFICIENT)
ARROW = "->"


@dataclass(frozen=True)
class SourceFile:
    """One source file of a claim: the repository-relative path, the module, and the file digest."""

    file: str
    module: str
    sha256: str


@dataclass(frozen=True)
class Request:
    """One semantic claim that a coding agent examines.

    `digest` is None if the claim has no current digest. `blocked` then tells the cause,
    and a `supported` verdict cannot be recorded until the map or the source changes.
    `identity` is the target in the store. If it is empty, the store uses `target`.
    """

    id: str
    type: str
    map: str
    target: str
    claim: str
    digest: str | None
    files: tuple[SourceFile, ...]
    blocked: str = ""
    identity: str = ""

    @property
    def key(self) -> str:
        """The store key: the request type, the map, and the identity, without the digest."""
        return f"{self.type}\n{self.map}\n{self.identity or self.target}"

    def row(self) -> dict[str, Any]:
        """Give the JSON object of the request."""
        out = dataclasses.asdict(self)
        out["claim_digest"] = out.pop("digest")
        out["files"] = [dataclasses.asdict(f) for f in self.files]
        out["verdicts"] = list(VERDICTS)
        return out


def file_digest(path: Path) -> str:
    """Give the SHA-256 digest of the full file content, as `shasum -a 256` gives it."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# A Windows drive ("C:") or a UNC path ("//host" or "\\\\host") is never a repository path.
_FOREIGN = re.compile(r"^(?:[A-Za-z]:|//|\\\\)")


def confined(root: Path, name: str) -> tuple[Path | None, str]:
    """Give the regular file at a repository-relative path, or None and the cause.

    This is the one check before a read of a path from the facts, the model, or a verdict.
    It refuses an absolute path, a Windows drive or UNC path, a backslash, a `..` part, a
    path whose resolved location (with symbolic links resolved) is outside the resolved
    repository root, and a path that is not a regular file.
    """
    pure = PurePosixPath(name)
    if not name or _FOREIGN.match(name) or "\\" in name or pure.is_absolute():
        return None, "must be a path relative to the repository root"
    if ".." in pure.parts:
        return None, "must be a path relative to the repository root, without '..'"
    try:
        return repo_files.checked(root, pure), ""
    except repo_files.RepoPathError as exc:
        if "not in the repository" in str(exc):
            return None, "is outside the repository"
        return None, "is not a regular file"
    except OSError:
        return None, "is not a regular file"


def source_files(root: Path, facts: dict[str, Any]) -> dict[str, str]:
    """Give the module of each source file in the facts, by repository-relative path."""
    out: dict[str, str] = {}
    for module, record in facts.get("components", {}).items():
        name = record.get("file") if isinstance(record, dict) else None
        if isinstance(name, str) and confined(root, name)[0] is not None:
            out.setdefault(PurePosixPath(name).as_posix(), module)
    return out


def _files(root: Path, facts: dict[str, Any], modules: Iterable[str]) -> tuple[SourceFile, ...]:
    components = facts.get("components", {})
    out: dict[str, SourceFile] = {}
    for module in sorted(set(modules)):
        record = components.get(module)
        name = record.get("file") if isinstance(record, dict) else None
        if not isinstance(name, str):
            continue
        full = confined(root, name)[0]
        if full is None:
            continue
        rel = PurePosixPath(name).as_posix()
        out.setdefault(rel, SourceFile(rel, module, file_digest(full)))
    return tuple(out.values())


def _id(kind: str, target: str, digest: str | None) -> str:
    short = (digest or "none")[:16]
    if kind == JUDGEMENT:
        return f"{kind}@{short}"
    return f"{kind}:{target}@{short}"


def _label(m: nest.Map, target: str) -> str:
    return f"{m.id}/{target}" if m.id else target


def _card_claim(card: Component, model: Model, meaning: Meaning) -> str:
    rows = [
        f"component {card.id} ({meaning.plain.get(card.id, '')}): {card.does}",
        f"interface: {card.interface}",
        f"implemented_by: {', '.join(card.implemented_by)}",
        f"entry: {card.entry}",
    ]
    rows += [
        f"flow: {f.src} {ARROW} {f.dst} ({f.artifact}, {f.kind}): "
        f"{meaning.relations.get(f.edge, '')}"
        for f in model.flows
        if card.id in f.edge
    ]
    rows += [
        f"invariant {inv.n}: {inv.text}"
        for inv in model.invariants
        if not inv.governs or card.id in inv.governs
    ]
    rows += [
        f"sequence {journey.id}: {journey.label}"
        for journey in meaning.journeys
        if any(card.id in (*s.acts, *s.measures, *s.edge) for s in journey.steps)
    ]
    return "\n".join(rows)


def _flow_claim(flow: Flow, meaning: Meaning) -> str:
    return (
        f"flow {flow.src} {ARROW} {flow.dst} ({flow.artifact}, {flow.kind}): "
        f"{meaning.relations.get(flow.edge, '')}\nsource_refs: {', '.join(flow.source_refs)}"
    )


def _card_requests(m: nest.Map, facts: dict[str, Any], root: Path) -> list[Request]:
    out: list[Request] = []
    for card in m.model.components:
        if card.kind == "actor":
            continue
        if card_review.state(card, m.model, m.meaning, facts) == card_review.CURRENT:
            continue
        digest = card_review.digest(card, m.model, m.meaning, facts)
        target = _label(m, card.id)
        blocked = (
            ""
            if digest
            else "The component has no current digest. It claims no module, a claimed module "
            "is missing, or the parser cannot read a claimed module. Correct the map or the source."
        )
        out.append(
            Request(
                _id(SOURCE_REVIEW, target, digest),
                SOURCE_REVIEW,
                m.id,
                card.id,
                _card_claim(card, m.model, m.meaning),
                digest,
                _files(root, facts, card_modules(card, facts)),
                blocked,
            )
        )
    return out


def endpoint_modules(flow: Flow, model: Model, facts: dict[str, Any]) -> list[str]:
    """Give the modules of the two endpoints of a flow."""
    return [
        module
        for card in model.components
        if card.id in flow.edge
        for module in card_modules(card, facts)
    ]


def _flow_requests(m: nest.Map, facts: dict[str, Any], root: Path) -> list[Request]:
    states = evidence.of_model(m.model, m.meaning, facts)
    out: list[Request] = []
    for flow in m.model.flows:
        digest = evidence.flow_claim_digest(flow, m.meaning)
        if not flow.source_refs or flow.review_digest == digest:
            continue
        unresolved = states[flow.edge].unresolved_refs
        blocked = (
            f"Source records do not agree with the current source: {', '.join(unresolved)}. "
            "Examine the source. Then correct source_refs."
            if unresolved
            else ""
        )
        target = f"{flow.src}{ARROW}{flow.dst}"
        modules = endpoint_modules(flow, m.model, facts)
        modules += [evidence.ref_module(ref) for ref in flow.source_refs]
        out.append(
            Request(
                _id(FLOW_REVIEW, _label(m, target), digest),
                FLOW_REVIEW,
                m.id,
                target,
                _flow_claim(flow, m.meaning),
                digest,
                _files(root, facts, modules),
                blocked,
            )
        )
    return out


def _subject(m: nest.Map, line: str, facts: dict[str, Any]) -> str:
    """Give the finding kind and the names in the line, or the line if it names nothing."""
    bare = judgement.unprefixed(line[len(m.prefix) :])
    kind = next((k for k, head in judgement.KIND_PREFIX.items() if bare.startswith(head)), "")
    cards = sorted({card.id for card in judgement_evidence.named_cards(m, line)})
    modules = sorted(
        name for name in facts.get("components", {}) if judgement_evidence.names(name, bare)
    )
    if not kind or not (cards or modules):
        return line
    return f"{kind}: {' '.join(cards + modules)}"


def _covered(review_requests: list[Request], m: nest.Map, line: str) -> bool:
    """Find if a review request closes this judgement line. Then the line is not a request."""
    bare = judgement.unprefixed(line)
    for request in review_requests:
        if request.map != m.id:
            continue
        if request.type == SOURCE_REVIEW:
            heads = (f"stale source review: {request.target} ", review_policy.line(request.target))
        else:
            src, _arrow, dst = request.target.partition(ARROW)
            heads = (f"flow review: {src} -> {dst} (", f"declared flow: {src} -> {dst} (")
        if bare.startswith(heads):
            return True
    return False


def _line_requests(
    tree: nest.Tree,
    facts: dict[str, Any],
    root: Path,
    judged: judgement_json.Judged,
    reviews: list[Request],
) -> list[Request]:
    """Give one request for each open line that no review request closes.

    If two lines have the same kind and the same names, the identity of each is its line.
    """
    chosen = [
        (m, line)
        for line in judged.result.open
        for m in [judgement_evidence.map_of(tree, line)]
        if not _covered(reviews, m, line)
    ]
    subjects = [_subject(m, line, facts) for m, line in chosen]
    out: list[Request] = []
    for (m, line), subject in zip(chosen, subjects, strict=True):
        digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
        blocked = (
            ""
            if judgement_json.digest(line, judged.evidence)
            else "The evidence digest of the line is not available. Do systemap refresh."
        )
        files = _files(root, facts, judgement_evidence.line_modules(m, line, facts))
        identity = subject if subjects.count(subject) == 1 else line
        out.append(
            Request(
                _id(JUDGEMENT, line, digest),
                JUDGEMENT,
                m.id,
                line,
                line,
                digest,
                files,
                blocked,
                identity,
            )
        )
    return out


def requests(
    tree: nest.Tree, facts: dict[str, Any], root: Path, judged: judgement_json.Judged
) -> list[Request]:
    """Give all current requests: judgement lines, then source reviews, then flow reviews.

    The facts must be current. A component or a flow needs facts for its digest.
    """
    if not facts.get("components"):
        return []
    reviews: list[Request] = []
    for m in tree.maps:
        reviews += _card_requests(m, facts, root)
    for m in tree.maps:
        reviews += _flow_requests(m, facts, root)
    return _line_requests(tree, facts, root, judged, reviews) + reviews
