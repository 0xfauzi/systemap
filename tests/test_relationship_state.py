"""Exact flows survive endpoint navigation in the generated page.

Acceptance: zero substituted flow identifiers, evidence states or authored
explanations when opposite flows share a pair of parts. A selected flow has at
most one moving cue; its original dash never changes. Reduced motion has zero
moving cues. Reading view matches every derived reading's stored edge indices,
restores the actual endpoint button and keeps the journey while opening sections.
This local DOM harness checks interaction semantics, not browser layout.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample

from systemap import page, theme
from systemap.model import Flow, all_layers

SCENARIO = r"""
function relationships(page) {
  const {doc, win, svg, A, key} = page, X = svg.workspace;
  const report = {flows:[],readings:[],headers:[]};
  const originalDashes = () => svg.querySelectorAll('.flow').map(p =>
    p.getAttribute('stroke-dasharray'));
  const moving = () => svg.querySelectorAll('.moving').length;
  const relationship = () => {
    const panel = doc.getElementById('panel');
    return {focus:A.state.focus,edge:A.state.edge,moving:moving(),
      artifact:panel.querySelector('.systemap-f__artifact').textContent,
      explanation:panel.querySelector('[data-say]').textContent,
      evidence:panel.querySelector('.systemap-f__state').textContent,
      reason:panel.querySelector('[data-evidence]').textContent,
      from:panel.querySelector('[data-endpoint]').dataset.endpoint,
      dashes:originalDashes(),
      selected:svg.querySelectorAll('.flowlbl[aria-pressed="true"]').map(l=>+l.dataset.edge)};
  };
  report.originalDashes = originalDashes();
  [2,5,1,0].forEach(i => {
    const e=A.edges[i],label=svg.querySelector('.flowlbl[data-edge="'+i+'"]');
    label.focus();
    const activated=key('Enter',label),states=[relationship()];
    [e.to,e.from].forEach(id=>{
      doc.getElementById('panel').querySelector('[data-endpoint="'+id+'"]').click();
      runFrames(win);states.push(relationship());
    });
    report.flows.push({expected:e,index:i,activated:activated,states:states});
  });
  const motion=doc.getElementById('reduce-motion');
  motion.checked=true;motion.dispatchEvent(new EventImpl('change',{bubbles:true}));
  report.userReduced=moving();
  motion.checked=false;motion.dispatchEvent(new EventImpl('change',{bubbles:true}));
  report.preferenceRestored=moving();
  report.reduced=page.reduced;

  A.clear();doc.getElementById('view-reading').click();
  ['structure','agents','all'].forEach(layer=>{
    doc.querySelector('[data-layer-btn="'+layer+'"]').click();
    const root=doc.getElementById('atlas');
    report.readings.push({layer:layer,
      expected:layer==='all'?A.edges.map((e,i)=>i):A.detail._meta.readings[layer].edges,
      rendered:root.querySelectorAll('.reading-flow').map(article=>
        +article.querySelector('[data-flow]').dataset.flow)});
  });
  const root=doc.getElementById('atlas');
  const button=root.querySelector('[data-flow="5"][data-endpoint="Parser"]');
  button.focus();button.click();runFrames(win);
  report.readingSelection=relationship();
  report.readingFocus={flow:doc.activeElement.dataset.flow,
    endpoint:doc.activeElement.dataset.endpoint,connected:root.contains(doc.activeElement)};

  X.trace(0);X.traceStep(2);runFrames(win);
  const state=()=>({journey:X.state().j,step:X.state().s,roles:A.state.journey});
  report.journeyBefore=state();
  ['components','invariants','review'].forEach(id=>{
    const anchor=doc.querySelector('.header-links a[href="#'+id+'"]');
    anchor.click();runFrames(win);
    const section=doc.getElementById(id);
    let exposed=true;
    for(let parent=section;parent&&parent!==doc;parent=parent.parentNode){
      if(parent.hidden){exposed=false;}
    }
    report.headers.push({id:id,exposed:exposed,
      open:section.tag==='details'?section.hasAttribute('open'):true,state:state(),
      reviewExposed:!doc.getElementById('reviewindex').hidden});
  });
  return report;
}
"""


@pytest.fixture(params=[False, True], ids=["motion", "os-reduced-motion"])
def relationship_report(
    sample: Sample, tmp_path: Path, request: pytest.FixtureRequest
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated relationship JavaScript needs Node")
    model = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, kind="agent") if c.id == "Writer" else c
            for c in sample.model.components
        ),
        flows=sample.model.flows + (Flow("Writer", "Parser", "acknowledgement", "control"),),
    )
    meaning = dataclasses.replace(
        sample.meaning,
        relations={
            **sample.meaning.relations,
            ("Writer", "Parser"): "The queue returns an acknowledgement to the parser.",
        },
    )
    cfg = dataclasses.replace(sample.cfg, observed_by=("queue",))
    html = tmp_path / "map.html"
    html.write_text(
        page.build(
            cfg, model, meaning, theme.resolve({}, all_layers(model, meaning)), sample.facts, {}
        ),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, relationships};",
    )
    harness = tmp_path / "relationships.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    args = [node, str(harness), str(html), "--scenario", "relationships"]
    if request.param:
        args.append("--reduced")
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def test_opposite_flows_keep_exact_evidence_and_explanation(
    relationship_report: dict[str, Any],
) -> None:
    for flow in relationship_report["flows"]:
        expected = flow["expected"]
        assert flow["activated"]
        assert [s["focus"] for s in flow["states"]][1:] == [expected["to"], expected["from"]]
        for state in flow["states"]:
            assert state["edge"] == flow["index"]
            assert state["artifact"] == expected["art"]
            assert state["explanation"] == expected["say"]
            assert state["evidence"] == expected["evidence"]
            assert state["reason"] == expected["evidence_says"]
            assert state["from"] == expected["from"]
            assert state["selected"] == [flow["index"]]
    forward, reverse = relationship_report["flows"][:2]
    assert forward["expected"]["evidence"] == "declared"
    assert reverse["expected"]["evidence"] == "structural"


def test_animation_preserves_dash_and_respects_both_motion_controls(
    relationship_report: dict[str, Any],
) -> None:
    report = relationship_report
    for flow in report["flows"]:
        for state in flow["states"]:
            assert state["dashes"] == report["originalDashes"]
            assert state["moving"] == (0 if report["reduced"] else 1)
    assert report["userReduced"] == 0
    assert report["preferenceRestored"] == (0 if report["reduced"] else 1)


def test_reading_view_matches_derived_layers_and_restores_endpoint_focus(
    relationship_report: dict[str, Any],
) -> None:
    report = relationship_report
    for reading in report["readings"]:
        assert reading["rendered"] == reading["expected"]
    assert report["readings"][0]["rendered"] == []
    assert report["readings"][1]["rendered"]
    assert report["readingFocus"] == {"flow": "5", "endpoint": "Parser", "connected": True}
    assert report["readingSelection"]["focus"] == "Parser"
    assert report["readingSelection"]["edge"] == 5


def test_header_links_expose_sections_without_losing_journey(
    relationship_report: dict[str, Any],
) -> None:
    report = relationship_report
    for header in report["headers"]:
        assert header["exposed"] and header["open"]
        assert header["state"] == report["journeyBefore"]
    assert report["headers"][-1]["reviewExposed"]
