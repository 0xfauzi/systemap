"""The page must match the CLI's evidence-bound answer decisions.

Acceptance: zero accepted exact answers after their source evidence changes,
and preserved reasons and identifiers for current answers and explicit policies.
Audit answer families must not interrupt a page's mechanical review.
"""

from __future__ import annotations

import dataclasses

import pytest
from conftest import Sample

from systemap import audit, judgement, nest, page, page_data
from systemap.config import Answer


def reviewed_tree(sample: Sample) -> nest.Tree:
    path = sample.cfg.root / sample.cfg.model
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"from systemap.model import *\nMODEL = {sample.model!r}\nMEANING = {sample.meaning!r}\n"
    )
    return nest.load(sample.cfg)


def test_current_exact_answer_retains_its_reason_then_reopens_after_source_edit(
    sample: Sample,
) -> None:
    tree = reviewed_tree(sample)
    lines = judgement.run_tree(tree, sample.facts)
    current = judgement.evidence_for_tree(tree, sample.facts, sample.cfg.root, lines)
    answer = Answer(
        items=(lines[0],),
        reason="This part has a separate responsibility.",
        evidence=judgement.answer_digest((lines[0],), current),
    )
    cfg = dataclasses.replace(sample.cfg, judgement_answered=(answer,))
    data = page_data.tree_review(cfg, tree, tree.top, sample.facts)
    assert [r["line"] for r in data["open"]] == lines[1:]
    assert data["answered"][0]["line"] == lines[0]
    assert data["answered"][0]["reasons"] == [answer.reason]
    assert not data["pending"]

    source = sample.cfg.root / "pkg/reader.py"
    source.write_text(source.read_text() + "\nNEW_VALUE = 1\n")
    changed = page_data.tree_review(cfg, tree, tree.top, sample.facts)
    assert [r["line"] for r in changed["open"]] == lines
    assert not changed["answered"]
    assert "must have a new source review" in changed["pending"][0]


def test_explicit_policy_notice_is_retained_by_programmatic_page(sample: Sample) -> None:
    answer = Answer(
        items=(), kind="single module", policy=True, reason="These parts have separate jobs."
    )
    cfg = dataclasses.replace(sample.cfg, judgement_answered=(answer,))
    data = page_data.review(cfg, sample.model, sample.meaning, sample.facts)
    assert data["answered"]
    assert data["policies"] and "outside the source-review baseline" in data["policies"][0]
    html = page.build(cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    assert "Policy answers" in html
    assert "outside the source-review baseline" in html


def test_audit_policy_preserves_mechanical_exact_answer_and_page(sample: Sample) -> None:
    tree = reviewed_tree(sample)
    lines = judgement.run_tree(tree, sample.facts)
    current = judgement.evidence_for_tree(tree, sample.facts, sample.cfg.root, lines)
    exact = Answer(
        items=(lines[0],),
        reason="This part has a separate responsibility.",
        evidence=judgement.answer_digest((lines[0],), current),
    )
    policy = Answer(
        items=(), kind="jev flow", policy=True, reason="The reviewed event joins are intended."
    )
    mechanical_cfg = dataclasses.replace(sample.cfg, judgement_answered=(exact,))
    mixed_cfg = dataclasses.replace(sample.cfg, judgement_answered=(exact, policy))
    expected = page_data.tree_review(mechanical_cfg, tree, tree.top, sample.facts)
    actual = page_data.tree_review(mixed_cfg, tree, tree.top, sample.facts)
    assert actual == expected
    assert actual["answered"][0]["line"] == lines[0]
    assert actual["answered"][0]["reasons"] == [exact.reason]
    html = page.build(
        mixed_cfg,
        sample.model,
        sample.meaning,
        sample.theme,
        sample.facts,
        {},
        nesting=page.nesting_of(mixed_cfg, tree, tree.top, sample.facts),
    )
    assert exact.reason in html
    assert policy.reason not in html


@pytest.mark.parametrize(
    "case",
    [
        "exact",
        "nested",
        "group",
        "policy",
        "unbound-family",
        "mixed-group",
        "stale-group",
        "mixed-policy",
    ],
)
def test_page_answer_results_match_cli_selection(sample: Sample, case: str) -> None:
    tree = reviewed_tree(sample)
    lines = judgement.run_tree(tree, sample.facts)
    current = judgement.evidence_for_tree(tree, sample.facts, sample.cfg.root, lines)
    audit_line = "jev flow: Reader -> Parser needs review"
    nested_line = "Gateway: jev flow: Reader -> Parser needs review"

    def exact(items: tuple[str, ...]) -> Answer:
        return Answer(items, "Reviewed answer.", evidence=judgement.answer_digest(items, current))

    policy = Answer((), "Explicit audit policy.", kind="jev flow", policy=True)
    grouped = exact((lines[0], audit_line, nested_line))
    cases = {
        "exact": exact((audit_line,)),
        "nested": exact((nested_line,)),
        "group": exact((audit_line, nested_line)),
        "policy": policy,
        "unbound-family": dataclasses.replace(policy, policy=False),
        "mixed-group": grouped,
        "stale-group": dataclasses.replace(grouped, evidence="0" * 64),
        "mixed-policy": policy,
    }
    first = (
        Answer((), "Mechanical policy.", kind=judgement.kind_of(lines[0]), policy=True)
        if case == "mixed-policy"
        else exact((lines[0],))
    )
    answers = (first, cases[case])
    cfg = dataclasses.replace(sample.cfg, judgement_answered=answers)
    cli_answers = [answer for answer in answers if not audit.is_audit_answer(answer)]
    expected = judgement.apply_answers(lines, cli_answers, current)
    actual = page_data.tree_review(cfg, tree, tree.top, sample.facts)
    assert [record["line"] for record in actual["open"]] == expected.open
    assert len(actual["answered"]) == expected.answered
    assert actual["pending"] == expected.pending
    assert actual["policies"] == expected.policies
    accepted = [
        answer
        for answer in cli_answers
        if judgement.apply_answers(lines, (answer,), current).answered
    ]
    for record in actual["answered"]:
        assert record["reasons"] == [
            answer.reason for answer in accepted if judgement.answers(answer, record["line"])
        ]


def test_unavailable_model_file_leaves_exact_answers_pending(sample: Sample) -> None:
    tree = reviewed_tree(sample)
    lines = judgement.run_tree(tree, sample.facts)
    cfg = dataclasses.replace(
        sample.cfg,
        judgement_answered=(Answer(items=(lines[0],), evidence="old", reason="Earlier review."),),
    )
    tree.top.path.unlink()
    data = page_data.tree_review(cfg, tree, tree.top, sample.facts)
    assert not data["answered"]
    assert "unavailable" in data["pending"][0]
    html = page.build(cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    assert "Answers for examination" in html
