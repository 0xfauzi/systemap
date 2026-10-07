"""Examine the page projection and its text transform.

Acceptance: keep every component, flow, evidence state, and accessible name.
Both transformed text axes must agree with the original axes within 1e-12.
The source geometry must stay identical for source checks and routing.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from conftest import Sample

from systemap.schematic import render
from systemap.schematic_style import ISO_X, project_svg


def test_projection_preserves_map_data_and_upright_text(sample: Sample) -> None:
    source, detail = render(sample.model, sample.meaning, sample.theme, sample.facts)
    drawing = ET.fromstring(project_svg(source))
    original = ET.fromstring(source)
    assert float(drawing.attrib["data-projection"]) == pytest.approx(ISO_X)
    for selector in (".//{*}g[@data-id]", ".//{*}path[@data-edge]"):
        before, after = original.findall(selector), drawing.findall(selector)
        assert [element.attrib for element in before] == [element.attrib for element in after]
    for node in drawing.findall(".//{*}g[@data-id]"):
        base = node.find("{*}rect[@class='node__base']")
        box = node.find("{*}g[@class='node__plate']/{*}rect[@class='node__box']")
        assert base is not None and box is not None
        assert float(base.attrib["x"]) - float(box.attrib["x"]) == 6
        assert float(base.attrib["y"]) - float(box.attrib["y"]) == 6
        original_box = original.find(f".//{{*}}g[@data-id='{node.attrib['data-id']}']/{{*}}rect")
        assert original_box is not None
        for key in ("x", "y", "width", "height"):
            assert box.attrib[key] == original_box.attrib[key]
        assert node.find("{*}text[@data-caption]") is not None
        assert box.attrib.get("stroke-dasharray") == original_box.attrib.get("stroke-dasharray")
    for text in drawing.findall(".//{*}text"):
        transform = text.attrib["transform"]
        inverse = re.search(r"matrix\(([^)]+)\)", transform)
        assert inverse is not None
        a, b, c, d, e, f = map(float, inverse[1].split())
        assert (ISO_X * a - ISO_X * b, 0.5 * a + 0.5 * b) == pytest.approx((1, 0), abs=1e-12)
        assert (ISO_X * c - ISO_X * d, 0.5 * c + 0.5 * d) == pytest.approx((0, 1), abs=1e-12)
        assert (e, f) == (0, 0)
    assert render(sample.model, sample.meaning, sample.theme, sample.facts)[1] == detail


def test_projected_boundaries_keep_header_lines_separate(sample: Sample) -> None:
    source, _ = render(sample.model, sample.meaning, sample.theme, sample.facts)
    drawing = ET.fromstring(project_svg(source))
    for boundary in drawing.findall(".//{*}g[@class='boundary']"):
        texts = boundary.findall("{*}text")
        origins = []
        for text in texts:
            origin = re.search(r"translate\(([^)]+)\)", text.attrib["transform"])
            assert origin is not None
            x, y = map(float, origin[1].split())
            origins.append((ISO_X * (x - y), (x + y) / 2))
        assert all(origin[0] == pytest.approx(origins[0][0]) for origin in origins)
        assert all(b[1] - a[1] >= 12 for a, b in zip(origins, origins[1:], strict=False))


SCENARIO = r"""
function projection(page) {
  const {doc,win,svg,A}=page,X=svg.workspace,seen=[];
  const state=()=>({focus:A.state.focus,edge:A.state.edge,layer:A.state.layer,
    journey:X.state().j,step:X.state().s,roles:A.state.journey,view:A.view.snapshot()});
  svg.addEventListener('systemap:view',()=>seen.push(+svg.dataset.projection));
  A.select('Reader');A.view.zoomBy(1.2);runFrames(win);
  const before=state();X.trace(0);X.traceStep(1);runFrames(win);
  const traced=state();doc.getElementById('view-isometric').click();runFrames(win);
  const iso=state();X.inspect('Parser');runFrames(win);X.returnToJourney();runFrames(win);
  const returned=state();X.endJourney();runFrames(win);const ended=state();
  doc.getElementById('view-map').click();runFrames(win);
  const flat=state(),matrix=svg.querySelector('.projection').getAttribute('transform');
  doc.getElementById('view-isometric').click();doc.getElementById('view-map').click();
  runFrames(win);const rapid=svg.dataset.plane;
  doc.getElementById('view-isometric').click();
  [20,260].forEach(now=>{const batch=rafQueue;rafQueue=[];batch.forEach(f=>f.cb(now));});
  const motion=doc.getElementById('reduce-motion');motion.checked=true;
  motion.dispatchEvent(new EventImpl('change',{bubbles:true}));
  doc.getElementById('view-isometric').click();
  const reduced={plane:svg.dataset.plane,projection:+svg.dataset.projection};
  doc.querySelector('[data-mode="trace"]').click();
  doc.getElementById('browser-close').click();
  return {before,traced,iso,returned,ended,flat,matrix,reduced,seen,
    browse:doc.body.dataset.browse,rapid,
    nodes:svg.querySelectorAll('.node').map(n=>n.dataset.id),
    flows:svg.querySelectorAll('.flow').map(n=>+n.dataset.edge)};
}
"""


def test_projection_toggle_preserves_sequence_and_camera(sample: Sample, tmp_path) -> None:
    """Acceptance: exact state, exact endpoints, and camera error below 1e-6 units."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    from systemap import page

    node = shutil.which("node")
    if node is None:
        pytest.skip("The JavaScript test requires Node.")
    html = tmp_path / "projection.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    )
    driver = Path(__file__).with_name("page_driver.js").read_text()
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, projection};",
    )
    harness = tmp_path / "projection.js"
    harness.write_text(driver + SCENARIO)
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "projection"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    for key in ("journey", "step", "roles", "layer"):
        assert report["iso"][key] == report["traced"][key]
        assert report["returned"][key] == report["traced"][key]
    for key in ("focus", "edge", "layer"):
        assert report["ended"][key] == report["before"][key]
    assert report["iso"]["view"]["projection"] == 1
    assert report["flat"]["view"]["projection"] == 0
    assert report["matrix"] == "matrix(1 0 0 1 0 0)"
    assert any(0 < value < ISO_X for value in report["seen"])
    assert report["reduced"] == {"plane": "isometric", "projection": ISO_X}
    assert report["browse"] == "false"
    assert report["rapid"] == "flat"
    assert set(report["nodes"]) == {c.id for c in sample.model.components}
    assert report["flows"] == list(range(len(sample.model.flows)))
    assert report["flat"]["view"]["zoom"] == pytest.approx(
        report["before"]["view"]["zoom"], abs=1e-6
    )
    for key in ("k", "tx", "ty"):
        assert report["flat"]["view"][key] == pytest.approx(report["before"]["view"][key], abs=1e-6)
