"""This module gives the judgement report as one JSON object for programs.

The text report and the JSON object use the same lines, answers, and evidence
digests. A different command can import `evaluate` and `payload`. The object
contains no explanation text. `SCHEMA_VERSION` increases when a field changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from systemap import (
    answer_migrations,
    audit,
    flow_review,
    judgement,
    nest,
    review_policy,
    source_facts,
)
from systemap import language as languages
from systemap.config import LINE_KINDS, Answer, Config

# Version 2 adds `cause` to each row of `open`. Version 3 adds `sources`. Version 4 adds
# `earlier_flow_reviews`. Version 5 adds `insufficient`, `open_lines`, and `history` to
# each row of `unknown_requests`. Version 6 adds `count` to each row of `open`.
SCHEMA_VERSION = 6


@dataclass(frozen=True)
class Judged:
    """This record contains the judgement lines, their evidence digests, the result of
    the answers, the cause and the sources of each `unknown surface` line, and the count
    of each line with a count (`line_counts`).
    """

    lines: list[str]
    evidence: Mapping[str, str]
    result: judgement.Answered
    require_reviews: bool = False
    causes: Mapping[str, str] = field(default_factory=dict)
    sources: Mapping[str, list[dict[str, Any]]] = field(default_factory=dict)
    earlier: list[dict[str, str]] = field(default_factory=list)
    counts: Mapping[str, tuple[int, str]] = field(default_factory=dict)

    def detail(
        self, tree: nest.Tree, facts: dict[str, Any], verbose: bool
    ) -> dict[str, list[str]] | None:
        """Give the rows below each line: the count row, the source rows of an `unknown
        surface` line, and with `verbose`, the import rows of a crossing-import line."""
        imports = judgement.crossing_detail_tree(tree, facts) if verbose else {}
        out = {line: [count_row(*count)] for line, count in self.counts.items()}
        for line, rows in imports.items():
            out[line] = [*out.get(line, []), *rows]
        for line, sources in self.sources.items():
            out[line] = [*out.get(line, []), *source_facts.source_rows(sources)]
        return out


def count_row(count: int, noun: str) -> str:
    """Give the row below a line for its count, for example `count: 3 modules`."""
    return f"count: {count} {noun}{'' if count == 1 else 's'}"


def line_counts(
    tree: nest.Tree, facts: dict[str, Any], lines: list[str]
) -> dict[str, tuple[int, str]]:
    """Give the count and the counted noun of each line with a count. A count can change
    while the finding stays the same. Thus the count is not in the line.

    A crossing-import line counts the modules of the source component that import the
    destination component. An `unknown surface` line counts the targets of its record."""
    found = {line: (n, "module") for line, n in judgement.crossing_counts(tree, facts).items()}
    found |= {line: (n, "target") for line, n in source_facts.unknown_counts(facts).items()}
    present = set(lines)
    return {line: count for line, count in found.items() if line in present}


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
    given = answer_migrations.current_lines(given, lines)
    evidence = judgement.evidence_for_tree(tree, facts, cfg.root, lines)
    result = judgement.apply_answers(lines, given, evidence)
    causes = line_causes(lines, facts)
    sources = line_sources(lines, facts)
    earlier = earlier_reviews(tree, facts)
    counts = line_counts(tree, facts, lines)
    return Judged(lines, evidence, result, cfg.require_reviews, causes, sources, earlier, counts)


def earlier_reviews(tree: nest.Tree, facts: dict[str, Any]) -> list[dict[str, str]]:
    """This function gives each flow with the review state `earlier` (`flow_review`).

    Such a review is current, so it gives no finding line. The report gives it as a row
    with the label, because the review digest does not identify the examined source.
    """
    return [
        {"map": m.id, "flow": flow.key}
        for m in tree.maps
        for flow in m.model.flows
        if flow_review.state(flow, m.meaning, facts) == flow_review.EARLIER
    ]


def earlier_rows(judged: Judged, tree: nest.Tree, teach: bool) -> list[str]:
    """This function gives one text row for each flow review with the state `earlier`."""
    if not judged.earlier:
        return []
    prefixes = {m.id: m.prefix for m in tree.maps}
    rows = [
        f"{flow_review.EARLIER_LABEL}: {prefixes.get(row['map'], '')}{row['flow']}"
        for row in judged.earlier
    ]
    action = (
        "  The review digest does not identify the examined source. Examine the flow claim "
        "against the source. Then use systemap review --flow ID."
    )
    return rows + ([action] if teach else [])


def line_causes(lines: Iterable[str], facts: dict[str, Any]) -> dict[str, str]:
    """This function gives the cause that the adapter wrote for each `unknown surface`
    line. A line of a nested map has the cause of the same line without the map prefix.
    """
    causes = dict(source_facts.unknown_fact_causes(facts))
    return {line: causes[bare] for line in lines if (bare := judgement.unprefixed(line)) in causes}


def line_sources(lines: Iterable[str], facts: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """This function gives the source location of each record of an `unknown surface` line
    of a module or a test file: the file, the line, the source excerpt, and the parser
    version. A value that the record does not give is None. These values change while the
    finding stays the same. Thus they are not in the line.
    """
    located = source_facts.located_records(facts)
    return {
        line: [source_facts.source_fields(found) for found in located[bare]]
        for line in lines
        if (bare := judgement.unprefixed(line)) in located
    }


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
                "cause": judged.causes.get(line),
                "sources": judged.sources.get(line),
                "count": judged.counts[line][0] if line in judged.counts else None,
            }
            for line in shown
        ],
        "answered": {
            "count": result.answered,
            "answers": [_answer_row(a, judged.lines) for a in result.accepted],
        },
        "stale_answers": list(result.stale),
        "source_reviews": dict(reviews) if reviews is not None else None,
        "earlier_flow_reviews": [dict(row) for row in judged.earlier],
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
