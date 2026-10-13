"""This module gives the judgement report as one JSON object for programs.

The text report and the JSON object use the same lines, answers, and evidence
digests. A different command can import `evaluate` and `payload`. The object
contains no explanation text. `SCHEMA_VERSION` increases when a field changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from systemap import audit, judgement, judgement_moves, nest, review_policy
from systemap import language as languages
from systemap.config import LINE_KINDS, Answer, Config

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Judged:
    """This record contains the judgement lines, their evidence digests, and the
    result of the answers.
    """

    lines: list[str]
    evidence: Mapping[str, str]
    result: judgement.Answered
    require_reviews: bool = False


def evaluate(tree: nest.Tree, facts: dict[str, Any], cfg: Config) -> Judged:
    """This function gives the judgement lines and applies the answers that are not
    audit answers. With `[judgement] require_reviews`, a missing source review is a line.
    """
    adapter = languages.repository(cfg.language) if cfg.language else None
    base = adapter.model_sdks if adapter else judgement.MODEL_SDKS
    separators = (adapter.import_separator,) if adapter else judgement.IMPORT_SEPARATORS
    sdks = judgement.sdk_list(cfg.model_sdks, base)
    lines = judgement.run_tree(tree, facts, sdks, cfg.observed_by, separators=separators)
    if cfg.require_reviews:
        lines += review_policy.missing_lines(tree, facts)
    given = [a for a in cfg.judgement_answered if not audit.is_audit_answer(a)]
    given = judgement_moves.current_lines(given, lines)
    evidence = judgement.evidence_for_tree(tree, facts, cfg.root, lines)
    result = judgement.apply_answers(lines, given, evidence)
    return Judged(lines, evidence, result, cfg.require_reviews)


def digest(line: str, evidence: Mapping[str, str]) -> str | None:
    """This function gives the digest that an exact answer for one line must have.

    The result is None if the evidence is not available.
    """
    found = judgement.answer_digest([line], evidence)
    return None if found == "unavailable" else found


def payload(
    judged: Judged,
    detail: Mapping[str, list[str]],
    reviews: Mapping[str, int] | None,
    kind: str = "",
) -> dict[str, Any]:
    """This function gives the JSON object of the judgement report.

    The detail argument contains the import lines for each crossing-import line. The
    kind argument selects the open rows of one kind. The counts include all kinds.
    """
    result = judged.result
    shown = judgement.of_kind(result.open, kind) if kind else result.open
    return {
        "schema_version": SCHEMA_VERSION,
        "open": [
            {
                "line": line,
                "kind": judgement.kind_of(line),
                "detail": list(detail.get(line, [])),
                "evidence": digest(line, judged.evidence),
            }
            for line in shown
        ],
        "answered": {
            "count": result.answered,
            "answers": [_answer_row(a, judged.lines) for a in result.accepted],
        },
        "stale_answers": list(result.stale),
        "source_reviews": dict(reviews) if reviews is not None else None,
        "require_reviews": judged.require_reviews,
        "kinds": _kind_counts(judged.lines, result.open),
    }


def _answer_row(answer: Answer, lines: list[str]) -> dict[str, Any]:
    return {
        "answer": answer.label,
        "items": list(answer.items),
        "reason": answer.reason,
        "lines": [line for line in lines if judgement.answers(answer, line)],
    }


def _kind_counts(lines: list[str], open_lines: list[str]) -> dict[str, dict[str, int]]:
    """This function counts the open lines and the answered lines of each kind."""
    counts = {kind: {"open": 0, "answered": 0} for kind in LINE_KINDS}
    still_open = set(open_lines)
    for line in lines:
        row = counts.setdefault(judgement.kind_of(line), {"open": 0, "answered": 0})
        row["open" if line in still_open else "answered"] += 1
    return counts


def empty(require_reviews: bool = False) -> dict[str, Any]:
    """This function gives the JSON object for a model without components."""
    return payload(Judged([], {}, judgement.Answered([], 0, []), require_reviews), {}, None)
