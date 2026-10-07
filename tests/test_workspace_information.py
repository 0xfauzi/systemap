"""Examine information from a second repository model.

Acceptance: exact source counts, flow identity, and sequence roles.
Maps without regions must include every component in a summary group.
The DOM harness examines data and controls. It does not measure browser geometry.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page

SCENARIO = r"""
function information(page){
  const {doc,win,svg,A}=page,X=svg.workspace;
  const context=()=>({title:doc.querySelector('#map-context h3').textContent,
    counts:doc.querySelectorAll('#map-context dl>div').map(n=>
      [n.querySelector('dt').textContent,+n.querySelector('dd').textContent]),
    text:doc.getElementById('map-context').textContent});
  const report={initial:context(),groups:svg.querySelectorAll('.region-summary').map(n=>
    ({name:n.getAttribute('aria-label'),text:n.textContent}))};
  A.select('Reader');runFrames(win);report.component=context();
  A.inspectFlow(0);runFrames(win);report.flow=context();
  X.trace(0);X.traceStep(2);runFrames(win);report.sequence=context();
  X.inspect('Ledger');runFrames(win);report.inspection=context();
  X.returnToJourney();runFrames(win);report.returned=context();
  doc.getElementById('view-isometric').click();runFrames(win);report.isometric=context();
  report.legend={hidden:doc.getElementById('map-roles').hidden,
    text:doc.getElementById('map-roles').textContent};
  report.heightRatio=['Parser','Ledger'].map(id=>-parseFloat(svg.querySelector(
    '.node[data-id="'+id+'"] .node__plate').style.transform.split('(')[1]));
  X.endJourney();runFrames(win);report.restored=context();
  return report;
}
"""


@pytest.mark.parametrize("regions", [True, False], ids=["regions", "no-regions"])
def test_map_information_uses_source_records(sample: Sample, tmp_path: Path, regions: bool) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("The JavaScript test requires Node.")
    model = sample.model
    if not regions:
        model = dataclasses.replace(
            model,
            regions=(),
            components=tuple(
                dataclasses.replace(c, region="", container=c.container or "system")
                for c in model.components
            ),
        )
    assert model.layout_problems() == []
    html = tmp_path / "map.html"
    html.write_text(page.build(sample.cfg, model, sample.meaning, sample.theme, sample.facts, {}))
    driver = Path(__file__).with_name("page_driver.js").read_text()
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, information};",
    )
    harness = tmp_path / "information.js"
    harness.write_text(driver + SCENARIO)
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "information", "--viewport", "390x844"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert dict(report["initial"]["counts"]) == {
        "Source modules": 4,
        "Entry points": 0,
        "Flows": 0,
        "Sequences": 1,
    }
    assert dict(report["component"]["counts"])["Source modules"] == 1
    assert dict(report["component"]["counts"])["Flows"] == 2
    assert sample.model.components[1].does in report["component"]["text"]
    assert report["flow"]["title"] == "User to Reader: input"
    assert "1 external" in report["flow"]["text"]
    assert (
        "Acting components: Parser. Measurement components: Ledger." in report["sequence"]["text"]
    )
    assert report["isometric"] == report["sequence"]
    assert report["inspection"]["title"] == "Ledger"
    assert dict(report["inspection"]["counts"])["Flows"] == 2
    assert report["returned"] == report["sequence"]
    assert report["legend"] == {
        "hidden": False,
        "text": "Acting components: ParserMeasurement components: Ledger",
    }
    assert report["heightRatio"][0] / report["heightRatio"][1] == pytest.approx(1.8)
    assert report["restored"] == report["flow"]
    groups = {g["name"]: g["text"] for g in report["groups"]}
    if regions:
        assert "4 flows / 2 modules" in groups["WORK, 2 components"]
        assert "3 flows / 2 modules" in groups["KEEP, 2 components"]
    else:
        assert "5 flows / 4 modules" in groups["Other components, 4 components"]
    assert "1 flows / 0 modules" in groups["External components, 1 components"]
