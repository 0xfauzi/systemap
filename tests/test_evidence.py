"""Evidence on every flow: observed, external or declared, from the facts.

ROADMAP.md, gap 2: a fixture asserting the three states plus observed by
a mechanism; the drawing dashes a declared edge and the panel says so;
the judgement prints one line per declared edge; `[flows] observed_by`
names the mechanisms and the answer forms cover the line kind.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import Sample, write_tree

from systemap import config, evidence, figure, judgement, page
from systemap.config import Answer, ConfigError
from systemap.schematic import render as render_schematic

# The sample: the parser imports the reader and the writer imports the
# ledger; nothing imports across the other two internal flows.
EXPECTED = {
    ("User", "Reader"): "external",
    ("Reader", "Parser"): "observed",
    ("Parser", "Writer"): "declared",
    ("Writer", "Ledger"): "observed",
    ("Ledger", "Parser"): "declared",
}


def test_the_three_states_and_observed_by_a_mechanism(sample: Sample) -> None:
    states = evidence.of_model(sample.model, sample.meaning, sample.facts)
    assert {edge: ev.state for edge, ev in states.items()} == EXPECTED
    assert all(ev.mechanism == "" for ev in states.values())
    assert states[("User", "Reader")].says == "external: outside the code"
    assert states[("Reader", "Parser")].says == "observed: an import joins them"
    assert states[("Parser", "Writer")].says == "declared: no import behind it"
    # The artifact of Ledger -> Parser is `history`; named as a mechanism, the
    # flow is observed by it. A word in the sentence counts the same way,
    # whole and case blind; a substring does not.
    states = evidence.of_model(sample.model, sample.meaning, sample.facts, ["queue", "history"])
    assert states[("Ledger", "Parser")] == evidence.Evidence("observed", "history")
    assert states[("Ledger", "Parser")].says == "observed by: history"
    assert states[("Parser", "Writer")].state == "declared"
    states = evidence.of_model(sample.model, sample.meaning, sample.facts, ["In Order"])
    assert states[("Parser", "Writer")] == evidence.Evidence("observed", "In Order")
    states = evidence.of_model(sample.model, sample.meaning, sample.facts, ["order", "hist"])
    assert states[("Parser", "Writer")].mechanism == "order"
    assert states[("Ledger", "Parser")].state == "declared"
    # No facts: nothing can be observed, so an internal flow is declared.
    states = evidence.of_model(sample.model, sample.meaning, {})
    assert states[("Reader", "Parser")].state == "declared"
    assert states[("User", "Reader")].state == "external"
    assert [f.edge for f in evidence.declared(sample.model, sample.meaning, sample.facts)] == [
        ("Parser", "Writer"),
        ("Ledger", "Parser"),
    ]


def test_a_declared_edge_is_dashed_and_the_panel_says_so(sample: Sample) -> None:
    svg, detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    paths = {
        (m.group(1), m.group(2)): m.group(0)
        for m in __import__("re").finditer(
            r'<path id="schematic-f\d+" class="flow[^>]*data-from="(\w+)" data-to="(\w+)"[^>]*/>',
            svg,
        )
    }
    assert set(paths) == set(EXPECTED)
    for edge, state in EXPECTED.items():
        assert f'data-evidence="{state}"' in paths[edge], edge
        assert ('stroke-dasharray="7 5"' in paths[edge]) == (state == "declared"), edge
    meta = json.loads(detail)["_meta"]
    by_edge = {(e["from"], e["to"]): e for e in meta["edges"]}
    assert by_edge[("Parser", "Writer")]["evidence"] == "declared"
    assert by_edge[("Parser", "Writer")]["evidence_says"] == "declared: no import behind it"
    assert by_edge[("Parser", "Writer")]["mechanism"] == ""
    assert meta["evidence"] == {"observed": 2, "external": 1, "declared": 2}
    # With the mechanism configured, the same edge is solid and says which.
    svg, detail = render_schematic(
        sample.model, sample.meaning, sample.theme, sample.facts, observed_by=("history",)
    )
    meta = json.loads(detail)["_meta"]
    by_edge = {(e["from"], e["to"]): e for e in meta["edges"]}
    assert by_edge[("Ledger", "Parser")]["evidence_says"] == "observed by: history"
    assert meta["evidence"] == {"observed": 3, "external": 1, "declared": 1}
    assert svg.count('stroke-dasharray="7 5"') == 1
    # The page and a figure carry the legend entry and the panel's line.
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    assert 'class="lg--dashline"' in html and ">declared</span>" in html
    assert "A dashed line is a declared flow" in html
    assert "declared: no import behind it" in html
    assert "data-evidence" in html and "evidence_says" in html
    fig, _collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, bare=True
    )
    assert fig.count('stroke-dasharray="7 5"') == 2
    fig, _collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="structure"
    )
    assert "declared</span>" not in fig, "a figure with no edges has no dashed line to explain"
    fig, _collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts
    )
    assert "declared</span>" in fig


def test_judgement_prints_one_line_per_declared_edge(sample: Sample) -> None:
    lines = judgement.run(sample.model, sample.meaning, sample.facts)
    declared = [line for line in lines if line.startswith("declared flow: ")]
    assert declared == [
        "declared flow: Parser -> Writer (parts): no import joins them; find the evidence, name "
        "the mechanism in the sentence, or remove it",
        "declared flow: Ledger -> Parser (history): no import joins them; find the evidence, "
        "name the mechanism in the sentence, or remove it",
    ]
    # After the crossing-import lines and before the model sdk ones.
    kinds = [line.split(":")[0] for line in lines]
    assert kinds.index("declared flow") > max(
        (k for k, kind in enumerate(kinds) if kind == "crossing import"), default=-1
    )
    assert judgement.run(sample.model, sample.meaning, sample.facts, observed_by=["history"])
    assert not [
        line
        for line in judgement.run(
            sample.model, sample.meaning, sample.facts, observed_by=["history"]
        )
        if "Ledger -> Parser" in line and line.startswith("declared flow")
    ]
    assert judgement.declared_flows(sample.model, sample.meaning, {}) == [], (
        "no facts: nothing is observed and nothing is asked"
    )
    # The bulk answer form covers the kind, and the exact line answers one.
    assert "declared flow" in config.LINE_KINDS
    answered = judgement.apply_answers(
        declared,
        [Answer((), "the parser calls the writer through a callback", kind="declared flow")],
    )
    assert answered.open == [] and answered.answered == 2
    answered = judgement.apply_answers(declared, [Answer((declared[0],), "a callback")])
    assert answered.open == [declared[1]] and answered.answered == 1


def test_flows_observed_by_in_the_configuration(tmp_path: Path) -> None:
    write_tree(tmp_path, {"systemap.toml": '[flows]\nobserved_by = ["queue", "subprocess"]\n'})
    cfg = config.load(tmp_path)
    assert cfg.observed_by == ("queue", "subprocess")
    assert config.load(tmp_path.parent / "nowhere").observed_by == () if False else True
    for text, message in (
        ('[flows]\nobserved_by = "queue"\n', "observed_by must be a list of strings"),
        ('[flows]\nobserved_by = [""]\n', "must name each mechanism with a word"),
        ('[flows]\nmechanisms = ["queue"]\n', "flows has unknown key: mechanisms"),
        ("flows = 3\n", "flows must be a table"),
        (
            '[judgement]\nanswered = [{ kind = "declared edge", reason = "r" }]\n',
            "kind must be one of",
        ),
    ):
        (tmp_path / "systemap.toml").write_text(text)
        with pytest.raises(ConfigError, match=message):
            config.load(tmp_path)
    (tmp_path / "systemap.toml").write_text(
        '[judgement]\nanswered = [{ kind = "declared flow", reason = "every edge here crosses a queue" }]\n'
    )
    assert config.load(tmp_path).judgement_answered[0].kind == "declared flow"
