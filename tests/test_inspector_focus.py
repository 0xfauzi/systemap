"""Keyboard inspection retains the exact relationship and its active control.

Acceptance: zero lost focused controls across endpoint following, flow choice
and wheel activation. Each activation retains the exact flow index it names.
The generated page runs against recorded local data, without external services.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample

from systemap import page

SCENARIO = r"""
function inspectorfocus(page) {
  const {doc, win, A, key} = page;
  const panel = doc.getElementById('panel');
  const results = [];
  A.inspectFlow(0, A.edges[0].from); runFrames(win);
  function activate(control, attribute, value, edge, kind) {
    control.focus(); key('Enter', control); runFrames(win);
    const active = doc.activeElement;
    results.push({kind, edge, selected:A.state.edge, focusInPanel:panel.contains(active),
      attribute:active.getAttribute(attribute), expected:String(value),
      oldRemoved:!panel.contains(control), wheel:active.classList.contains('systemap-w__spoke')});
  }
  const endpoint = A.edges[0].to;
  activate(panel.querySelector('[data-endpoint="'+endpoint+'"]'),
    'data-endpoint', endpoint, 0, 'endpoint');
  const choice = panel.querySelector('[data-inspect-edge]');
  activate(choice, 'data-inspect-edge', choice.dataset.inspectEdge,
    +choice.dataset.inspectEdge, 'flow choice');
  const wheel = panel.querySelector('.systemap-w__spoke');
  activate(wheel, 'data-edge', wheel.dataset.edge, +wheel.dataset.edge, 'wheel');
  return results;
}
"""


def test_keyboard_inspection_restores_the_exact_control(sample: Sample, tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated navigation JavaScript needs Node")
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, inspectorfocus};",
    )
    harness = tmp_path / "focus.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "inspectorfocus"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    records: list[dict[str, Any]] = json.loads(result.stdout)
    for record in records:
        assert record["oldRemoved"], record
        assert record["focusInPanel"], record
        assert record["attribute"] == record["expected"], record
        assert record["selected"] == record["edge"], record
        assert record["wheel"] == (record["kind"] == "wheel"), record
