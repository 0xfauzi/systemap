"""A comparison inspector explains the stored source changes it highlights.

Acceptance: zero missing added, removed or changed public names, test-reference
changes or unknown records. Comparison inspection preserves exact relationships
and renders source strings as text. Adjacent and unchanged parts remain distinct.
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
function comparisoninspector(page) {
  const {doc} = page, A=doc.getElementById('changemap').systemap;
  const panel=doc.getElementById('change-panel'), report={};
  ['Reader','Writer','Parser','Ledger'].forEach(id=>{
    A.select(id);
    report[id]=panel.textContent;
  });
  const edge=A.edges.findIndex(e=>e.from==='Reader' || e.to==='Reader');
  A.inspectFlow(edge,'Reader');
  report.exactRelationship=panel.querySelector('[data-relationship]').textContent;
  report.selected=A.state.edge; report.expectedEdge=edge;
  report.evidence=doc.getElementById('change-panel').querySelectorAll('.comparison-source').length;
  report.unsafe=panel.querySelectorAll('img, script').length;
  return report;
}
"""


def test_comparison_inspector_shows_changes_and_limits(sample: Sample, tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated navigation JavaScript needs Node")
    reader: dict[str, Any] = {
        "modules": ["pkg.reader"],
        "gained": {"operations": 1},
        "surface": {
            "added": {"operations": ["new_symbol"]},
            "removed": {"operations": ["removed_symbol"]},
            "changed": {"types": ["Request"]},
            "tests_added": ["tests/test_<new>.py:test_new"],
            "tests_removed": ["tests/test_old.py:test_old"],
        },
        "unknown": {
            "pkg.reader": {
                "base": [],
                "head": [{"line": 3, "column": 2, "reason": "Unknown <img src=x> export"}],
            }
        },
    }
    comparison: dict[str, Any] = {
        "has_change": True,
        "base": "main",
        "head": "feature",
        "direct": {"Reader", "Writer"},
        "adjacent": {"Parser"},
        "modules": {"pkg.reader", "pkg.writer"},
        "flow_artifacts": set(),
        "per_component": {
            "Reader": reader,
            "Writer": {"modules": ["pkg.writer"], "gained": {}, "surface": {}, "unknown": {}},
        },
        "files": 2,
        "reach_known": True,
        "unparsed": ["pkg.writer"],
    }
    html = tmp_path / "map.html"
    html.write_text(
        page.build(
            sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, comparison
        ),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, comparisoninspector};",
    )
    harness = tmp_path / "comparison.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "comparisoninspector"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    for value in (
        "new_symbol",
        "removed_symbol",
        "Request",
        "test_<new>",
        "test_old",
        "head",
        "Unknown <img src=x> export",
    ):
        assert value in report["Reader"]
    assert "pkg.writer" in report["Writer"] and "could not be parsed" in report["Writer"]
    assert "possible import-derived effect" in report["Parser"]
    assert "No source changes were recorded" in report["Ledger"]
    assert "Selected relationship" in report["exactRelationship"]
    assert report["selected"] == report["expectedEdge"]
    assert report["evidence"] == 1 and report["unsafe"] == 0
