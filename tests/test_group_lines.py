"""Group lines are horizontal and vertical, as the flow routes are.

Acceptance: in the committed self-map page, every straight part of every group
line in the Data flow and All layers is horizontal or vertical (0.05 units of
tolerance). The bends are quarter curves between the straight parts. The Node
harness runs the page script with fixed geometry.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from test_keyboard import DRIVER, SELF_MAP, needs_node

SCENARIO = r"""
function grouplines(page) {
  const {doc, svg, win} = page;
  const out = {};
  ['data', 'all'].forEach((layer) => {
    doc.querySelector('[data-layer-btn="' + layer + '"]').click();
    runFrames(win);
    out[layer] = svg.querySelectorAll('.fg-line').map((p) => p.getAttribute('d'));
  });
  return out;
}
"""


def straight_parts(d: str) -> list[tuple[float, float, float, float]]:
    """Give the start and end of each L command, after the point before it."""
    tokens = re.findall(r"[MLQ]|-?\d+(?:\.\d+)?", d)
    parts: list[tuple[float, float, float, float]] = []
    x = y = 0.0
    k = 0
    while k < len(tokens):
        command = tokens[k]
        if command == "M":
            x, y = float(tokens[k + 1]), float(tokens[k + 2])
            k += 3
        elif command == "L":
            nx, ny = float(tokens[k + 1]), float(tokens[k + 2])
            parts.append((x, y, nx, ny))
            x, y = nx, ny
            k += 3
        elif command == "Q":
            x, y = float(tokens[k + 3]), float(tokens[k + 4])
            k += 5
        else:
            raise AssertionError(f"unexpected path command {command!r} in {d!r}")
    return parts


@needs_node
def test_group_lines_have_no_diagonal_parts(tmp_path: Path) -> None:
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    driver = DRIVER.read_text(encoding="utf-8").replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, grouplines};",
    )
    harness = tmp_path / "group-lines.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(SELF_MAP), "--scenario", "grouplines"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, list[str]] = json.loads(result.stdout)
    for layer, paths in report.items():
        assert paths, f"the {layer} layer shows groups"
        for d in paths:
            for x0, y0, x1, y1 in straight_parts(d):
                assert abs(x0 - x1) <= 0.05 or abs(y0 - y1) <= 0.05, (layer, d)
