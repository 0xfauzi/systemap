"""Put the open stale source review lines in sequence by a drift score.

`systemap judgement --order-by-drift` uses this module. For each open stale source
review line, a predicate question goes to the decision provider. The question gives
the claims of the component and a part of its source. The answer is the probability
that the claims agree with the source. This probability is the drift score.

The score sets only the sequence of the stale lines, from the lowest score. It does
not close a line, and it does not change a review or an answer. The set of open lines
and the exit code are the same with and without the option. No threshold applies,
because no measurement gives a threshold for this question (bench/jev/README.md,
test 7).

The source part has two forms. Both forms have a limit of `CAP` characters.

- `diff`: Git finds the last commit that added the recorded `source_review` digest
  below the folder of the model file. The part is the `git diff` of the module files
  of the component between that commit and the working tree. A new file that is not
  in Git is not in the diff.
- `text`: if Git cannot find that commit, or the diff is empty, the part is the
  current text of the module files, in path sequence. A module file that has a stopped
  Git filter (`git_command.stopped_filters`) also gives this form. Git compares such a
  file without its filter, so the diff can show changes that do not exist.

A refusal or a request error gives no score. A line without a score goes to the
end. No other value replaces a missing score.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import (
    card_review,
    contract,
    decision,
    delta,
    flow_ids,
    git_command,
    history,
    jev,
    judgement,
    judgement_json,
    nest,
    providers,
    repo_files,
)
from systemap.config import Config
from systemap.decision import DecisionError, DecisionProvider, PredicateQuestion
from systemap.model import Component, Meaning, Model, claimed, is_symbol

# The limit of the source part in characters. Test 7 in bench/jev used the same limit.
CAP = 12_000
NAME = "agrees"

CLAIMS = (
    "`component`, `flows`, `sequences`, and `invariants` give the map claims about one "
    "component of a software system. "
)
DIFF_Q = CLAIMS + (
    "`source.text` gives the changes to the source of the component after the last "
    "source review of these claims, as a unified diff. "
    "Do the claims agree with the source after these changes?"
)
TEXT_Q = CLAIMS + (
    "`source.text` gives the current source of the modules of the component. "
    "Do the claims agree with this source?"
)


@dataclass(frozen=True)
class Target:
    """One open stale source review line, its map, and its component."""

    line: str
    map: nest.Map
    card: Component


@dataclass(frozen=True)
class Scored:
    """The drift score of one line. `probability` is None when no score is available."""

    probability: float | None
    form: str


@dataclass(frozen=True)
class Order:
    """The scores by line, the count of questions, and the cause of missing scores."""

    scores: dict[str, Scored] = field(default_factory=dict)
    reason: str = ""

    @property
    def no_score(self) -> int:
        return sum(s.probability is None for s in self.scores.values())

    def ordered(self, open_lines: list[str]) -> list[str]:
        """Put the scored lines in sequence from the lowest score, then the lines without a score.

        The stale lines keep the positions of the stale lines in the open list. The
        other lines do not move. Equal scores keep the sequence of the report.
        """
        stale = [line for line in open_lines if line in self.scores]
        ranked = sorted(stale, key=self._rank)
        fill = iter(ranked)
        return [next(fill) if line in self.scores else line for line in open_lines]

    def _rank(self, line: str) -> tuple[int, float]:
        found = self.scores[line].probability
        return (1, 0.0) if found is None else (0, found)

    def applied(self, result: judgement.Answered) -> judgement.Answered:
        """Give the same result with the stale lines in the drift sequence."""
        return dataclasses.replace(result, open=self.ordered(result.open))

    def rows(self) -> dict[str, list[str]]:
        """Give the score row under each stale line of the text report."""
        return {line: [f"drift score: {_shown(s.probability)}"] for line, s in self.scores.items()}

    def item(self, line: str) -> dict[str, Any] | None:
        """Give the drift object of one JSON item, or None for a line without a question."""
        found = self.scores.get(line)
        if found is None:
            return None
        return {"probability": found.probability, "source": found.form}

    def summary(self) -> dict[str, Any]:
        return {"questions": len(self.scores), "no_score": self.no_score, "reason": self.reason}

    def notes(self) -> list[str]:
        """Give the notice lines that tell the sequence and the questions without a score."""
        if not self.scores:
            return ["drift sequence: No stale source review line is open. No question was sent."]
        out = [
            "drift sequence: The stale source review lines are in sequence from the lowest "
            "drift score. The drift score is the probability that the claims agree with "
            "the source. Examine each stale component."
        ]
        if self.no_score:
            out.append(
                f"drift sequence: {self.no_score} of {len(self.scores)} questions got no score. "
                f"Cause: {self.reason}"
            )
        return out


def _shown(probability: float | None) -> str:
    return "no score" if probability is None else f"{probability:.2f}"


# ---- the targets and the questions ------------------------------------------------


def targets(tree: nest.Tree, open_lines: Sequence[str]) -> list[Target]:
    """Give the open stale source review lines with their maps and components."""
    still_open = set(open_lines)
    out: list[Target] = []
    for m in tree.maps:
        for card in m.model.components:
            line = m.prefix + judgement.stale_review_line(card.id)
            if line in still_open:
                out.append(Target(line, m, card))
    return out


def files_of(card: Component, facts: dict[str, Any]) -> list[str]:
    """Give the source file paths of the modules that the component claims, in sequence."""
    components = facts.get("components", {})
    names = set(claimed(card, components))
    names.update(p.partition(":")[0] for p in card.implemented_by if is_symbol(p))
    found = {components.get(name, {}).get("file") for name in names}
    return sorted(path for path in found if isinstance(path, str) and path)


_DIGEST = re.compile(r"[0-9a-f]{64}")
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def reviewed_commit(root: Path, folder: str, digest: str) -> str | None:
    """Give the last commit that added the digest below the folder, or None.

    The commit must contain the digest below the folder. Without Git, the result is None.
    The digest comes from the model file of the repository. A value that is not a digest
    gives None, so that Git never reads a model value as an option.
    """
    if not _DIGEST.fullmatch(digest):
        return None
    try:
        # `git log -S` reads the content of each diff. Thus it gets `git_command.CONTENT`.
        sha = history.git(
            root, "log", f"-S{digest}", *git_command.CONTENT, "-1", "--format=%H", "--", folder
        ).strip()
        if not _SHA.fullmatch(sha):
            return None
        # The sha agrees with _SHA, so Git cannot read it as an option. Git 2.43 and earlier
        # do not accept --end-of-options before the revision of git grep.
        history.git(root, "grep", "-q", "-F", "-e", digest, sha, "--", folder)
    except (delta.DeltaError, OSError):
        return None
    return sha


def _diff(root: Path, sha: str, paths: list[str]) -> str:
    """Give the diff of the paths from the commit to the working tree, with fixed settings."""
    try:
        return history.git(
            root,
            "diff",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--unified=3",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            sha,
            "--",
            *paths,
            worktree=True,
        )
    except (delta.DeltaError, OSError):
        return ""


def _source_diff(root: Path, sha: str | None, paths: list[str]) -> str:
    """Give the diff of the paths, or an empty text if the diff form does not apply.

    The diff form does not apply without a commit or a path. It also does not apply if a
    path has a stopped Git filter, or if Git cannot give the filters.
    """
    if not (sha and paths):
        return ""
    try:
        if git_command.stopped_filters(root, paths, delta.DeltaError):
            return ""
    except (delta.DeltaError, OSError):
        return ""
    return _diff(root, sha, paths)


def _text(root: Path, paths: list[str]) -> str:
    parts = []
    for rel in paths:
        try:
            body = repo_files.read_text(root, rel, encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            body = f"(the file could not be read: {type(exc).__name__})"
        parts.append(f"=== {rel}\n{body}")
    return "\n".join(parts)


def source_of(cfg: Config, target: Target, facts: dict[str, Any]) -> dict[str, Any]:
    """Give the source part of one component: its form, its text, and if the limit cut it."""
    paths = files_of(target.card, facts)
    folder = cfg.rel(target.map.path.parent)
    sha = reviewed_commit(cfg.root, folder, target.card.source_review)
    form, body = "diff", _source_diff(cfg.root, sha, paths)
    if not body.strip():
        form, body = "text", _text(cfg.root, paths)
    return {"form": form, "text": body[:CAP], "cut": len(body) > CAP}


def claims_of(card: Component, model: Model, meaning: Meaning) -> dict[str, Any]:
    """Give the claims that `card_review` digests, with field names for the reader.

    The map path and the flow review digests are not claims about the source.
    """
    meaning = flow_ids.resolve(model, meaning)
    return {
        "component": {
            "id": card.id,
            "does": card.does,
            "plain": meaning.plain.get(card.id, ""),
            "interface": card.interface,
            "implemented_by": list(card.implemented_by),
            "entry": card.entry,
            "kind": card.kind,
            "note": card.note,
            "calls_model": card.calls_model,
        },
        "flows": [
            {
                "from": flow.src,
                "to": flow.dst,
                "artifact": flow.artifact,
                "kind": flow.kind,
                "source_refs": list(flow.source_refs),
                "relation": meaning.relation(flow),
                **({"id": flow.id} if flow.id else {}),
            }
            for flow in model.flows
            if card.id in flow.edge
        ],
        "sequences": [
            flow_ids.journey_record(journey)
            for journey in meaning.journeys
            if card_review.touches(journey, card.id)
        ],
        "invariants": [
            contract.claim(invariant)
            for invariant in model.invariants
            if not invariant.governs or card.id in invariant.governs
        ],
    }


def question(cfg: Config, target: Target, facts: dict[str, Any]) -> PredicateQuestion:
    """Make the drift question of one stale component."""
    source = source_of(cfg, target, facts)
    claims = claims_of(target.card, target.map.model, target.map.meaning)
    text = DIFF_Q if source["form"] == "diff" else TEXT_Q
    return PredicateQuestion(target.line, NAME, text, {**claims, "source": source})


# ---- the answers ------------------------------------------------------------------


Make = Callable[[], DecisionProvider]


def order(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    open_lines: Sequence[str],
    make: Make,
) -> Order:
    """Ask one question for each open stale line and give the scores.

    Without an open stale line, no provider is made and no request is sent.
    A refusal gives no score for its line. A provider error gives no score for all lines.
    """
    found = targets(tree, open_lines)
    if not found:
        return Order()
    questions = [question(cfg, t, facts) for t in found]
    forms = {q.key: q.state["source"]["form"] for q in questions}
    try:
        provider = make()
    except DecisionError as exc:
        return _failed(questions, forms, exc)
    try:
        answers = provider.decide(questions)
        scores = {
            q.key: Scored(decision.probability(a, q.key), forms[q.key])
            for q, a in zip(questions, answers, strict=True)
        }
    except DecisionError as exc:
        return _failed(questions, forms, exc)
    finally:
        _usage(provider)
    refused = decision.refused(questions, answers)
    return Order(scores, "the decision provider gave a refusal" if refused else "")


def _failed(questions: list[PredicateQuestion], forms: dict[str, str], exc: DecisionError) -> Order:
    """Give no score for each question, with the cause of the error."""
    scores = {q.key: Scored(None, forms[q.key]) for q in questions}
    return Order(scores, jev.printable(str(exc)))


def _usage(provider: Any) -> None:
    """Print the usage line of a provider that records usage, to stderr."""
    usage = getattr(provider, "usage", None)
    if isinstance(usage, jev.Usage) and (usage.sent or usage.cached):
        print(usage.line(), file=sys.stderr)


def with_provider(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    open_lines: Sequence[str],
    send: jev.Send | None = None,
) -> Order:
    """Give scores from the selected provider, with its configured cache."""

    def make() -> DecisionProvider:
        providers.require_drift(cfg)
        return providers.select(cfg, send)

    return order(
        cfg,
        tree,
        facts,
        open_lines,
        make,
    )


# ---- the report -------------------------------------------------------------------


def text(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    result: judgement.Answered,
    crossings: dict[str, list[str]] | None,
    args: argparse.Namespace,
) -> tuple[judgement.Answered, dict[str, list[str]] | None, list[str]]:
    """Give the text report parts. Without `--order-by-drift`, give them with no change."""
    if not args.order_by_drift:
        return result, crossings, []
    found = with_provider(cfg, tree, facts, result.open)
    return found.applied(result), {**(crossings or {}), **found.rows()}, found.notes()


def payload(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    given: judgement_json.Judged,
    crossings: dict[str, list[str]],
    reviews: dict[str, int] | None,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str]]:
    """Give the JSON object and the notices. Without `--order-by-drift`, send no request.

    With the option, each stale row has `drift`, and the object has `drift_order`.
    """
    kind = args.kind or ""
    if not args.order_by_drift:
        return judgement_json.payload(given, crossings, reviews, kind), []
    found = with_provider(cfg, tree, facts, given.result.open)
    ordered = dataclasses.replace(given, result=found.applied(given.result))
    obj = judgement_json.payload(ordered, crossings, reviews, kind)
    for row in obj["open"]:
        item = found.item(row["line"])
        if item is not None:
            row["drift"] = item
    obj["drift_order"] = found.summary()
    return obj, found.notes()
