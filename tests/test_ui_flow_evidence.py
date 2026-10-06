"""The generated inspector preserves the limits of each flow's evidence.

Acceptance: zero unreviewed claims labelled source review recorded, zero missing
review warnings or source records, and zero substituted flow selections.
Selection preserves every original dash and has at most one moving cue.
Reduced motion has zero moving cues. The local DOM harness checks interaction
semantics and escaped content, without claiming browser layout coverage.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample

from systemap import evidence, extract, page
from systemap.model import Flow
from systemap.schematic import render as render_schematic

UNSAFE_REF = '<img src=x onerror="bad()"> & </script>'

SCENARIO = r"""
function flowevidence(page) {
  const {doc, win, svg, A} = page;
  const panel = doc.getElementById('panel');
  const dashes = () => svg.querySelectorAll('.flow').map(p =>
    p.getAttribute('stroke-dasharray'));
  const moving = () => svg.querySelectorAll('.moving').length;
  const report = {reduced:page.reduced, originalDashes:dashes(), flows:[]};
  function snapshot(i) {
    const choice=panel.querySelector('[data-inspect-edge="'+i+'"]');
    const path=svg.querySelector('.flow[data-edge="'+i+'"]');
    const refs=panel.querySelector('.systemap-f__refs');
    return {edge:A.state.edge, focus:A.state.focus,
      artifact:panel.querySelector('.systemap-f__artifact').textContent,
      explanation:panel.querySelector('[data-say]').textContent,
      evidence:panel.querySelector('[data-evidence-state]').textContent,
      evidenceState:panel.querySelector('[data-evidence-state]').dataset.evidenceState,
      evidenceSays:panel.querySelector('[data-evidence]').textContent,
      reason:panel.querySelector('.systemap-f__reason').textContent,
      claimChanged:!!panel.querySelector('[data-claim-changed]'),
      warnings:panel.querySelectorAll('.systemap-f__review-warning').map(p=>p.textContent),
      unresolved:panel.querySelectorAll('[data-unresolved-refs] li code').map(c=>c.textContent),
      sourceRefs:panel.querySelectorAll('.systemap-f__refs li code').map(c=>c.textContent),
      sourceDetails:refs ? refs.textContent : '',
      injected:panel.querySelectorAll('img, script').length,
      pathDash:path.getAttribute('stroke-dasharray'),
      pathLabel:path.getAttribute('aria-label'),
      pathSelected:path.getAttribute('aria-pressed'),
      choiceSelected:choice.getAttribute('aria-pressed'),
      choiceEvidence:choice.dataset.evidenceState,
      choiceLabel:choice.querySelector('small').textContent,
      selected:svg.querySelectorAll('.flowlbl[aria-pressed="true"]').map(l=>+l.dataset.edge),
      dashes:dashes(), moving:moving()};
  }
  [1,3,2,4].forEach(i=>{
    const e=A.edges[i];
    svg.querySelector('.flowlbl[data-edge="'+i+'"]').click();runFrames(win);
    const states=[snapshot(i)];
    [e.to,e.from].forEach(id=>{
      panel.querySelector('[data-endpoint="'+id+'"]').click();runFrames(win);
      states.push(snapshot(i));
    });
    const choice=panel.querySelector('[data-inspect-edge="'+i+'"]');
    choice.focus();page.key('Enter',choice);runFrames(win);states.push(snapshot(i));
    const path=svg.querySelector('.flow[data-edge="'+i+'"]');
    path.focus();page.key('Enter',path);runFrames(win);states.push(snapshot(i));
    report.flows.push({index:i,metadata:e,states:states});
  });
  A.setMotion(false);report.userReduced=moving();
  A.setMotion(true);report.restoredMotion=moving();
  A.clear();doc.getElementById('view-reading').click();
  doc.querySelector('[data-layer-btn="all"]').click();
  report.readingLabels=doc.getElementById('atlas').querySelectorAll('.reading-flow')
    .map(article=>article.querySelector('.reading-meta').textContent);
  return report;
}
"""


def reviewed_flow(sample: Sample, index: int, refs: tuple[str, ...]) -> Flow:
    flow = dataclasses.replace(sample.model.flows[index], source_refs=refs)
    return dataclasses.replace(flow, review_digest=evidence.flow_claim_digest(flow, sample.meaning))


@pytest.fixture
def evidence_sample(sample: Sample) -> Sample:
    records = sample.facts["components"]
    reader_ref = f"pkg.reader:read@{records['pkg.reader']['source_sha256']}"
    parser_ref = f"pkg.parser:parse@{records['pkg.parser']['source_sha256']}"
    ledger_ref = f"pkg.ledger:Ledger@{records['pkg.ledger']['source_sha256']}"
    flows = list(sample.model.flows)
    flows[1] = reviewed_flow(sample, 1, (reader_ref,))
    flows[2] = dataclasses.replace(
        reviewed_flow(sample, 2, (parser_ref,)), artifact="changed parts"
    )
    flows[4] = reviewed_flow(sample, 4, (ledger_ref, UNSAFE_REF))
    source = sample.cfg.root / "pkg/ledger.py"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nNEW_VALUE = 1\n",
        encoding="utf-8",
        newline="\n",
    )
    return dataclasses.replace(
        sample,
        model=dataclasses.replace(sample.model, flows=tuple(flows)),
        facts=extract.build(sample.cfg),
    )


def metadata(sample: Sample) -> list[dict[str, Any]]:
    _, detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    return json.loads(detail)["_meta"]["edges"]  # type: ignore[no-any-return]


def test_generated_metadata_retains_review_and_independent_structure(
    evidence_sample: Sample,
) -> None:
    sample = evidence_sample
    edges = metadata(sample)
    assert [e["evidence"] for e in edges] == [
        "external",
        "observed",
        "declared",
        "structural",
        "declared",
    ]
    for index in (1, 2, 4):
        assert edges[index]["source_refs"] == list(sample.model.flows[index].source_refs)
        assert edges[index]["review_digest"] == sample.model.flows[index].review_digest
    assert edges[1]["import_present"] and not edges[1]["shared_module"]
    assert not edges[1]["claim_changed"] and not edges[1]["unresolved_refs"]
    assert edges[2]["claim_changed"] and not edges[2]["unresolved_refs"]
    assert not edges[4]["claim_changed"]
    assert edges[4]["unresolved_refs"] == list(sample.model.flows[4].source_refs)
    ledger_hash = hashlib.sha256((sample.cfg.root / "pkg/ledger.py").read_bytes()).hexdigest()
    assert sample.facts["components"]["pkg.ledger"]["source_sha256"] == ledger_hash
    assert sample.model.flows[4].source_refs[0].split("@")[-1] != ledger_hash
    assert edges[3]["import_present"] and not edges[3]["source_refs"]
    svg, _ = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    assert ', source review recorded"' in svg
    assert ', observed"' not in svg


def test_generated_metadata_names_shared_module_and_configured_mechanism(sample: Sample) -> None:
    components = tuple(
        dataclasses.replace(c, implemented_by=("pkg.reader:Request",)) if c.id == "Parser" else c
        for c in sample.model.components
    )
    model = dataclasses.replace(sample.model, components=components)
    _, detail = render_schematic(
        model, sample.meaning, sample.theme, sample.facts, observed_by=("history",)
    )
    edges = json.loads(detail)["_meta"]["edges"]
    assert edges[1]["evidence"] == "structural"
    assert edges[1]["shared_module"] and not edges[1]["import_present"]
    assert edges[4]["evidence"] == "structural"
    assert edges[4]["mechanism"] == "history"
    assert not edges[4]["import_present"] and not edges[4]["shared_module"]


@pytest.fixture(params=[False, True], ids=["motion", "os-reduced-motion"])
def flow_report(
    evidence_sample: Sample, tmp_path: Path, request: pytest.FixtureRequest
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated flow evidence JavaScript needs Node")
    sample = evidence_sample
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, flowevidence};",
    )
    harness = tmp_path / "flow-evidence.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    args = [node, str(harness), str(html), "--scenario", "flowevidence"]
    if request.param:
        args.append("--reduced")
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def test_inspector_keeps_exact_review_state_warnings_and_escaped_refs(
    flow_report: dict[str, Any],
) -> None:
    for flow in flow_report["flows"]:
        expected = flow["metadata"]
        label = "source review recorded" if flow["index"] == 1 else expected["evidence"]
        assert [s["focus"] for s in flow["states"]][1:3] == [expected["to"], expected["from"]]
        for state in flow["states"]:
            assert state["edge"] == flow["index"]
            assert state["selected"] == [flow["index"]]
            assert state["artifact"] == expected["art"]
            assert state["explanation"] == expected["say"]
            assert state["evidenceState"] == expected["evidence"]
            assert state["evidence"] == label
            assert state["evidenceSays"] == expected["evidence_says"]
            assert state["claimChanged"] == expected["claim_changed"]
            assert state["unresolved"] == expected["unresolved_refs"]
            assert state["sourceRefs"] == expected["source_refs"]
            assert state["injected"] == 0
            assert state["choiceSelected"] == state["pathSelected"] == "true"
            assert state["choiceEvidence"] == expected["evidence"]
            assert state["choiceLabel"] == label
            assert label in state["pathLabel"]
            if expected["source_refs"]:
                assert expected["review_digest"] in state["sourceDetails"]
                assert "source digest" in state["sourceDetails"]
    reviewed = flow_report["flows"][0]["states"][0]
    structural = flow_report["flows"][1]["states"][0]
    assert "There is no record of program execution." in reviewed["reason"]
    assert "Source review of direction and artifact is necessary." in structural["reason"]
    assert UNSAFE_REF in flow_report["flows"][3]["states"][0]["sourceRefs"]
    changed = flow_report["flows"][2]["states"][0]
    unresolved = flow_report["flows"][3]["states"][0]
    assert len(changed["warnings"]) == 1
    assert (
        "recorded review digest is missing or different from the flow claim digest"
        in changed["warnings"][0]
    )
    assert len(unresolved["warnings"]) == 1
    assert "references do not identify source at this revision" in unresolved["warnings"][0]
    assert not reviewed["warnings"] and not structural["warnings"]
    assert "source review recorded" in flow_report["readingLabels"][1]
    assert all("observed" not in label for label in flow_report["readingLabels"])


def test_review_states_keep_dash_patterns_and_motion_limit(flow_report: dict[str, Any]) -> None:
    assert flow_report["originalDashes"][1:] == [None, "7 5", "3 4", "7 5"]
    path_dashes = {1: None, 2: "7 5", 3: "3 4", 4: "7 5"}
    for flow in flow_report["flows"]:
        for state in flow["states"]:
            assert state["dashes"] == flow_report["originalDashes"]
            assert state["pathDash"] == path_dashes[flow["index"]]
            assert state["moving"] == (0 if flow_report["reduced"] else 1)
    assert flow_report["userReduced"] == 0
    assert flow_report["restoredMotion"] == (0 if flow_report["reduced"] else 1)
