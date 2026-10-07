"""Framing uses the drawable SVG area rather than the empty CSS pane.

Acceptance: zero framed endpoint boxes or selected routes outside the drawable
viewBox after fitting. An overlapping side cover removes the same CSS area before
conversion. Cases exercise excess space below and to the right of a meet-scaled
SVG, plus a pane clipped by the window. A fully covered pane preserves the last
valid camera. The local DOM harness checks geometry; it does not measure actual
browser rendering.
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

PANES = (
    {"left": 20, "top": 100, "width": 1000, "height": 600},
    {"left": 20, "top": 100, "width": 1300, "height": 300},
    {"left": -60, "top": -20, "width": 1000, "height": 600},
)

GEOMETRY = r"""
  const pane = PANE;
  const drawing = doc.getElementById('schematic'), vb = drawing.viewBox.baseVal;
  const scale = Math.min(pane.width / vb.width, pane.height / vb.height);
  const offsetX = pane.left - vb.x * scale, offsetY = pane.top - vb.y * scale;
  drawing.getBoundingClientRect = () => rect(pane.left,pane.top,pane.width,pane.height);
  drawing.getScreenCTM = () => ({a:scale,b:0,c:0,d:scale,e:offsetX,f:offsetY,
    inverse(){return {a:1/scale,b:0,c:0,d:1/scale,e:-offsetX/scale,f:-offsetY/scale};}});
  doc.getElementById('drawer').getBoundingClientRect = () =>
    rect(pane.left+pane.width+12,pane.top,340,pane.height);
  win.testGeometry = {pane:pane,scale:scale,offsetX:offsetX,offsetY:offsetY};
"""

SCENARIO = r"""
function drawable(page) {
  const {svg,A,win} = page,g=win.testGeometry,vb=svg.viewBox.baseVal;
  const right=g.pane.left+vb.width*g.scale;
  const covers=[null,
    {side:'left',rect:rect(g.pane.left,g.pane.top,180,g.pane.height)},
    {side:'right',rect:rect(right-180,g.pane.top,180,g.pane.height)}];
  const boxOf=n=>{
    const b=n.querySelector('.node__box');
    return projectedBounds(svg,{x:+b.getAttribute('x'),y:+b.getAttribute('y'),
      w:+b.getAttribute('width'),h:+b.getAttribute('height')});
  };
  const cases=[];
  covers.forEach(cover=>{
    A.edges.forEach((edge,i)=>{
      A.inspectFlow(i,edge.from);runFrames(win);A.view.frameFocus(cover,true);
      const route=svg.querySelector('.flow[data-edge="'+i+'"]').getBBox();
      cases.push({cover:cover,edge:i,area:A.view.visibleArea(cover),
        view:A.view.snapshot(),endpoints:[edge.from,edge.to].map(id=>
          boxOf(svg.querySelector('.node[data-id="'+id+'"]'))),
        route:projectedBounds(svg,{x:route.x,y:route.y,w:route.width,h:route.height})});
    });
  });
  A.view.frameFocus(null,true);
  const before=A.view.snapshot(),frameBefore=A.view.frame();
  const fullCover={side:'left',rect:rect(g.pane.left,g.pane.top,g.pane.width,g.pane.height)};
  A.view.frameFocus(fullCover,true);
  return {geometry:g,viewBox:{x:vb.x,y:vb.y,w:vb.width,h:vb.height},cases:cases,
    window:{width:win.innerWidth,height:win.innerHeight},
    covered:{area:A.view.visibleArea(fullCover),before:before,after:A.view.snapshot(),
      frameBefore:frameBefore,frameAfter:A.view.frame()}};
}
"""


@pytest.fixture(params=PANES, ids=["space-below", "space-right", "clipped-window"])
def drawable_report(
    sample: Sample, tmp_path: Path, request: pytest.FixtureRequest
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated camera JavaScript needs Node")
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "  const context = vm.createContext(win);",
        GEOMETRY.replace("PANE", json.dumps(request.param))
        + "\n  const context = vm.createContext(win);",
    ).replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, drawable};",
    )
    harness = tmp_path / "drawable.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "drawable", "--viewport", "1440x900"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def expected_area(report: dict[str, Any], cover: dict[str, Any] | None) -> dict[str, float]:
    """Intersect the CSS window and cover, then clip to the SVG's native viewBox."""
    geometry, vb, window = report["geometry"], report["viewBox"], report["window"]
    pane, scale = geometry["pane"], geometry["scale"]
    left, top = max(pane["left"], 0), max(pane["top"], 0)
    right = min(pane["left"] + pane["width"], window["width"])
    bottom = min(pane["top"] + pane["height"], window["height"])
    if cover:
        if cover["side"] == "left":
            left = max(left, cover["rect"]["right"] + 12)
        else:
            right = min(right, cover["rect"]["left"] - 12)
    x0 = max(vb["x"], (left - geometry["offsetX"]) / scale)
    y0 = max(vb["y"], (top - geometry["offsetY"]) / scale)
    x1 = min(vb["x"] + vb["w"], (right - geometry["offsetX"]) / scale)
    y1 = min(vb["y"] + vb["h"], (bottom - geometry["offsetY"]) / scale)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def transformed(box: dict[str, float], view: dict[str, float]) -> dict[str, float]:
    return {
        "x": box["x"] * view["k"] + view["tx"],
        "y": box["y"] * view["k"] + view["ty"],
        "w": box["w"] * view["k"],
        "h": box["h"] * view["k"],
    }


def assert_inside(box: dict[str, float], bounds: dict[str, float]) -> None:
    assert box["x"] >= bounds["x"] - 1e-6
    assert box["y"] >= bounds["y"] - 1e-6
    assert box["x"] + box["w"] <= bounds["x"] + bounds["w"] + 1e-6
    assert box["y"] + box["h"] <= bounds["y"] + bounds["h"] + 1e-6


def test_visible_area_excludes_letterboxed_space_and_overlapping_cover(
    drawable_report: dict[str, Any],
) -> None:
    for case in drawable_report["cases"]:
        expected = expected_area(drawable_report, case["cover"])
        assert case["area"] == pytest.approx(expected)
        assert_inside(case["area"], drawable_report["viewBox"])


def test_framed_endpoints_and_route_stay_inside_drawable_area(
    drawable_report: dict[str, Any],
) -> None:
    for case in drawable_report["cases"]:
        bounds = expected_area(drawable_report, case["cover"])
        for box in [*case["endpoints"], case["route"]]:
            drawn = transformed(box, case["view"])
            assert_inside(drawn, drawable_report["viewBox"])
            assert_inside(drawn, bounds)


def test_fully_covered_pane_preserves_the_last_valid_camera(
    drawable_report: dict[str, Any],
) -> None:
    covered = drawable_report["covered"]
    assert covered["area"]["w"] == 0
    assert covered["before"]["k"] > 0
    assert covered["after"] == covered["before"]
    assert covered["frameAfter"] == covered["frameBefore"]
