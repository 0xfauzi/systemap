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
    assurance,
    audit,
    flow_review,
    judgement,
    judgement_evidence,
    module_use,
    nest,
    nest_join,
    refused_answers,
    review_policy,
    source_facts,
)
from systemap import language as languages
from systemap.config import LINE_KINDS, Answer, Config

# Version 2 adds `cause` to each row of `open`. Version 3 adds `sources`. Version 4 adds
# `earlier_flow_reviews`. Version 5 adds `insufficient`, `open_lines`, and `history` to
# each row of `unknown_requests`. Version 6 adds `count` to each row of `open`. Version 7
# adds `assurance`: the level, the freshness, and the basis of each claim. Version 8 adds
# `map_id`, `parent_flow`, `nested_flows`, and `import_pairs` to each row of `open`. They
# have values only for a `boundary flow` or a `boundary import` line (`nest_join.fields`).
# Version 9 adds `module_use` to each row of `open`, `role`, `symbol`, and `handoff` to each
# answer of `answered`, and `refused_answers`, `unused_answers`, `import_crossings`, and
# `module_roles` (`role_fields`).
SCHEMA_VERSION = 9
# The fields of a row of `open` for a line that is not a boundary line.
NO_BOUNDARY: dict[str, Any] = dict.fromkeys(
    ("map_id", "parent_flow", "nested_flows", "import_pairs")
)


@dataclass(frozen=True)
class Judged:
    """This record contains the judgement lines, their evidence digests, the result of
    the answers, the cause and the sources of each `unknown surface` line, the count
    of each line with a count (`line_counts`), and the fields of each boundary line.

    `crossings` gives the state and the units of each import crossing, and `uses` gives
    the record of each `module use` line (`module_use`). `hidden` gives the waiting and
    the closed crossing import lines. They are not in `lines`.
    """

    lines: list[str]
    evidence: Mapping[str, str]
    result: judgement.Answered
    require_reviews: bool = False
    causes: Mapping[str, str] = field(default_factory=dict)
    sources: Mapping[str, list[dict[str, Any]]] = field(default_factory=dict)
    earlier: list[dict[str, str]] = field(default_factory=list)
    counts: Mapping[str, tuple[int, str]] = field(default_factory=dict)
    claims: list[assurance.Claim] = field(default_factory=list)
    boundary: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    found: Mapping[str, nest_join.Finding] = field(default_factory=dict)
    crossings: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    uses: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    hidden: list[str] = field(default_factory=list)
    refused_rows: list[dict[str, Any]] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        """Tell if `judgement --strict` exits 1: a line is open, an answer is refused, or an
        import crossing waits for module roles."""
        waiting = any(row["state"] == module_use.WAITING for row in self.crossings.values())
        return bool(self.result.open or self.result.refused or waiting)

    def import_rows(self, tree: nest.Tree, facts: dict[str, Any]) -> dict[str, list[str]]:
        """Give the import rows of each crossing-import line and `boundary import` line, and
        the rows of each `module use` line. The rows of an open crossing import line start
        with its handoff modules."""
        out = judgement.crossing_detail_tree(tree, facts) | nest_join.detail(self.found)
        for line, row in self.crossings.items():
            if row["rows"] and line in out:
                out[line] = [*row["rows"], *out[line]]
        return out | {line: list(row["rows"]) for line, row in self.uses.items()}

    def detail(
        self, tree: nest.Tree, facts: dict[str, Any], verbose: bool
    ) -> dict[str, list[str]] | None:
        """Give the rows below each line: the count row, the source rows of an `unknown
        surface` line, and with `verbose`, the import rows of a crossing-import line and
        of a `boundary import` line."""
        imports = self.import_rows(tree, facts) if verbose else {}
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
    tree: nest.Tree,
    facts: dict[str, Any],
    lines: list[str],
    found: Mapping[str, nest_join.Finding],
) -> dict[str, tuple[int, str]]:
    """Give the count and the counted noun of each line with a count. A count can change
    while the finding stays the same. Thus the count is not in the line.

    A crossing-import line counts the modules of the source component that import the
    destination component. A `boundary import` line counts the modules of the internal
    component that import the modules of the other component. An `unknown surface` line
    counts the targets of its record. `found` is the result of `boundary_findings`."""
    modules = judgement.crossing_counts(tree, facts) | nest_join.counts(found)
    out = {line: (n, "module") for line, n in modules.items()}
    out |= {line: (n, "target") for line, n in source_facts.unknown_counts(facts).items()}
    present = set(lines)
    return {line: count for line, count in out.items() if line in present}


