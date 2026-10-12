"""One review state for each component, and source records that touch the flow.

Acceptance: delta and judgement use one evaluator for the review state of a component.
A map that passed `judgement --strict` fails it after this change only if a review is
stale. A missing review is a count, not a finding. A flow whose source records are in no
module of an endpoint is not `observed`, and judgement gives one `no endpoint source` line
for it. The reader text for `observed` is "current source review".
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, Sample, init_two_cards, write_tree

from systemap import (
    card_review,
    config,
    delta,
    describe,
    evidence,
    explain,
    extract,
    judgement,
    nest,
    page,
)
from systemap.cli import main
from systemap.config import Config
from systemap.model import Component, Flow, Meaning, Model
from systemap.schematic import render as render_schematic

# ---- one review state ------------------------------------------------------------


def _one_card(review: str = "") -> tuple[Component, Model, Meaning]:
    card = Component("Reader", "Reads inputs.", implemented_by=("pkg.reader",))
    card = dataclasses.replace(card, source_review=review)
    return card, Model((800, 600), (), (), (card,), (), ()), Meaning({"Reader": "Reader"})


# A shared reader accepts only a module record with a parsed completeness record.
PARSED = {"parsed": True, "line": 0, "reason": "", "unresolved_imports": []}
FACTS: dict[str, Any] = {
    "components": {"pkg.reader": {"syntax_sha": "one", "completeness": PARSED}}
}
CHANGED: dict[str, Any] = {
    "components": {"pkg.reader": {"syntax_sha": "two", "completeness": PARSED}}
}


def test_the_review_state_is_missing_stale_or_current() -> None:
    card, model, meaning = _one_card()
    assert card_review.state(card, model, meaning, FACTS) == card_review.MISSING
    now = card_review.digest(card, model, meaning, FACTS)
    assert now is not None
    card, model, meaning = _one_card(now)
    assert card_review.state(card, model, meaning, FACTS) == card_review.CURRENT
    assert card_review.state(card, model, meaning, CHANGED) == card_review.STALE
    # Without a current digest, a recorded review cannot be current.
    assert card_review.state(card, model, meaning, {"components": {}}) == card_review.STALE
    assert card_review.STATES == ("current", "stale", "missing")


def _delta_lines(card: Component, model: Model, meaning: Meaning) -> list[str]:
    lines = delta._evidence_review_lines(
        Config(Path("."), "Example", ()),
        model,
        meaning,
        FACTS,
        CHANGED,
        model,
        model,
        " at the base commit",
        "map/model.py",
    )
    return [line.text for line in lines if line.kind == "source review"]


def test_delta_and_judgement_read_the_same_review_state(monkeypatch: pytest.MonkeyPatch) -> None:
    card, model, meaning = _one_card()
    stale_digest = card_review.digest(card, model, meaning, FACTS)
    assert stale_digest is not None
    card, model, meaning = _one_card(stale_digest)
    # The code changed after the review: delta asks for a source review, and judgement
    # gives the same component as a stale review.
    assert _delta_lines(card, model, meaning) == [
        "source review: Reader has changed code in pkg.reader. Compare its description, "
        "flows, sequences, and invariants with the new source."
    ]
    assert judgement.stale_source_reviews(model, meaning, CHANGED) == [
        "stale source review: Reader has a source_review digest that is not the current "
        "digest. Examine its source and claims again. Then record the current digest."
    ]
    assert judgement.stale_source_reviews(model, meaning, FACTS) == []
    # A missing review: delta keeps its line, and judgement gives no finding.
    card, model, meaning = _one_card()
    assert len(_delta_lines(card, model, meaning)) == 1
    assert judgement.stale_source_reviews(model, meaning, CHANGED) == []
    # Delta reads the one evaluator.
    monkeypatch.setattr(card_review, "state", lambda *_args: card_review.CURRENT)
    assert _delta_lines(card, model, meaning) == []


def _two_cards(root: Path) -> None:
    write_tree(root, {**STARTER_MODULES, "pkg/__init__.py": ""})
    init_two_cards(root)
    answers = ", ".join(
        f'{{ kind = "{kind}", policy = true, reason = "a test" }}'
        for kind in ("single module", "thin layer", "flow review")
    )
    with (root / "systemap.toml").open("a", encoding="utf-8") as out:
        out.write(f"\n[judgement]\nanswered = [{answers}]\n")
    assert main(["--root", str(root), "extract"]) == 0


def _review(root: Path, value: str) -> None:
    path = root / "map/model.py"
    text = re.sub(r' source_review="\w*",', "", path.read_text(encoding="utf-8"))
    old = 'implemented_by=("pkg.reader",),'
    path.write_text(text.replace(old, f'{old} source_review="{value}",'), encoding="utf-8")


def test_judgement_strict_fails_on_a_stale_review_and_counts_a_missing_review(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_cards(tmp_path)
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "judgement", "--strict", "--brief"]) == 0
    out = capsys.readouterr().out
    assert "stale source review" not in out
    assert "source reviews: 0 current, 0 stale, 2 missing" in out.splitlines()
    _review(tmp_path, "0" * 64)
    assert main(["--root", str(tmp_path), "judgement", "--strict", "--brief"]) == 1
    out = capsys.readouterr().out
    assert (
        "  stale source review: Reader has a source_review digest that is not the current "
        "digest. Examine its source and claims again. Then record the current digest."
    ) in out.splitlines()
    assert "source reviews: 0 current, 1 stale, 1 missing" in out.splitlines()
    cfg = config.load(tmp_path)
    tree = nest.load(cfg)
    facts = extract.read_facts(cfg.facts_path)
    reader = next(c for c in tree.top.model.components if c.id == "Reader")
    current = card_review.digest(reader, tree.top.model, tree.top.meaning, facts)
    assert current is not None
    _review(tmp_path, current)
    assert main(["--root", str(tmp_path), "judgement", "--strict", "--brief"]) == 0
    assert "source reviews: 1 current, 0 stale, 1 missing" in capsys.readouterr().out


def test_the_new_kinds_have_explanations_and_answer_forms() -> None:
    for kind in ("stale source review", "no endpoint source"):
        assert kind in config.LINE_KINDS
        found = explain.lesson(kind)
        assert found is not None
        assert found.means and found.why.endswith(".") and found.do.endswith(".")
    line = "stale source review: Reader has a source_review digest that is not current."
    assert judgement.kind_of(line) == "stale source review"
    assert judgement.kind_of(f"Gateway: {line}") == "stale source review"


# ---- source records that touch the flow ----------------------------------------------


def _with_refs(sample: Sample, edge: tuple[str, str], module: str) -> Model:
    digest = sample.facts["components"][module]["source_sha256"]
    return dataclasses.replace(
        sample.model,
        flows=tuple(
            dataclasses.replace(
                flow,
                source_refs=(f"{module}@{digest}",),
                review_digest=evidence.flow_claim_digest(flow, sample.meaning),
            )
            if flow.edge == edge
            else flow
            for flow in sample.model.flows
        ),
    )


def test_a_source_record_outside_the_endpoints_is_not_observed(sample: Sample) -> None:
    edge = ("Reader", "Parser")
    model = _with_refs(sample, edge, "pkg.parser")
    assert evidence.of_model(model, sample.meaning, sample.facts)[edge].state == "observed"
    assert judgement.no_endpoint_source(model) == []
    model = _with_refs(sample, edge, "pkg.ledger")
    found = evidence.of_model(model, sample.meaning, sample.facts)[edge]
    assert found.state == evidence.STRUCTURAL
    assert found.no_endpoint_ref and not found.unresolved_refs and not found.claim_changed
    assert found.says == (
        "source review pending: No source record is in a module of a flow endpoint."
    )
    assert judgement.no_endpoint_source(model) == [
        "no endpoint source: Reader -> Parser (parse): no source record is in a module of "
        "Reader or Parser. Add a source record in a module of Reader or Parser, or change "
        "the flow."
    ]
    lines = judgement.run(model, sample.meaning, sample.facts)
    assert sum(line.startswith("no endpoint source: ") for line in lines) == 1


def test_an_actor_end_needs_a_source_record_of_the_other_end(sample: Sample) -> None:
    edge = ("User", "Reader")
    model = _with_refs(sample, edge, "pkg.ledger")
    assert evidence.of_model(model, sample.meaning, sample.facts)[edge].state == "external"
    assert judgement.no_endpoint_source(model) == [
        "no endpoint source: User -> Reader (input): no source record is in a module of "
        "Reader. Add a source record in a module of Reader, or change the flow."
    ]
    assert judgement.no_endpoint_source(_with_refs(sample, edge, "pkg.reader")) == []


def test_package_patterns_and_symbol_claims_put_a_component_in_a_module() -> None:
    def touches(claims: tuple[str, ...], ref: str) -> bool:
        cards = (
            Component("A", "Reads.", implemented_by=claims),
            Component("B", "Writes.", implemented_by=("other.writer",)),
            Component("User", "Types.", kind="actor"),
        )
        model = Model((800, 600), (), (), cards, (), ())
        return evidence.cites_an_endpoint(Flow("A", "B", "x", "data", (ref,)), model)

    digest = "0" * 64
    assert touches(("pkg.*",), f"pkg.deep.reader:read@{digest}")
    assert touches(("pkg.reader:read",), f"pkg.reader@{digest}")
    assert touches(("pkg.reader",), f"other.writer@{digest}")
    assert not touches(("pkg.reader",), f"pkg.parser@{digest}")
    assert not touches(("pkg.reader:read",), f"pkg.parser@{digest}")
    cards = (Component("User", "Types.", kind="actor"), Component("Bot", "Answers.", kind="actor"))
    model = Model((800, 600), (), (), cards, (), ())
    # No endpoint has a module claim, so no source record can be in an endpoint module.
    assert evidence.cites_an_endpoint(Flow("User", "Bot", "x", "data", (f"pkg@{digest}",)), model)


# ---- the reader text for `observed` --------------------------------------------------


def test_the_reader_text_for_observed_is_current_source_review(sample: Sample) -> None:
    edge = ("Reader", "Parser")
    model = _with_refs(sample, edge, "pkg.parser")
    found = evidence.of_model(model, sample.meaning, sample.facts)[edge]
    assert found.says == (
        "current source review: The source records agree with this source snapshot."
    )
    svg, detail = render_schematic(model, sample.meaning, sample.theme, sample.facts)
    assert ', current source review"' in svg and "source review recorded" not in svg
    html = page.build(sample.cfg, model, sample.meaning, sample.theme, sample.facts, {})
    assert ">current source review</span>" in html
    assert "source review recorded" not in html
    assert "'with a current source review'" in html
    assert "A solid internal line has a current source review." in html
    out = "\n".join(describe.run(model, sample.meaning, sample.theme, sample.facts))
    assert "evidence: 1 observed (current source review), 1 structural (an import," in out
    assert json.loads(detail)["_meta"]["evidence"]["observed"] == 1


def test_the_lost_evidence_line_does_not_say_observed(sample: Sample) -> None:
    edge = ("Parser", "Writer")
    model = _with_refs(sample, edge, "pkg.parser")
    base = evidence.of_model(model, sample.meaning, sample.facts)
    assert base[edge].state == "observed"
    head = {**base, edge: evidence.Evidence(evidence.DECLARED)}
    lines = delta._flow_review_lines(model, base, head, " at abc1234", "map/model.py")
    assert [line.text for line in lines] == [
        "evidence lost: Parser -> Writer (parts) had a current source review at abc1234 and "
        "no import connects them now. Find the evidence, give the mechanism, or remove the "
        "flow in map/model.py"
    ]
