"""Map text at Fit: the camera, the labels that grow and the phone step frame.

Acceptance (bench/jev/README.md, "Map text at Fit"):
- Fit shows the drawn map (`data-fit`: containers, regions, cards, paths and
  labels), not the empty margin of the viewBox. It keeps the map 8 px from the
  frame and above one line of the legend. The page opens at Fit.
- Below 100 percent, a flow label grows so that it shows at 11 px, but not
  larger than the card descriptions (`data-grow`). It moves along its own line to
  a free place. A label with no free place is with the labels beside their lines.
  At 100 percent and more, the labels keep their layout size and place.
- A phone step frame stays at or above the zoom at which card text is readable
  (`data-read`), and the acting card stays in view.
- The layout does not change: the label boxes keep 6.1 units for each character.
- The title block is one line, and the text of the Sequences marks is 13.6 units.
The DOM harness has no layout. Chromium measurements are in bench/jev/README.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample

from systemap import page
from systemap.page_sequences import MARKS_CSS
from systemap.schematic import render as render_schematic
from systemap.schematic_cards import LABEL_CHAR_W

DRIVER = Path(__file__).with_name("page_driver.js")

SCENARIOS = r"""
function fitscene(page){
  const {doc,win,svg,A}=page,lg=doc.getElementById('map-legend');
  const out={box:svg.getAttribute('data-fit').split(' ').map(Number),boot:A.view.snapshot(),
    bootFit:A.view.isFit(),zoom:doc.getElementById('zpct').textContent};
  const s=svg.getBoundingClientRect();
  out.svg={left:s.left,top:s.top,right:s.right,bottom:s.bottom};
  lg.hidden=false;
  lg.getBoundingClientRect=()=>({left:24,top:s.bottom-34,right:300,bottom:s.bottom-10,
    width:276,height:24});
  A.view.zoomBy(1.25);runFrames(win);
  out.zoomedFit=A.view.isFit();
  A.view.fit(true);runFrames(win);
  out.fit=A.view.snapshot();out.isFit=A.view.isFit();out.legendTop=s.bottom-34;
  return out;
}
function growscene(page){
  const {doc,win,svg,A}=page;
  const look=()=>svg.querySelectorAll('.flowlbl').map(l=>{
    const h=l.querySelector('.flowlbl__hit');
    return {edge:+l.dataset.edge,tf:l.getAttribute('transform')||'',
      shown:!l.classList.contains('off'),beside:A.besideEdges.indexOf(+l.dataset.edge)>=0,
      hit:['x','y','width','height'].map(k=>+h.getAttribute(k))};
  });
  const out={grow:+svg.getAttribute('data-grow'),layer:A.state.layer};
  out.cards=svg.querySelectorAll('.node__box').map(r=>['x','y','width','height']
    .map(k=>+r.getAttribute(k)));
  A.view.restore({k:1,tx:0,ty:0},true);runFrames(win);
  out.at100=look();
  A.view.restore({k:0.7,tx:0,ty:0},true);runFrames(win);
  out.at70=look();
  return out;
}
function phonestep(page){
  const {doc,win,svg,A}=page,P=svg.page;
  // A small map frame: 240 by 200 pixels.
  svg.getBoundingClientRect=()=>({left:0,top:0,right:240,bottom:200,width:240,height:200,
    x:0,y:0});
  doc.querySelector('[data-mode="trace"]').click();runFrames(win);
  const out={read:+svg.getAttribute('data-read'),steps:[]};
  A.journeys.forEach((j,k)=>j.steps.forEach((st,s)=>{
    if(P.journey.state().j!==k){P.journey.start(k);runFrames(win);}
    P.sequence.go('steps',s,'frame');runFrames(win);
    const box=id=>{const n=svg.querySelectorAll('.node').filter(x=>x.dataset.id===id)[0];
      const r=n.querySelector('.node__box');
      return ['x','y','width','height'].map(a=>+r.getAttribute(a));};
    out.steps.push({j:k,s:s,phone:doc.body.dataset.phone,view:A.view.snapshot(),
      acts:(st.acts||[]).map(box)});
  }));
  return out;
}
"""


def run(sample: Sample, tmp_path: Path, name: str, *flags: str) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("The JavaScript test requires Node.")
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = DRIVER.read_text(encoding="utf-8").replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, " + name + "};",
    )
    harness = tmp_path / f"{name}.js"
    harness.write_text(driver + SCENARIOS, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", name, *flags],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    return report


def svg_tag(sample: Sample) -> str:
    svg, _detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    found = re.match(r"<svg [^>]*>", svg)
    assert found
    return found[0]


def test_the_svg_gives_the_drawn_bounds_and_the_label_limits(sample: Sample) -> None:
    tag = svg_tag(sample)
    # The sample containers are the drawn bounds: (16, 16) to (884, 384).
    assert 'data-fit="16 16 868 368"' in tag
    # The card descriptions are 13.6 units and the labels 11: a label grows to 1.236.
    assert 'data-grow="1.236"' in tag
    # Card names at 12 px and descriptions at 11 px: the zoom is 12 / 14.75.
    assert 'data-read="0.814"' in tag
    svg, _detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    assert '<g class="box__h" data-at="16 16 186">' in svg
    assert '<g class="zone__h" data-zone="work" data-at="240 66 626">' in svg


def test_the_label_layout_keeps_its_widths(sample: Sample) -> None:
    """The page scales the labels. The layout boxes that the checks read do not change."""
    _svg, detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    labels = json.loads(detail)["_meta"]["labels"]
    assert labels
    for label in labels:
        assert label["box"][2] == round(len(label["artifact"]) * LABEL_CHAR_W + 6, 1)


def test_fit_shows_the_drawn_map_above_the_legend(sample: Sample, tmp_path: Path) -> None:
    report = run(sample, tmp_path, "fitscene")
    x, y, w, h = report["box"]
    s = report["svg"]
    # The harness puts one viewBox unit on one pixel. The page opens at Fit:
    # the drawn map 8 px from the frame, at the largest zoom that shows all of it.
    boot = report["boot"]
    assert report["bootFit"] is True
    assert boot["k"] == pytest.approx(
        min((s["right"] - s["left"] - 16) / w, (s["bottom"] - s["top"] - 16) / h)
    )
    assert report["zoom"] == f"{round(boot['k'] * 100)}%"
    assert report["zoomedFit"] is False
    # With a legend at the foot, Fit keeps the drawn map above it, 8 px clear.
    fit = report["fit"]
    assert report["isFit"] is True
    k, tx, ty = fit["k"], fit["tx"], fit["ty"]
    assert k * y + ty >= s["top"] + 8 - 1e-6
    assert k * (y + h) + ty <= report["legendTop"] - 8 + 1e-6
    assert k * x + tx >= s["left"] + 8 - 1e-6
    assert k * (x + w) + tx <= s["right"] - 8 + 1e-6
    assert k == pytest.approx(
        min((s["right"] - s["left"] - 16) / w, (report["legendTop"] - s["top"] - 16) / h)
    )


def label_box(label: dict[str, Any]) -> tuple[float, float, float, float]:
    """The text box of a label in drawing units, after its transform."""
    hx, hy, hw, hh = label["hit"]
    s, e, f = 1.0, 0.0, 0.0
    if label["tf"]:
        values = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", label["tf"])]
        s, e, f = values[0], values[4], values[5]
    return hx * s + e, (hy + 6) * s + f, hw * s, (hh - 12) * s


def overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def test_labels_grow_on_a_small_map(sample: Sample, tmp_path: Path) -> None:
    report = run(sample, tmp_path, "growscene")
    # At 100 percent each label has its layout size and place.
    assert all(label["tf"] == "" for label in report["at100"])
    # At 70 percent, 11 px needs a scale of 1.57: the card description size stops it at 1.236.
    shown = [label for label in report["at70"] if label["shown"]]
    assert shown, report["layer"]
    for label in shown:
        assert label["tf"].startswith(f"matrix({report['grow']} 0 0 {report['grow']} ")
    boxes = [label_box(label) for label in shown]
    for i, box in enumerate(boxes):
        assert not any(overlap(box, card) for card in report["cards"]), shown[i]
        assert not any(overlap(box, other) for other in boxes[i + 1 :]), shown[i]
    # A shown label is not in the list of labels beside their lines.
    assert not any(label["beside"] for label in shown)


def test_a_phone_step_keeps_a_readable_zoom(sample: Sample, tmp_path: Path) -> None:
    report = run(sample, tmp_path, "phonestep", "--viewport", "390x844", "--phone")
    assert report["steps"]
    read = report["read"]
    small = 0
    for step in report["steps"]:
        assert step["phone"] == "step"
        view = step["view"]
        k = view["k"]
        assert k >= read - 1e-6, step
        # The acting card is in the 240 by 200 frame.
        for x, y, w, h in step["acts"]:
            assert k * x + view["tx"] >= -1e-6, step
            assert k * (x + w) + view["tx"] <= 240 + 1e-6, step
            assert k * y + view["ty"] >= -1e-6, step
            assert k * (y + h) + view["ty"] <= 200 + 1e-6, step
        small += k == pytest.approx(read)
    # In this small frame, at least one step does not fit whole at a readable zoom.
    assert small


def page_css(sample: Sample) -> str:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    return "".join(re.findall(r"<style>(.*?)</style>", html, flags=re.S))


def test_the_title_block_is_one_line_above_the_map(sample: Sample) -> None:
    css = page_css(sample)
    assert ".mapbar{position:relative;margin:62px 24px 0;" in css
    assert "flex-wrap:wrap;align-items:baseline;gap:2px 16px;" in css
    assert ".mapwrap{position:absolute;inset:2px 0 0 0;" in css
    # A window of 1259px or less shows only the question: a layer change does not change Fit.
    assert "@media(max-width:1259px){.mapbar__label{display:none}}" in css


def test_the_sequence_marks_use_the_card_description_size(sample: Sample) -> None:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    assert "#schematic .seq-tagm text{font:700 13.6px var(--fm);" in html
    assert "#schematic .seq-pill .seq-pill__n{font:600 13.6px var(--fm);" in html
    assert "#schematic .seq-co .seq-co__ft{font:13.6px/18px var(--fm);" in html
    assert "textWidth(word, 'seq-tagm', 13.6)" in html
    assert "11.4px" not in MARKS_CSS and "12.5px" not in MARKS_CSS
