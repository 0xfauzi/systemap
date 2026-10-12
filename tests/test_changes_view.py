"""The Changes view: the link that opens it, and the map changes that it shows.

A pull request comment links to `<page>#changes`. The page must open the Changes view
for that link, with a revision comparison or without one, and keep the link while the
reader stays in the view.
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
function viewlink(page) {
  const {doc, win} = page;
  const report = {mode: doc.body.dataset.mode, hash: win.location.hash,
    status: (doc.getElementById('linkstatus') || {textContent: ''}).textContent,
    pressed: doc.querySelector('button[data-mode="change"]').getAttribute('aria-pressed')};
  doc.querySelector('button[data-mode="understand"]').click();
  report.afterMap = {mode: doc.body.dataset.mode, hash: win.location.hash};
  doc.querySelector('button[data-mode="change"]').click();
  report.afterChanges = {mode: doc.body.dataset.mode, hash: win.location.hash};
  return report;
}
"""

COMPARISON: dict[str, Any] = {
    "has_change": True,
    "base": "main",
    "head": "feature",
    "direct": {"Reader"},
    "adjacent": set(),
    "modules": {"pkg.reader"},
    "flow_artifacts": set(),
    "per_component": {"Reader": {"modules": ["pkg.reader"], "gained": {}, "surface": {}}},
    "files": 1,
    "reach_known": True,
    "unparsed": [],
}


def drive(html: str, tmp_path: Path, hash_: str) -> dict[str, Any]:
    """Run the page scripts under the Node DOM harness with a link fragment."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated navigation JavaScript needs Node")
    out = tmp_path / "map.html"
    out.write_text(html, encoding="utf-8")
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    start = "location: {hash: '',"
    assert driver.count(start) == 1
    driver = driver.replace(start, f"location: {{hash: {json.dumps(hash_)},")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, viewlink};",
    )
    harness = tmp_path / "viewlink.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(out), "--scenario", "viewlink"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return dict(json.loads(result.stdout))


@pytest.mark.parametrize("compared", [True, False])
def test_the_changes_link_opens_the_changes_view(
    sample: Sample, tmp_path: Path, compared: bool
) -> None:
    ch = COMPARISON if compared else {"has_change": False}
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, ch)
    report = drive(html, tmp_path, "#changes")
    assert report["mode"] == "change"
    assert report["pressed"] == "true"
    assert report["hash"] == "#changes"
    assert report["status"] == "", "the link is not a missing component"
    # The other views remove the link. Changes puts it back.
    assert report["afterMap"] == {"mode": "understand", "hash": ""}
    assert report["afterChanges"] == {"mode": "change", "hash": "#changes"}


def test_without_the_link_the_page_opens_the_map(sample: Sample, tmp_path: Path) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, COMPARISON
    )
    report = drive(html, tmp_path, "")
    assert report["mode"] == "understand"
    assert report["hash"] == ""
