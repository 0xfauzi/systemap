"""The route search of the group lines does little work, and late lines are the same lines.

Acceptance: on the self-map page with the current group script, the search for
the Data flow and All layers calls cost() fewer than COST_BOUND times. The
script of commit d90d08e called cost() 34,859 times for the same page and
layers, and the current script calls it 3,119 times. On a page with 72 cards,
the old script blocked the browser for 10 to 12 s. When the search cannot end
in its wait time, the map shows no group line at first. After the idle work,
the lines are the same as the lines of a search that ends at once. The Node
harness runs the page script with fixed geometry.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from test_keyboard import DRIVER, SELF_MAP, needs_node

from systemap import page, page_groups

# The bound is approximately three times lower than the count of the old
# script, and approximately four times higher than the count of this script.
COST_BOUND = 12_000

# The search adds one to the count at each call of cost(): one shape with the
# lines and badges of the layer.
COUNTED = r"function cost\([^)]*\)\{"

SCENARIOS = r"""
function readLines(page) {
  return page.svg.querySelectorAll('.fg-line').map((p) => p.getAttribute('d'));
}
function grouplinework(page) {
  const {doc, win} = page;
  const out = {layers: {}};
  ['data', 'all'].forEach((layer) => {
    doc.querySelector('[data-layer-btn="' + layer + '"]').click();
    runFrames(win);
    out.layers[layer] = readLines(page);
  });
  out.costs = win.__costs || 0;
  return out;
}
function grouplinelater(page) {
  const {doc, win} = page;
  doc.querySelector('[data-layer-btn="data"]').click();
  runFrames(win);
  const out = {before: readLines(page).length, parts: 0};
  while ((win.__idle || []).length && out.parts < 100000) { win.__idle.shift()(); out.parts++; }
  runFrames(win);
  out.after = readLines(page);
  return out;
}
"""


def current_page(tmp_path: Path, name: str, *edits: tuple[str, str]) -> Path:
    """Write the self-map page with the current group script, and count the calls to cost()."""
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    script, n = re.subn(
        COUNTED,
        lambda m: m.group(0) + " window.__costs = (window.__costs || 0) + 1;",
        page._compact(page_groups.SCRIPT),
    )
    assert n == 1, "one cost function"
    for old, new in edits:
        assert script.count(old) == 1, old
        script = script.replace(old, new)
    html = SELF_MAP.read_text(encoding="utf-8")
    blocks = [
        m
        for m in re.finditer(r"<script>(.*?)</script>", html, flags=re.S)
        if "P.groups = {" in m.group(1)
    ]
    assert len(blocks) == 1, "one group script in the page"
    out = tmp_path / name
    out.write_text(html[: blocks[0].start(1)] + script + html[blocks[0].end(1) :], encoding="utf-8")
    return out


def drive(tmp_path: Path, html: Path, scenario: str) -> dict[str, object]:
    """Run one scenario of the Node harness on the page, and give its report."""
    driver = DRIVER.read_text(encoding="utf-8").replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, grouplinework, grouplinelater};",
    )
    harness = tmp_path / "group-line-work.js"
    harness.write_text(driver + SCENARIOS, encoding="utf-8")
    result = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(html), "--scenario", scenario],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, object] = json.loads(result.stdout)
    return report


@needs_node
def test_group_line_search_calls_cost_few_times(tmp_path: Path) -> None:
    report = drive(tmp_path, current_page(tmp_path, "work.html"), "grouplinework")
    layers = report["layers"]
    assert isinstance(layers, dict)
    assert layers["data"] and layers["all"], "the two layers show groups"
    costs = report["costs"]
    assert isinstance(costs, int)
    assert 0 < costs < COST_BOUND, costs


@needs_node
def test_lines_after_the_idle_work_are_the_same_lines(tmp_path: Path) -> None:
    # The wait time is zero, and the idle work goes into a list that the scenario empties.
    later = current_page(
        tmp_path,
        "later.html",
        ("WAIT = 120", "WAIT = 0"),
        (
            "(window.requestIdleCallback || window.setTimeout)(work);",
            "(window.__idle = window.__idle || []).push(work);",
        ),
    )
    report = drive(tmp_path, later, "grouplinelater")
    now = drive(tmp_path, current_page(tmp_path, "now.html"), "grouplinework")
    layers = now["layers"]
    assert isinstance(layers, dict)
    assert report["before"] == 0, "no group line before the work is done"
    assert isinstance(report["parts"], int) and report["parts"] > 1, "the work goes in parts"
    assert report["after"] == layers["data"]
