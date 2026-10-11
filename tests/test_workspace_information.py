"""Examine information from a second repository model.

Acceptance: exact source modules, flow counts, flow identity, and sequence roles.
Maps with and without regions give the same information.
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
  const {doc,win,svg,A}=page,X=svg.workspace,panel=doc.getElementById('panel');
  const context=()=>({readout:doc.getElementById('map-context').textContent,
    modules:panel.querySelectorAll('.systemap-f__chip').map(n=>n.textContent),
    flows:panel.querySelectorAll('[data-inspect-edge]').length,
    text:panel.textContent,
    sequence:(doc.getElementById('seqbody')||{textContent:''}).textContent});
  const report={initial:context()};
  doc.querySelector('[data-layer-btn="structure"]').click();runFrames(win);
  report.structure=context();
  doc.querySelector('[data-layer-btn="system"]').click();runFrames(win);
  A.select('Reader');runFrames(win);report.component=context();
  A.inspectFlow(0);runFrames(win);report.flow=context();
  X.trace(0);X.traceStep(2);runFrames(win);report.sequence=context();
  X.inspect('Ledger');runFrames(win);report.inspection=context();
  X.returnToJourney();runFrames(win);report.returned=context();
  // From a step, the first end goes to the whole route and the second ends.
  X.endJourney();runFrames(win);X.endJourney();runFrames(win);report.restored=context();
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
    html.write_text(
        page.build(sample.cfg, model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, information};",
    )
    harness = tmp_path / "information.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "information", "--viewport", "390x844"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    # The readout counts what the map draws: the System context layer shows
    # the one flow from the actor, and Structure counts the components.
    assert report["initial"]["readout"] == "1 flow · 1 actor"
    structure = "4 components" + (" · 2 regions" if regions else "")
    assert report["structure"]["readout"] == structure
    assert "The source facts contain no entry points." in report["initial"]["sequence"]
    # A component: its source modules and its flows, from the source records.
    assert report["component"]["modules"] == ["pkg.reader"]
    assert report["component"]["flows"] == 2
    assert sample.model.components[1].does in report["component"]["text"]
    assert report["component"]["readout"].startswith("Reader · ")
    # A flow: its artifact, its ends and its evidence state.
    assert report["flow"]["readout"] == "input · User → Reader · external"
    assert "Selected flow" in report["flow"]["text"]
    # A sequence step: the acting and the measuring components.
    assert report["sequence"]["readout"] == "3 · Parser → Writer · parts"
    assert "ACTSParserMEASURESLedger" in report["sequence"]["sequence"]
    assert report["inspection"]["readout"].startswith("Ledger · ")
    assert report["inspection"]["flows"] == 2
    assert report["returned"] == report["sequence"]
    assert report["restored"] == report["flow"]
