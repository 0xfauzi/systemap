"""Evidence on every flow: source reviewed, structural, external, or declared.

A fixture distinguishes structural evidence from source-reviewed claims;
the drawing dashes a declared edge and the panel says so;
the judgement prints one line per declared edge; `[flows] observed_by`
names the mechanisms and the answer forms cover the line kind.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import fixture_workspace
import pytest
from conftest import Sample, write_tree

from systemap import config, evidence, figure, judgement, page
from systemap import theme as theme_mod
from systemap.config import Answer, ConfigError
from systemap.model import all_layers
from systemap.schematic import render as render_schematic

# The sample: the parser imports the reader and the writer imports the
# ledger; nothing imports across the other two internal flows.
EXPECTED = {
    ("User", "Reader"): "external",
    ("Reader", "Parser"): "structural",
    ("Parser", "Writer"): "declared",
    ("Writer", "Ledger"): "structural",
    ("Ledger", "Parser"): "declared",
}


def test_structural_evidence_does_not_claim_a_flow_was_observed(sample: Sample) -> None:
    states = evidence.of_model(sample.model, sample.meaning, sample.facts)
    assert {edge: ev.state for edge, ev in states.items()} == EXPECTED
    assert all(ev.mechanism == "" for ev in states.values())
    assert states[("User", "Reader")].says == "external: The endpoint is outside the source code."
    assert states[("Reader", "Parser")].says == (
        "import present: The flow direction and artifact have no source review."
    )
    assert states[("Parser", "Writer")].says == "declared: The flow has no import evidence."
    # The artifact of Ledger -> Parser is `history`; named as a mechanism, the
    # flow has a declared mechanism. A word in the sentence counts the same
    # way, whole and case blind; a substring does not.
    states = evidence.of_model(sample.model, sample.meaning, sample.facts, ["queue", "history"])
    assert states[("Ledger", "Parser")] == evidence.Evidence("structural", "history")
    assert (
        states[("Ledger", "Parser")].says
        == "mechanism declared: history. The flow has no source review."
    )
    assert states[("Parser", "Writer")].state == "declared"
    states = evidence.of_model(sample.model, sample.meaning, sample.facts, ["In Order"])
    assert states[("Parser", "Writer")] == evidence.Evidence("structural", "In Order")
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


def test_source_review_refs_resolve_against_the_extracted_source(sample: Sample) -> None:
    module = "pkg.reader"
    digest = sample.facts["components"][module]["source_sha256"]
    ref = f"{module}:read@{digest}"
    model = dataclasses.replace(
        sample.model,
        flows=tuple(
            dataclasses.replace(
                flow,
                source_refs=(ref,),
                review_digest=evidence.flow_claim_digest(flow, sample.meaning),
            )
            if flow.edge == ("Reader", "Parser")
            else flow
            for flow in sample.model.flows
        ),
    )
    reviewed = evidence.of_model(model, sample.meaning, sample.facts)[("Reader", "Parser")]
    assert reviewed.state == evidence.OBSERVED
    assert reviewed.import_present
    assert reviewed.source_refs == (ref,)
    assert reviewed.says == "source reviewed: The references resolve at this source snapshot."
    _svg, detail = render_schematic(model, sample.meaning, sample.theme, sample.facts)
    edges = json.loads(detail)["_meta"]["edges"]
    edge = next(e for e in edges if (e["from"], e["to"]) == ("Reader", "Parser"))
    assert edge["source_refs"] == [ref]
    assert edge["import_present"]
    assert edge["unresolved_refs"] == []
    assert not edge["claim_changed"]
    assert edge["review_digest"] == evidence.flow_claim_digest(
        next(flow for flow in model.flows if flow.edge == ("Reader", "Parser")), sample.meaning
    )
    changed = copy.deepcopy(sample.facts)
    changed["components"][module]["source_sha256"] = "0" * 64
    stale = evidence.of_model(model, sample.meaning, changed)[("Reader", "Parser")]
    assert stale.state == evidence.STRUCTURAL
    assert stale.unresolved_refs == (ref,)
    assert "pending" in stale.says
    revised = dataclasses.replace(
        model,
        flows=tuple(
            dataclasses.replace(flow, artifact="different")
            if flow.edge == ("Reader", "Parser")
            else flow
            for flow in model.flows
        ),
    )
    invalid = evidence.of_model(revised, sample.meaning, sample.facts)[("Reader", "Parser")]
    assert invalid.state == evidence.STRUCTURAL
    assert invalid.claim_changed
    assert "digest is missing or different" in invalid.says
    bad_symbol = ref.replace(":read@", ":missing@")
    assert not evidence._resolves(bad_symbol, sample.facts)
    assert not evidence._resolves(f"{module}:read@not-a-digest", sample.facts)


def test_two_cards_sharing_a_module_have_structural_evidence() -> None:
    """A tool claimed by symbol inside its agent's module can never be joined
    by an import; the shared module is the evidence, and the panel says so."""
    model, meaning, facts = (
        fixture_workspace.MODEL,
        fixture_workspace.MEANING,
        fixture_workspace.facts(),
    )
    assert model.component("CropPicker").implemented_by == (
        "wharf_server.style.completer:pick_crops",
    )
    assert evidence.sharing_a_module(model, facts) == {frozenset({"StyleCompleter", "CropPicker"})}
    states = evidence.of_model(model, meaning, facts)
    assert states[("StyleCompleter", "CropPicker")] == evidence.Evidence("structural", shared=True)
    assert states[("StyleCompleter", "CropPicker")].says == (
        "shared module: The flow direction and artifact have no source review."
    )
    assert ("StyleCompleter", "CropPicker") not in {
        f.edge for f in evidence.declared(model, meaning, facts)
    }
    lines = judgement.run(model, meaning, facts)
    assert not [line for line in lines if "CropPicker" in line and line.startswith("declared flow")]
    # The drawing carries the state and the line, so the page and a figure agree.
    t = theme_mod.resolve({}, all_layers(model, meaning))
    _svg, detail = render_schematic(model, meaning, t, facts)
    by_edge = {(e["from"], e["to"]): e for e in json.loads(detail)["_meta"]["edges"]}
    picker = by_edge[("StyleCompleter", "CropPicker")]
    assert (picker["evidence"], picker["mechanism"], picker["evidence_says"]) == (
        "structural",
        "",
        "shared module: The flow direction and artifact have no source review.",
    )
    # A symbol claim on the card's own module, or on a module no card claims,
    # joins no pair; an import still wins the wording when both hold.
    own = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(
                c, implemented_by=(*c.implemented_by, "wharf_server.style.completer:complete")
            )
            if c.id == "StyleCompleter"
            else dataclasses.replace(c, implemented_by=("wharf_server.nowhere:pick",))
            if c.id == "CropPicker"
            else c
            for c in model.components
        ),
    )
    assert evidence.sharing_a_module(own, facts) == set()
    assert (
        evidence.of_model(own, meaning, facts)[("StyleCompleter", "CropPicker")].state == "declared"
    )
    imported = copy.deepcopy(facts)
    imported["components"]["wharf_server.style.completion_eval"]["uses"] = {
        "wharf_server.style.completer": ["pick_crops"]
    }
    assert evidence.of_model(model, meaning, imported)[("StyleCompleter", "CropPicker")].says == (
        "shared module: The flow direction and artifact have no source review."
    ), "an import inside one module is not a crossing import; the module is still shared"


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
        assert ('stroke-dasharray="3 4"' in paths[edge]) == (state == "structural"), edge
    meta = json.loads(detail)["_meta"]
    by_edge = {(e["from"], e["to"]): e for e in meta["edges"]}
    assert by_edge[("Parser", "Writer")]["evidence"] == "declared"
    assert (
        by_edge[("Parser", "Writer")]["evidence_says"]
        == "declared: The flow has no import evidence."
    )
    assert by_edge[("Parser", "Writer")]["mechanism"] == ""
    assert meta["evidence"] == {"observed": 0, "structural": 2, "external": 1, "declared": 2}
    # With the mechanism configured, the edge stays unreviewed and says why.
    svg, detail = render_schematic(
        sample.model, sample.meaning, sample.theme, sample.facts, observed_by=("history",)
    )
    meta = json.loads(detail)["_meta"]
    by_edge = {(e["from"], e["to"]): e for e in meta["edges"]}
    assert by_edge[("Ledger", "Parser")]["evidence_says"] == (
        "mechanism declared: history. The flow has no source review."
    )
    assert meta["evidence"] == {"observed": 0, "structural": 3, "external": 1, "declared": 1}
    assert svg.count('stroke-dasharray="7 5"') == 1
    # The page and a figure carry the legend entry and the panel's line.
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    assert 'class="lg--dashline"' in html and ">flow without source review</span>" in html
    assert "A short dashed line shows structural evidence" in html
    assert "A long dashed line has no structural evidence" in html
    assert "For both dashed states, source review of direction and artifact is necessary" in html
    assert "No flow records program execution" in html
    assert "declared: The flow has no import evidence." in html
    assert "data-evidence" in html and "evidence_says" in html
    fig, _collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, bare=True
    )
    assert fig.count('stroke-dasharray="7 5"') == 2
    fig, _collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="structure"
    )
    assert "flow without source review</span>" not in fig, (
        "a figure with no edges has no dashed line to explain"
    )
    fig, _collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts
    )
    assert "flow without source review</span>" in fig


def test_judgement_prints_one_line_per_declared_edge(sample: Sample) -> None:
    lines = judgement.run(sample.model, sample.meaning, sample.facts)
    declared = [line for line in lines if line.startswith("declared flow: ")]
    assert declared == [
        "declared flow: Parser -> Writer (parts): no import connects them. Find the evidence, give the mechanism in the description, or remove the flow.",
        "declared flow: Ledger -> Parser (history): no import connects them. Find the evidence, give the mechanism in the description, or remove the flow.",
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
        ('[flows]\nobserved_by = "queue"\n', "observed_by must be a list of strings."),
        ('[flows]\nobserved_by = [""]\n', "must contain a word for each mechanism"),
        ('[flows]\nmechanisms = ["queue"]\n', "flows has an unknown key: mechanisms"),
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
