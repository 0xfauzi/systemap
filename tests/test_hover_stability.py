"""The Node harness runs flow selection and preview events.

Acceptance: Structure shows zero flows after component selection. Component
selection shows only connected flows in the selected layer, with zero selected paths.
Only labels for selection or preview appear. A preview makes zero changes to inspector
contents or camera state. Every connected flow has a button and evidence state.
The harness does not measure browser pointer movement or text geometry.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample
from test_keyboard import DRIVER, needs_node, sample_page

SCENARIO = r"""
function hoverstability(page) {
  const {doc,A,svg,key}=page, panel=doc.getElementById('panel');
  const visible=selector=>svg.querySelectorAll(selector).filter(el=>!el.classList.contains('off'));
  const snapshot=()=>({paths:visible('.flow').map(el=>+el.dataset.edge),
    labels:visible('.flowlbl').map(el=>+el.dataset.edge),
    hot:svg.querySelectorAll('.flow.hot').map(el=>+el.dataset.edge),
    peek:A.state.peek,selected:A.state.edge,layer:A.state.layer,
    pathsAccessible:svg.querySelectorAll('.flow').every(el=>
      el.getAttribute('role')==='button' && el.getAttribute('tabindex')===
      (el.classList.contains('off')?'-1':'0'))});
  const initial=snapshot();
  const ids=Object.keys(A.detail).filter(id=>id!=='_meta' && A.detail[id].edges.length);
  const cases=[];
  A.layers.map(layer=>layer.id).concat(['all']).forEach(layer=>{
    ids.forEach(id=>{
      A.clear(); A.setLayer(layer); A.select(id); runFrames(page.win);
      const groups=panel.querySelectorAll('.systemap-f__flow-group').map(group=>({
        heading:group.querySelector('h4').textContent,
        edges:group.querySelectorAll('[data-inspect-edge]').map(button=>({
          edge:+button.dataset.inspectEdge,evidence:button.dataset.evidenceState,
          text:button.textContent}))}));
      cases.push({id,layer,groups,...snapshot()});
    });
  });
  A.clear(); A.setLayer('all');
  const id=ids.find(id=>A.detail[id].edges.length>1);
  A.select(id); runFrames(page.win);
  const section=panel.querySelector('[data-relationship]');
  const list=panel.querySelector('.systemap-f__flow-list');
  const button=list.querySelector('[data-inspect-edge]');
  const switches=[];
  A.layers.forEach(layer=>{
    doc.querySelector('[data-layer-btn="'+layer.id+'"]').click();
    runFrames(page.win);
    switches.push({frame:A.view.frame(),...snapshot()});
  });
  doc.querySelector('[data-layer-btn="all"]').click(); runFrames(page.win);
  const edge=+button.dataset.inspectEdge;
  const path=svg.querySelector('.flow[data-edge="'+edge+'"]');
  const before={html:section.innerHTML,text:list.textContent,view:A.view.snapshot()};
  const interactions=[];
  const record=event=>interactions.push({event,...snapshot(),
    html:section.innerHTML,text:list.textContent,view:A.view.snapshot(),
    sameSection:section===panel.querySelector('[data-relationship]'),
    sameList:list===panel.querySelector('.systemap-f__flow-list'),
    sameButton:button===list.querySelector('[data-inspect-edge]')});
  [button,path].forEach(target=>{
    target.dispatchEvent(new EventImpl('mouseenter')); record('enter');
    target.dispatchEvent(new EventImpl('mouseleave')); record('leave');
    target.focus(); record('focus');
    target.blur(); record('blur');
  });
  const label=svg.querySelector('.flowlbl[data-edge="'+edge+'"]');
  path.dispatchEvent(new EventImpl('mouseenter'));
  path.dispatchEvent(new EventImpl('mouseleave',{relatedTarget:label})); record('relatedLeave');
  label.dispatchEvent(new EventImpl('mouseleave')); record('leave');
  path.focus();
  const prevented=key('Enter',path);
  const keyboard={prevented,...snapshot(),artifact:A.edges[edge].art,
    html:panel.querySelector('[data-relationship]').textContent};
  path.blur();
  const selected=snapshot();
  const chosen=panel.querySelector('[data-relationship]');
  const chosenHtml=chosen.innerHTML;
  const other=panel.querySelectorAll('[data-inspect-edge]').find(el=>+el.dataset.inspectEdge!==edge);
  other.dispatchEvent(new EventImpl('mouseenter'));
  const selectedPreview={...snapshot(),same:chosen===panel.querySelector('[data-relationship]'),
    html:panel.querySelector('[data-relationship]').innerHTML};
  other.dispatchEvent(new EventImpl('mouseleave'));
  const afterPreview=snapshot();
  other.click();
  const listSelection={...snapshot(),edge:+other.dataset.inspectEdge};
  const sequences=[];
  A.journeys.forEach(journey=>journey.steps.forEach(step=>{
    A.setJourney(step); sequences.push({edge:step.edge,...snapshot()});
  }));
  A.setJourney({acts:[id],measures:[],edge:-1});
  const noFlow=snapshot();
  return {initial,noFlow,cases,edges:A.edges,layers:A.layers,readings:A.detail._meta.readings,incident:Object.fromEntries(ids.map(id=>[id,A.detail[id].edges])),
    id,switches,edge,before,interactions,keyboard,selected,chosenHtml,selectedPreview,afterPreview,listSelection,sequences};
}
"""


@pytest.fixture
def crowding_report(sample: Sample, tmp_path: Path) -> dict[str, Any]:
    html = sample_page(sample, tmp_path)
    driver = DRIVER.read_text(encoding="utf-8").replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, hoverstability};",
    )
    harness = tmp_path / "hover.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(html), "--scenario", "hoverstability"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    return report


@needs_node
def test_component_selection_uses_only_incident_active_layer_flows(
    crowding_report: dict[str, Any],
) -> None:
    report = crowding_report
    assert report["initial"]["labels"] == []
    for case in report["cases"]:
        incident = report["incident"][case["id"]]
        expected = {
            edge
            for edge in incident
            if case["layer"] == "all" or edge in report["readings"][case["layer"]]["edges"]
        }
        assert set(case["paths"]) == expected, case
        assert case["hot"] == [] and case["labels"] == [], case
        assert case["pathsAccessible"], case
    assert any(case["layer"] == "structure" for case in report["cases"])
    assert any(len(case["paths"]) > 1 for case in report["cases"])
    for switch in report["switches"]:
        expected = set(report["incident"][report["id"]]) & set(
            report["readings"][switch["layer"]]["edges"]
        )
        assert set(switch["paths"]) == expected
        assert switch["hot"] == [] and switch["labels"] == []
        assert switch["frame"] is not None


@needs_node
def test_inspector_groups_all_incident_flows_with_evidence(
    crowding_report: dict[str, Any],
) -> None:
    report = crowding_report
    names = {layer["id"]: layer["label"] for layer in report["layers"]}
    for case in report["cases"]:
        choices = [choice for group in case["groups"] for choice in group["edges"]]
        assert sorted(choice["edge"] for choice in choices) == sorted(
            report["incident"][case["id"]]
        )
        for group in case["groups"]:
            check_flow_group(report, group, names)


def check_flow_group(report: dict[str, Any], group: dict[str, Any], names: dict[str, str]) -> None:
    assert group["edges"]
    for choice in group["edges"]:
        flow = report["edges"][choice["edge"]]
        assert group["heading"] == names[flow["layer"]]
        assert choice["evidence"] == flow["evidence"]
        assert flow["art"] in choice["text"]
        assert flow["from"] in choice["text"] and flow["to"] in choice["text"]
        evidence = "source review recorded" if flow["evidence"] == "observed" else flow["evidence"]
        assert evidence in choice["text"]


@needs_node
def test_path_and_list_preview_preserve_inspector_and_camera(
    crowding_report: dict[str, Any],
) -> None:
    report = crowding_report
    for state in report["interactions"]:
        expected = [report["edge"]] if state["event"] in ("enter", "focus", "relatedLeave") else []
        assert state["labels"] == expected
        assert state["peek"] == (report["edge"] if expected else -1)
        assert state["selected"] == -1
        assert state["hot"] == []
        assert state["sameSection"] and state["sameList"] and state["sameButton"]
        assert state["html"] == report["before"]["html"]
        assert state["text"] == report["before"]["text"]
        assert state["view"] == report["before"]["view"]


@needs_node
def test_path_keyboard_and_sequence_select_one_exact_flow(
    crowding_report: dict[str, Any],
) -> None:
    report = crowding_report
    keyboard = report["keyboard"]
    assert keyboard["prevented"]
    assert keyboard["artifact"] in keyboard["html"]
    assert keyboard["layer"] == report["edges"][report["edge"]]["layer"]
    for state in (keyboard, report["selected"], report["afterPreview"]):
        assert state["selected"] == report["edge"]
        assert state["paths"] == state["labels"] == state["hot"] == [report["edge"]]
    preview = report["selectedPreview"]
    assert preview["selected"] == report["edge"]
    assert preview["same"] and preview["html"] == report["chosenHtml"]
    assert set(preview["labels"]) == {report["edge"], preview["peek"]}
    selected = report["listSelection"]
    assert selected["selected"] == selected["edge"]
    assert selected["layer"] == report["edges"][selected["edge"]]["layer"]
    assert selected["paths"] == selected["labels"] == [selected["edge"]]
    assert report["noFlow"]["paths"] == report["noFlow"]["labels"] == []
    assert report["noFlow"]["hot"] == []
    assert report["sequences"]
    for step in report["sequences"]:
        assert step["paths"] == step["labels"] == step["hot"] == [step["edge"]]
        assert step["pathsAccessible"]


SEQUENCE_SCENARIO = r"""
function sequencefocus(page) {
  const {doc,A,svg,win}=page;
  const shown=element=>{
    for(let node=element;node;node=node.parentNode){ if(node.hidden){ return false; } }
    return true;
  };
  const snapshot=()=>({focus:A.state.focus,edge:A.state.edge,layer:A.state.layer,
    view:A.view.snapshot(),drawerHidden:doc.getElementById('drawer').hidden,
    returnHidden:doc.getElementById('jreturn').hidden,
    stripShown:shown(doc.getElementById('strip')),
    sourceShown:shown(doc.getElementById('source-detail')),
    sourceText:doc.getElementById('source-detail').textContent,
    sentence:doc.getElementById('stripsay').textContent,
    visiblePaths:svg.querySelectorAll('.flow').filter(path=>!path.classList.contains('off'))
      .map(path=>+path.dataset.edge)});
  const journey=A.journeys[0], first=journey.steps[0];
  const edge=A.edges.findIndex(flow=>flow.layer!==A.edges[first.edge].layer);
  A.inspectFlow(edge,A.edges[edge].to);runFrames(win);
  const before=snapshot();
  const select=doc.getElementById('journey');
  select.value='0';select.dispatchEvent(new EventImpl('change',{bubbles:true}));runFrames(win);
  const started=snapshot();
  doc.getElementById('jend').click();runFrames(win);
  return {edge,step:first,stepLayer:A.edges[first.edge].layer,before,started,ended:snapshot()};
}
"""


@needs_node
def test_sequence_start_clears_previous_flow_inspector_and_end_restores_it(
    sample: Sample,
    tmp_path: Path,
) -> None:
    """Acceptance: sequence start shows zero previous component controls or source content.

    End restores the exact previous flow, layer, component, and camera state.
    """
    html = sample_page(sample, tmp_path)
    driver = DRIVER.read_text(encoding="utf-8").replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, sequencefocus};",
    )
    harness = tmp_path / "sequence-focus.js"
    harness.write_text(driver + SEQUENCE_SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(html), "--scenario", "sequencefocus"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    before, started, ended = report["before"], report["started"], report["ended"]
    assert report["edge"] >= 0 and before["edge"] == report["edge"]
    assert before["layer"] != report["stepLayer"]
    assert not before["drawerHidden"] and before["sourceShown"] and before["sourceText"]
    assert started["focus"] == "" and started["edge"] == -1
    assert started["drawerHidden"] and started["returnHidden"]
    assert started["stripShown"] and not started["sourceShown"]
    assert started["sentence"] == report["step"]["say"]
    assert started["layer"] == report["stepLayer"]
    assert started["visiblePaths"] == [report["step"]["edge"]]
    for field in ("focus", "edge", "layer", "view", "visiblePaths", "sourceText"):
        assert ended[field] == before[field], field
    assert not ended["drawerHidden"] and ended["sourceShown"]
    assert ended["returnHidden"] and not ended["stripShown"]
