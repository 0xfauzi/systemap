"""The Map view uses the design of the Sequences view.

Acceptance: the Map view has the layer row with the segmented control, the
title block with a label and the question, and the zoom controls with icons.
The DOM harness examines data and controls. It does not measure browser geometry.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page

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
    zoom = re.search(r'<div class="zoom" role="group" aria-label="Zoom">(.*?data-zoom="fit".*?</button>)', html)
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