def current_lines(
    tree: nest.Tree, facts: dict[str, Any], cfg: Config, found: module_use.Index | None = None
) -> list[str]:
    """This function gives the judgement lines of the map tree, without the answers.

    The `module use` lines come after the lines of `judgement.run_tree`. `found` is the
    result of `module_use.index`. With `[judgement] require_reviews`, a missing source
    review is a line."""
    adapter = languages.repository(cfg.language) if cfg.language else None
    base = adapter.model_sdks if adapter else judgement.MODEL_SDKS
    separators = (adapter.import_separator,) if adapter else judgement.IMPORT_SEPARATORS
    sdks = judgement.sdk_list(cfg.model_sdks, base)
    lines = judgement.run_tree(tree, facts, sdks, cfg.observed_by, separators=separators)
    lines += module_use.lines(module_use.index(tree, facts) if found is None else found, tree)
    if cfg.require_reviews:
        lines += review_policy.missing_lines(tree, facts)
    return lines


def evaluate(tree: nest.Tree, facts: dict[str, Any], cfg: Config) -> Judged:
    """This function gives the judgement lines and applies the answers that are not
    audit answers. With `[judgement] require_reviews`, a missing source review is a line.

    The module role answers decide the state of each import crossing. Only the open
    crossing import lines are in `Judged.lines`. The evidence covers all lines, also the
    hidden crossing import lines."""
    found = module_use.index(tree, facts)
    lines = current_lines(tree, facts, cfg, found)
    given = [a for a in cfg.judgement_answered if not audit.is_audit_answer(a)]
    given = answer_migrations.current_lines(given, lines)
    present = set(lines)
    uses = {u.line: u.module for u in found.units.values() if u.line in present}
    evidence = judgement.evidence_for_tree(tree, facts, cfg.root, lines, uses=uses)
    picked = module_use.roles(given, found, module_use.evidence(found), tree, facts)
    states = module_use.crossing_states(found, picked.accepted)
    states = module_use.checked_states(states, found, tree, picked.accepted)
    shown = [line for line in lines if states.get(line, module_use.OPEN) == module_use.OPEN]
    refused = {row["answer"] for row in picked.refused}
    kept = [a for a in given if module_use.role_answer(a) is None or a.label not in refused]
    result = judgement.apply_answers(shown, kept, evidence)
    unused = refused_answers.correct_stale(result, states, found)
    rows = [*refused_answers.texts(given, lines), *picked.refused]
    result.refused.extend(row["text"] for row in rows)
    renamed = answer_migrations.renamed_items(cfg.judgement_answered)
    result.stale.extend(item for item in renamed if item not in result.stale)
    found_lines = boundary_findings(tree, facts, shown)
    counts = line_counts(tree, facts, shown, found_lines)
    counts |= {u.line: (module_use.user_count(u), "component") for u in found.units.values()}
    counts = {line: count for line, count in counts.items() if line in set(shown)}
    crossings, use_rows = role_records(tree, facts, found, picked, states)
    return Judged(
        shown,
        evidence,
        result,
        cfg.require_reviews,
        line_causes(shown, facts),
        line_sources(shown, facts),
        earlier_reviews(tree, facts),
        counts,
        assurance.of_tree(tree, facts),
        nest_join.all_fields(tree, found_lines),
        found_lines,
        crossings,
        use_rows,
        [line for line in lines if line not in set(shown)],
        rows,
        unused,
    )


