"""The Map view uses the design of the Sequences view.

Acceptance: the Map view has the layer row with the segmented control, the
title block with a label and the question, and the zoom controls with icons.
On a wide window the panel opens with the page. It shows the layer in the card
style of the sequence steps, and the guide steps after it. The pointer on a
card keeps its lines and the cards at their other ends at full contrast.
The DOM harness examines data and controls. It does not measure browser geometry.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page
from systemap.model import Flow

SCENARIO = r"""
function mapview(page){
  const {doc,win,svg,A}=page,label=doc.getElementById('mapbar-label');
  const title=()=>({label:label.hidden?'':label.textContent,
    question:doc.getElementById('layer-question').textContent});
  const tabs=doc.querySelectorAll('[data-layer-btn]').map(b=>b.dataset.layerBtn);
  const report={tabs,initial:title(),layers:{}};
  tabs.forEach(id=>{doc.querySelector('[data-layer-btn="'+id+'"]').click();runFrames(win);
    report.layers[id]=title();});
  doc.querySelector('[data-mode="trace"]').click();runFrames(win);report.trace=title();
  doc.querySelector('[data-mode="understand"]').click();runFrames(win);report.back=title();
  return report;
}
"""


def run_scenario(
    sample: Sample, tmp_path: Path, name: str, scenario: str, viewport: str = "1600x900"
) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("The JavaScript test requires Node.")
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, " + name + "};",
    )
    harness = tmp_path / f"{name}.js"
    harness.write_text(driver + scenario, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", name, "--viewport", viewport],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, object] = json.loads(result.stdout)
    return report


def test_layer_row_is_the_segmented_control_of_the_sequence_toolbar(sample: Sample) -> None:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    row = re.search(r'<div class="layer-controls" id="layercontrols">(.*?)</div></div>', html)
    assert row, "the Map view has its own toolbar row"
    assert '<span class="trace-controls__label" id="layer-label">Layer</span>' in row[1]
    assert '<div class="seq-seg layers" role="tablist" aria-labelledby="layer-label">' in row[1]
    assert re.findall(r'data-layer-btn="([^"]+)"', row[1])[-1] == "all"
    # The title block is no longer inside the tab row.
    assert '<div class="mapbar" id="mapbar"><p class="mapbar__label"' in html
    assert 'id="layer-select"' not in html


def test_zoom_controls_have_icons_and_names(sample: Sample) -> None:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    zoom = re.search(
        r'<div class="zoom" role="group" aria-label="Zoom">(.*?data-zoom="fit".*?</button>)', html
    )
    assert zoom
    buttons = re.findall(r'<button type="button" data-zoom="(\w+)"([^>]*)>(.*?)</button>', zoom[1])
    assert [b[0] for b in buttons] == ["out", "actual", "in", "fit"]
    for name, attrs, inner in buttons:
        assert 'aria-label="' in attrs, name
        assert 'title="' in attrs, name
        if name != "actual":
            assert inner.startswith('<svg class="icon" viewBox="0 0 16 16" aria-hidden="true"')


def test_title_block_names_the_layer_and_its_position(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "mapview", SCENARIO)
    tabs = report["tabs"]
    assert isinstance(tabs, list) and tabs[-1] == "all"
    layers = report["layers"]
    assert isinstance(layers, dict)
    shown = page.tab_layers(sample.model, sample.meaning)
    assert [layer.id for layer in shown] == tabs[:-1]
    for k, layer in enumerate(shown):
        assert layers[layer.id] == {
            "label": f"{layer.label.upper()} · LAYER {k + 1} OF {len(shown)}",
            "question": layer.question,
        }
    assert layers["all"]["label"] == "ALL LAYERS"
    assert layers["all"]["question"] == "Which flows connect the components?"
    assert report["initial"] == layers[tabs[0]]
    # The Sequences view keeps its own label, and the Map view gets its label back.
    trace = report["trace"]
    assert isinstance(trace, dict) and "LAYER" not in trace["label"]
    assert report["back"] == layers["all"]


PANEL = r"""
function mappanel(page){
  const {doc,win,A}=page,read=doc.getElementById('inspector-empty');
  const text=(n)=>(n?n.textContent:'');
  const state=()=>({panel:doc.body.dataset.panel,
    kicker:text(read.querySelector('.lay .seq-kicker')),
    title:text(read.querySelector('.lay .seq-title')),
    count:text(read.querySelector('.lay .seq-count')),
    cards:read.querySelectorAll('.lay-card').map(b=>text(b.querySelector('.seq-step__head'))),
    order:(read.querySelector('.read')||{children:[]}).children.map(n=>n.getAttribute('class'))});
  const tabs=doc.querySelectorAll('[data-layer-btn]').map(b=>b.dataset.layerBtn);
  const report={initial:state(),layers:{},expected:{}};
  tabs.forEach(id=>{
    doc.querySelector('[data-layer-btn="'+id+'"]').click();runFrames(win);
    report.layers[id]=state();
    const r=A.detail._meta.readings[id];
    report.expected[id]=A.edges.map((e,i)=>[e,i])
      .filter(([e,i])=>id==='all'||(r&&r.edges.includes(i)))
      .map(([e])=>e.from+' → '+e.to+' · '+e.art);
  });
  report.regions=(A.detail._meta.regions||[]).map(r=>r.label+' · '+r.ids.length+' component'
    +(r.ids.length===1?'':'s'));
  report.actors=Object.keys(A.detail).filter(id=>id!=='_meta'&&A.detail[id].kind==='actor');
  // A flow card: a pointer on it previews the flow, a click selects the flow.
  const flowLayer=tabs.find(id=>{
    doc.querySelector('[data-layer-btn="'+id+'"]').click();runFrames(win);
    return !!read.querySelector('[data-read-edge]');});
  const card=read.querySelector('[data-read-edge]');
  const i=+card.dataset.readEdge;
  card.dispatchEvent(new EventImpl('mouseenter',{bubbles:false}));
  report.peek={layer:flowLayer,edge:i,peek:A.state.peek};
  card.click();runFrames(win);
  report.selected={edge:A.state.edge,drawer:!doc.getElementById('drawer').hidden};
  return report;
}
"""


def test_panel_opens_with_the_layer_as_step_cards(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "mappanel", PANEL)
    initial, layers, expected = report["initial"], report["layers"], report["expected"]
    assert isinstance(initial, dict) and isinstance(layers, dict) and isinstance(expected, dict)
    # A wide window opens the panel with the page, as the Sequences view does.
    assert initial["panel"] == "open"
    shown = page.tab_layers(sample.model, sample.meaning)
    assert initial == layers[shown[0].id]
    for layer in shown:
        got = layers[layer.id]
        assert got["kicker"] == "LAYER"
        assert got["title"] == layer.label
        # The layer section comes first, and the guide steps follow it.
        assert got["order"][0].startswith("read__section lay")
        assert got["order"][-1] == "read__guide"
        if layer.id == "structure":
            assert got["cards"] == report["regions"]
        elif layer.id == "system":
            assert sorted(got["cards"]) == sorted(report["actors"])
        else:
            assert got["cards"] == expected[layer.id]
    assert layers["all"]["title"] == "All layers"
    assert layers["all"]["cards"] == expected["all"]
    peek, selected = report["peek"], report["selected"]
    assert isinstance(peek, dict) and peek["peek"] == peek["edge"]
    assert selected == {"edge": peek["edge"], "drawer": True}


GROUPS = r"""
function mapgroups(page){
  const {doc,win}=page,read=doc.getElementById('inspector-empty');
  const text=(n)=>(n?n.textContent:'');
  doc.querySelector('[data-layer-btn="data"]').click();runFrames(win);
  const sec=read.querySelector('.fg-read');
  const report={kicker:text(sec.querySelector('.seq-kicker')),
    title:text(sec.querySelector('.seq-title')),count:text(sec.querySelector('.seq-count')),
    rows:read.querySelectorAll('[data-fg-row]').length};
  read.querySelector('[data-fg-row]').click();runFrames(win);
  const open=read.querySelector('.fg-open');
  report.open={count:text(open.querySelector('.fg-open__head b')),
    name:text(open.querySelector('.fg-open__name')),
    flows:open.querySelectorAll('[data-fg-edge]').length};
  return report;
}
"""


def test_grouped_layer_panel_uses_the_step_style(sample: Sample, tmp_path: Path) -> None:
    extra = tuple(Flow("Reader", "Writer", f"part {k}", "data") for k in range(21))
    many = Sample(
        sample.cfg,
        dataclasses.replace(sample.model, flows=sample.model.flows + extra),
        sample.meaning,
        sample.theme,
        sample.facts,
    )
    report = run_scenario(many, tmp_path, "mapgroups", GROUPS)
    assert report["kicker"] == "LAYER"
    assert report["title"] == "Data flow"
    assert report["count"] == "23 flows · 2 groups"
    assert report["rows"] == 2
    assert report["open"] == {"count": "22", "name": "1 WORK → 2 KEEP", "flows": 22}


def test_panel_stays_closed_on_a_narrow_window(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "mappanel", PANEL, viewport="700x900")
    initial = report["initial"]
    assert isinstance(initial, dict) and initial["panel"] == "closed"


HOVER = r"""
function maphover(page){
  const {doc,win,svg,A}=page;
  doc.querySelector('[data-layer-btn="all"]').click();runFrames(win);
  const node=id=>svg.querySelectorAll('.node').find(n=>n.dataset.id===id);
  const lit=()=>({peek:svg.classList.contains('card-peek'),
    cards:svg.querySelectorAll('.node.card-lit').map(n=>n.dataset.id).sort(),
    flows:svg.querySelectorAll('.flow.card-lit').map(p=>+p.dataset.edge).sort()});
  const over=id=>node(id).querySelector('.node__box').dispatchEvent(
    new EventImpl('pointerover',{bubbles:true}));
  const report={};
  over('Parser');report.hover=lit();
  svg.dispatchEvent(new EventImpl('pointerdown',{bubbles:true}));report.down=lit();
  svg.classList.add('panning');over('Parser');report.panning=lit();
  svg.classList.remove('panning');
  report.edges=A.edges.map((e,i)=>[e.from,e.to,i]);
  return report;
}
"""


def test_hover_keeps_the_lines_and_the_cards_at_their_ends(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "maphover", HOVER)
    edges = report["edges"]
    assert isinstance(edges, list)
    touching = sorted(i for a, b, i in edges if "Parser" in (a, b))
    ends = sorted({c for a, b, _i in edges if "Parser" in (a, b) for c in (a, b)})
    assert report["hover"] == {"peek": True, "cards": ends, "flows": touching}
    # A press on the map ends it, and a drag of the map does not start it.
    empty = {"peek": False, "cards": [], "flows": []}
    assert report["down"] == empty
    assert report["panning"] == empty


def test_card_and_label_states_for_pointer_and_focus(sample: Sample) -> None:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    # A card under the pointer gets a stronger border, but not a selected or end card.
    assert (
        "#schematic[data-live] .node:not(.sel):not(.acts):not(.endpoint):not(.subject):hover "
        ".node__box{stroke:var(--ink-3" in html
    )
    # The label of a preview line gets an outline.
    assert "#schematic .flowlbl.peek .flowlbl__chip{stroke:var(--line-2" in html
    # The other cards go a little dim while the pointer is on a card.
    assert "#schematic.card-peek .node:not(.card-lit):not(.quiet):not(.dim){opacity:.6}" in html


FOOT = r"""
function mapfoot(page){
  const {doc,A}=page,lg=doc.getElementById('map-legend');
  const bottom=a=>a.y+a.h;
  const before=A.view.visibleArea(null),top=bottom(before)-40;
  lg.hidden=false;
  lg.getBoundingClientRect=()=>({left:24,top:top,right:300,bottom:top+26,width:276,height:26});
  const after=A.view.visibleArea(null);
  lg.hidden=true;
  const hidden=A.view.visibleArea(null);
  return {before:bottom(before),top:top,after:bottom(after),hidden:bottom(hidden)};
}
"""


def test_framing_keeps_the_selection_above_the_legend(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "mapfoot", FOOT)
    top = report["top"]
    assert isinstance(top, (int, float))
    # The area for a framing stops 8 pixels above the legend, as a sequence step does.
    assert report["after"] == top - 8
    assert report["hidden"] == report["before"]
