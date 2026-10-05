"""Hover leaves the inspector geometry unchanged.

Acceptance: zero changes to relationship contents or connection controls during
hover entry and exit. A click still selects the exact flow and its evidence.
The DOM harness checks event behavior, not physical browser pointer motion.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page

SCENARIO = r"""
function hoverstability(page) {
  const {doc, A, svg} = page, panel=doc.getElementById('panel');
  const id=Object.keys(A.detail).find(id=>id!=='_meta' && A.detail[id].edges.length>1);
  A.select(id);
  const section=panel.querySelector('[data-relationship]');
  const connections=panel.querySelector('.systemap-f__connections');
  const spoke=connections.querySelector('.systemap-w__spoke');
  const before=section.innerHTML, controls=connections.innerHTML;
  const edge=+spoke.dataset.edge;
  const states=[];
  for(let i=0;i<3;i++){
    spoke.dispatchEvent(new EventImpl('mouseenter'));
    states.push({html:section.innerHTML,controls:connections.innerHTML,
      peek:A.state.peek,selected:A.state.edge,sameSection:section===panel.querySelector('[data-relationship]'),
      sameControls:spoke===panel.querySelector('.systemap-w__spoke')});
    spoke.dispatchEvent(new EventImpl('mouseleave'));
    states.push({html:section.innerHTML,peek:A.state.peek,selected:A.state.edge});
  }
  spoke.click();
  const chosen=panel.querySelector('[data-relationship]').innerHTML;
  const other=panel.querySelectorAll('.systemap-w__spoke').find(s=>+s.dataset.edge!==edge);
  other.dispatchEvent(new EventImpl('mouseenter'));
  const selectedAfterHover=panel.querySelector('[data-relationship]').innerHTML;
  return {before,controls,states,edge,chosen,selected:A.state.edge,selectedAfterHover,
    artifact:A.edges[edge].art,selectedText:panel.querySelector('[data-relationship]').textContent};
}
"""


def test_hover_preserves_inspector_contents_and_click_selects_flow(
    sample: Sample, tmp_path: Path
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated inspector JavaScript needs Node")
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, hoverstability};",
    )
    harness = tmp_path / "hover.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "hoverstability"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    for state in report["states"]:
        assert state["html"] == report["before"]
        assert state["selected"] == -1
        if state["peek"] >= 0:
            assert state["peek"] == report["edge"]
            assert state["sameSection"] and state["sameControls"]
    assert report["selected"] == report["edge"]
    assert report["artifact"] in report["selectedText"]
    assert report["selectedAfterHover"] == report["chosen"]