def role_records(
    tree: nest.Tree,
    facts: dict[str, Any],
    found: module_use.Index,
    picked: module_use.Roles,
    states: Mapping[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Give the record of each import crossing and of each unit with a line in this run.

    The record of an import crossing has its state, its units with their module roles,
    and, for an open import crossing, the `handoff modules:` row. The record of a unit has
    the fields of `module_use` in the JSON object and the rows below its line."""
    prefixes = {m.id: m.prefix for m in tree.maps}
    crossings = {
        line: {
            "line": line,
            "map": c.map,
            "from": c.source,
            "to": c.target,
            "state": states[line],
            "modules": [{"module": u, "role": module_use.unit_role(u, picked)} for u in c.units],
            "rows": (
                [module_use.handoff_row(c, picked.accepted)]
                if states[line] == module_use.OPEN and any(u in picked.accepted for u in c.units)
                else []
            ),
        }
        for line, c in found.crossings.items()
    }
    refs = module_use.flow_refs(tree, facts) if found.units else []
    uses = {
        u.line: {
            "module": u.module,
            "component": u.component,
            "users": [
                {"map": user.map, "component": user.component, "names": list(user.names)}
                for user in u.users
            ],
            "waiting_crossings": sum(states.get(x) == module_use.WAITING for x in u.crossings),
            "role": module_use.unit_role(u.module, picked),
            "rows": module_use.unit_rows(u, found, states, refs, prefixes),
        }
        for u in found.units.values()
        if u.line_map is not None
    }
    return crossings, uses


def open_boundary(tree: nest.Tree, facts: dict[str, Any], cfg: Config) -> frozenset[str]:
    """This function gives the open `boundary flow` and `boundary import` lines of the
    tree. The set is the set of boundary lines in `evaluate(...).result.open`.

    The function applies the answers only to the boundary lines, with the evidence of the
    boundary lines (`judgement_evidence.boundary_evidence`). Thus it does not make the
    other judgement lines. An exact answer for a boundary line that also names a different
    line has a digest of all its items. For such an answer, the function uses `evaluate`.
    A tree with no nested map has no boundary line."""
    if not tree.nested:
        return frozenset()
    lines = [line for m in tree.reported for line in nest_join.lines(tree, m, facts)]
    given = [a for a in cfg.judgement_answered if not audit.is_audit_answer(a)]
    given = answer_migrations.current_lines(given, lines)
    present = set(lines)
    if any(_names_other_lines(a, lines, present) for a in given):
        judged = evaluate(tree, facts, cfg).result.open
        return frozenset(line for line in judged if nest_join.is_line(tree, line))
    evidence = judgement_evidence.boundary_evidence(tree, facts, lines)
    return frozenset(judgement.apply_answers(lines, given, evidence).open)


def _names_other_lines(answer: Answer, lines: list[str], present: set[str]) -> bool:
    """Tell if an exact answer selects a boundary line and has an item that is not a
    boundary line."""
    if not answer.items or not any(judgement.answers(answer, line, present) for line in lines):
        return False
    items = answer_migrations.current_items(answer.items, present)
    return any(item not in present for item in items)


def boundary_findings(
    tree: nest.Tree, facts: dict[str, Any], lines: list[str]
) -> dict[str, nest_join.Finding]:
    """Give the finding of each boundary line of `lines`. A tree with no nested map has
    no boundary lines."""
    present = set(lines)
    found = nest_join.findings(tree, facts) if tree.nested else {}
    return {line: one for line, one in found.items() if line in present}


def earlier_reviews(tree: nest.Tree, facts: dict[str, Any]) -> list[dict[str, str]]:
    """This function gives each flow with the review state `earlier` (`flow_review`).

    Such a review is current, so it gives no finding line. The report gives it as a row
    with the label, because the review digest does not identify the examined source.
    """
    return [
        {"map": m.id, "flow": flow.key}
        for m in tree.reported
        for flow in m.model.flows
        if flow_review.state(flow, m.meaning, facts) == flow_review.EARLIER
    ]


def earlier_rows(judged: Judged, tree: nest.Tree, teach: bool) -> list[str]:
    """This function gives the count rows of the import crossings and of the module roles
    (`module_use.count_rows`). Then it gives one text row for each flow review with the
    state `earlier`."""
    counts = module_use.count_rows(
        (row["state"] for row in judged.crossings.values()),
        (row["role"] for row in judged.uses.values()),
    )
    if not judged.earlier:
        return counts
    prefixes = {m.id: m.prefix for m in tree.maps}
    rows = [
        f"{flow_review.EARLIER_LABEL}: {prefixes.get(row['map'], '')}{row['flow']}"
        for row in judged.earlier
    ]
    action = (
        "  The review digest does not identify the examined source. Examine the flow claim "
        "against the source. Then use systemap review --flow ID."
    )
    return counts + rows + ([action] if teach else [])


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
                **judged.boundary.get(line, NO_BOUNDARY),
                "module_use": _use_row(judged.uses.get(line)),
            }
            for line in shown
        ],
        "answered": {
            "count": result.answered,
            "answers": [_answer_row(a, judged.lines) for a in result.accepted],
        },
        **role_fields(judged),
        "stale_answers": list(result.stale),
        "source_reviews": dict(reviews) if reviews is not None else None,
        "earlier_flow_reviews": [dict(row) for row in judged.earlier],
        "require_reviews": judged.require_reviews,
        "kinds": _kind_counts(judged.lines, result.open),
        "assurance": assurance.payload(judged.claims),
    }


def _answer_row(answer: Answer, lines: list[str]) -> dict[str, Any]:
    present = set(lines)
    return {
        "answer": answer.label,
        "items": list(answer.items),
        "reason": answer.reason,
        "lines": [line for line in lines if judgement.answers(answer, line, present)],
        "role": answer.role,
        "symbol": answer.symbol,
        "handoff": list(answer.handoff),
    }


def _use_row(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Give the `module_use` field of a row of `open`: None for a line of a different kind."""
    if row is None:
        return None
    keys = ("module", "component", "users", "waiting_crossings")
    return {key: row[key] for key in keys}


def role_fields(judged: Judged) -> dict[str, Any]:
    """Give the fields of the module roles: the refused answers, the unused answers, the
    states of the import crossings, and the module role counts of the units."""
    crossings = list(judged.crossings.values())
    states = [row["state"] for row in crossings]
    roles = [row["role"] for row in judged.uses.values()]
    keys = ("answer", "items", "cause", "text", "lines")
    return {
        "refused_answers": [{key: row[key] for key in keys} for row in judged.refused_rows],
        "unused_answers": list(judged.unused),
        "import_crossings": {
            **{state: states.count(state) for state in ("open", "waiting", "closed")},
            "crossings": [
                {key: row[key] for key in ("line", "map", "from", "to", "state", "modules")}
                for row in crossings
            ],
        },
        "module_roles": {
            role: roles.count(role) for role in ("helper", "handoff", "mixed", "refused", "none")
        },
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
