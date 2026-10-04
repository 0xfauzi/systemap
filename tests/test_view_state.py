"""Navigation preserves authored context in the generated page.

Acceptance: zero lost journey steps or exact flow identifiers across part
inspection, Fit, return and End. Restored viewport coordinates must equal the
saved coordinates. Nested maps restore the actual opener and every prior inert
attribute. Finder matches all three supported fields and ignores typing targets.
The recorded sample and generated JavaScript run locally without services.
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

from systemap import page

SCENARIO = r"""
function viewstate(page) {
  const {doc, win, svg, A, key} = page;
  const X = svg.workspace;
  const report = {};
  const snapshot = () => ({focus:A.state.focus,edge:A.state.edge,layer:A.state.layer,
    view:A.view.snapshot(),journey:X.state().j,step:X.state().s,roles:A.state.journey});
  A.inspectFlow(1, A.edges[1].from);
  A.view.zoomBy(1.25); runFrames(win);
  const before = snapshot();
  X.trace(0); X.traceStep(1); runFrames(win);
  const expected = snapshot();
  const step = A.journeys[0].steps[1];
  report.expectedStepEdge = step.edge;
  X.inspect(step.acts[0]); runFrames(win);
  report.inspected = snapshot();
  A.inspectFlow(step.edge,A.edges[step.edge].to); runFrames(win);
  report.followed = snapshot();
  doc.querySelector('[data-zoom="fit"]').click(); runFrames(win);
  report.fitted = snapshot();
  doc.getElementById('jreturn').click(); runFrames(win);
  report.returned = snapshot(); report.expected = expected;
  doc.getElementById('jend').click(); runFrames(win);
  report.ended = snapshot(); report.before = before;

  const search = doc.getElementById('partsearch');
  report.matches = {};
  ['Reader','reads', 'pkg.reader'].forEach(q => {
    search.value=q; search.dispatchEvent(new EventImpl('input',{bubbles:true}));
    report.matches[q] = doc.querySelectorAll('.ix').filter(b=>!b.hidden).map(b=>({
      id:b.dataset.go, reason:(b.querySelector('.ix__match')||{}).textContent}));
  });
  search.value='nothing-matches'; search.dispatchEvent(new EventImpl('input',{bubbles:true}));
  report.empty = !doc.getElementById('searchempty').hidden;
  report.shortcut = key('/'); report.searchFocused = doc.activeElement===search;
  report.typing = key('/',search);
  const motion = doc.getElementById('reduce-motion');
  motion.checked=true; motion.dispatchEvent(new EventImpl('change',{bubbles:true}));
  report.reduced = doc.documentElement.dataset.reduceMotion;
  report.motion = A.state.motion;

  A.select('Reader'); runFrames(win);
  const nestedBefore = snapshot();
  const opener = doc.querySelector('[data-open-map]');
  const preserved = doc.createElement('div'); preserved.setAttribute('inert','');
  doc.body.appendChild(preserved);
  opener.focus(); opener.click();
  const overlay = doc.getElementById('submap');
  report.backgroundInert = doc.body.children.filter(n=>n!==overlay && n.tag!=='script')
    .every(n=>n.hasAttribute('inert'));
  key('Escape',doc.getElementById('submapclose'));
  report.openerRestored = doc.activeElement===opener;
  report.inertRestored = preserved.hasAttribute('inert');
  report.backgroundRestored = !doc.querySelector('main').hasAttribute('inert');
  report.nestedBefore = nestedBefore; report.nestedAfter = snapshot();
  return report;
}
"""


@pytest.fixture
def navigation_report(sample: Sample, tmp_path: Path) -> dict[str, Any]:
    if shutil.which("node") is None:
        pytest.skip("generated navigation JavaScript needs Node")
    nesting = page.Nesting(
        model_file="map/model.py",
        opens={"Reader": {"name": "Reader map", "href": "Reader/index.html", "cards": 2}},
    )
    html = tmp_path / "map.html"
    model = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, map="reader.py") if c.id == "Reader" else c
            for c in sample.model.components
        ),
    )
    html.write_text(
        page.build(sample.cfg, model, sample.meaning, sample.theme, sample.facts, {}, nesting),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, viewstate};",
    )
    harness = tmp_path / "navigation.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(html), "--scenario", "viewstate"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def test_inspection_following_fit_and_return_preserve_journey(
    navigation_report: dict[str, Any],
) -> None:
    report = navigation_report
    for state in ("inspected", "followed", "fitted"):
        assert report[state]["journey"] == 0 and report[state]["step"] == 1
        assert report[state]["roles"] == report["expected"]["roles"]
    assert report["followed"]["edge"] == report["expectedStepEdge"]
    assert report["fitted"]["edge"] == report["followed"]["edge"]
    assert report["returned"] == report["expected"]
    assert report["ended"] == report["before"]


def test_finder_explains_matches_and_respects_typing(navigation_report: dict[str, Any]) -> None:
    report = navigation_report
    for query in ("Reader", "reads", "pkg.reader"):
        matches = report["matches"][query]
        assert [m["id"] for m in matches] == ["Reader"]
        assert all(m["reason"] for m in matches)
    assert report["shortcut"] and report["searchFocused"] and not report["typing"]
    assert report["empty"]


def test_nested_focus_inert_state_and_motion_control(navigation_report: dict[str, Any]) -> None:
    report = navigation_report
    assert report["backgroundInert"] and report["backgroundRestored"]
    assert report["inertRestored"] and report["openerRestored"]
    assert report["nestedAfter"] == report["nestedBefore"]
    assert report["reduced"] == "true" and report["motion"] is False
