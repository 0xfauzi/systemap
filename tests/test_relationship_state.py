"""Exact flows survive endpoint navigation in the generated page.

Acceptance: zero substituted flow identifiers, evidence states or authored
explanations when opposite flows share a pair of parts. A selected flow has at
most one moving cue; its original dash never changes. Reduced motion has zero
moving cues. The page keeps the journey while it opens sections.
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
  const report = {flows:[]};
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
  // Reduce motion is a toggle button in the header.
  const motion=doc.getElementById('reduce-motion');
  const pressed=()=>motion.getAttribute('aria-pressed')==='true';
  const set=(on)=>{if(pressed()!==on){motion.click();}};
  const initial=pressed();
  set(true);
  report.userReduced=moving();
  set(initial);
  report.preferenceRestored=moving();
  report.reduced=page.reduced;

  A.clear();

  X.trace(0);X.traceStep(2);runFrames(win);
  const state=()=>({journey:X.state().j,step:X.state().s,roles:A.state.journey});
  report.journeyBefore=state();
  // The Map view gives all rules in its panel. Sequences opens the
  // sequence again at the same step.
  doc.querySelector('.views button[data-mode="understand"]').click();runFrames(win);
  const rules=doc.getElementById('invariants');
  rules.setAttribute('open','');
  let exposed=true;
  for(let parent=rules;parent&&parent!==doc;parent=parent.parentNode){
    if(parent.hidden){exposed=false;}
  }
  report.rules={exposed:exposed,state:state(),
    items:rules.querySelectorAll('li').length,panel:doc.body.dataset.panel};
  doc.querySelector('.views button[data-mode="trace"]').click();runFrames(win);
  report.journeyAgain=state();
  return report;
}
"""


@pytest.fixture(
    params=["", "--system-reduced", "--reduced"],
    ids=["motion", "system-reduced-motion", "page-reduced-motion"],
)
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
        args.append(request.param)
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30)
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
            assert state["moving"] <= (0 if report["reduced"] else 1)
    assert report["userReduced"] == 0
    assert report["preferenceRestored"] <= (0 if report["reduced"] else 1)


def test_the_map_panel_gives_all_rules_and_sequences_returns_to_the_step(
    relationship_report: dict[str, Any],
) -> None:
    report = relationship_report
    rules = report["rules"]
    assert rules["exposed"] and rules["items"] and rules["panel"] == "open"
    assert rules["state"]["journey"] == -1, "the Map view ends the sequence"
    assert report["journeyAgain"] == report["journeyBefore"]
