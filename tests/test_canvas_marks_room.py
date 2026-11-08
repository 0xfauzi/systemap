"""The budget of the marks images of the canvas page (`marksRoom` in page_canvas_image).

The marks images of all maps have at most MARKS_PX pixels together (docs/design/
nested-canvas.md, "Performance"). The old image of a view change (`img0`) counts too.
Node runs the function with stub maps. The test skips when Node is not there, except when
SYSTEMAP_BROWSER_TESTS is "required".
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

from systemap import page_canvas_image

# Four maps of 4 million pixels, each with an old image of 4 million pixels from a view
# change. The frame 100 draws a fifth map, and the last frame drew none of the four maps.
SCRIPT = """
var MARKS_PX = 16e6, drawn = 100;
function map(id) { return {id: id, img: {px: 4e6, used: 50}, img0: {px: 4e6}}; }
var MARKS = [map('a'), map('b'), map('c'), map('d')], fifth = {id: 'e', img: null, img0: null};
FUNCTIONS
marksRoom(fifth, 4e6);
var kept = MARKS.reduce(function (n, o) { return n + o.img.px + (o.img0 ? o.img0.px : 0); }, 4e6);
process.stdout.write(JSON.stringify({kept: kept, maps: MARKS.length,
  old: MARKS.filter(function (o) { return o.img0; }).length}));
"""


def _functions() -> str:
    found = re.search(r"function marksOld.*?\n}\n", page_canvas_image.IMAGE, re.S)
    assert found is not None
    return found.group(0)


def test_the_old_images_count_in_the_budget() -> None:
    """Before the change, the four old images stayed and the total was 32 million pixels."""
    node = shutil.which("node")
    if node is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail("The node command is necessary.")
        pytest.skip("the test needs Node")
    proc = subprocess.run(
        [node, "-e", SCRIPT.replace("FUNCTIONS", _functions())],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["kept"] <= 16e6
    assert out["old"] == 0
    assert out["maps"] == 3
