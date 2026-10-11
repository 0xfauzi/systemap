"""The Sequences view: the sequence chooser, the line colors and the phone step layout.

Acceptance:
- The toolbar has no native select. The chooser is a button with
  `aria-haspopup="listbox"` that opens a listbox with one option for each
  sequence: its region map, its name, its entry point and its step count.
  The current sequence is the selected option and has the focus on open.
- The arrow keys, Home, End and a first letter move the focus in the list.
  Enter, Space or a click selects. Escape and Tab close. Keys in the list do
  not change the layer or the step. A new sequence keeps Whole route or
  Steps and starts at step 1.
- On a phone the same chooser is in the phone head.
- A sequence line keeps the color and the arrowhead of its flow kind. The
  current step is the selected line of the map. No line is drawn in amber.
- The phone step fills the screen: the map gets the height that the step
  card and its buttons leave.
The DOM harness examines data and controls. It does not measure browser geometry:
bench/jev/README.md records the browser measurements.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page
from systemap.model import Journey, Meaning, Step

SCENARIO = r"""
function chooser(page){
  const {doc,win,svg,A,key}=page,P=svg.page;
  const btn=doc.getElementById('seqpick'),list=doc.getElementById('seqpick-list');
  const focus=()=>doc.activeElement.dataset?(doc.activeElement.dataset.pick
    ||doc.activeElement.id):'';
  const look=()=>({hidden:list.hidden,expanded:btn.getAttribute('aria-expanded'),
    name:btn.querySelector('.seq-choose__name').textContent,focus:focus(),
    state:P.journey.state(),layer:A.state.layer});
  const report={};
  doc.querySelector('[data-mode="trace"]').click();runFrames(win);
  report.trace=look();
  btn.click();runFrames(win);
  report.open=look();
  report.options=list.querySelectorAll('[role="option"]').map(o=>({pick:o.dataset.pick,
    selected:o.getAttribute('aria-selected'),tabindex:o.getAttribute('tabindex'),
    label:o.querySelector('.seq-pick__label').textContent,
    meta:o.querySelector('.seq-pick__meta').textContent,glyph:!!o.querySelector('svg')}));
  const at=()=>doc.activeElement;
  key('ArrowDown',at());report.down=focus();
  key('End',at());report.end=focus();
  key('ArrowDown',at());report.endDown=focus();
  key('Home',at());report.home=focus();
  key('ArrowUp',at());report.homeUp=focus();
  key('r',at());report.letter=focus();
  report.rightPrevented=key('ArrowRight',at());
  report.afterRight=look();
  key('Escape',at());runFrames(win);
  report.escape=look();
  // The arrow key on the button opens the list.
  key('ArrowDown',btn);report.arrowOpens=look();
  key('Tab',at());report.tab=look();
  // Steps view at step 2: a new sequence keeps Steps and starts at step 1.
  P.journey.step(1);runFrames(win);
  btn.click();key('ArrowDown',at());key('Enter',at());runFrames(win);
  report.enter=look();
  // Whole route: a click on an option keeps Whole route.
  doc.getElementById('jwhole').click();runFrames(win);
  btn.click();list.querySelector('[data-pick="2"]').click();runFrames(win);
  report.click=look();
  // The current sequence again: no change.
  btn.click();list.querySelector('[data-pick="2"]').click();runFrames(win);
  report.same=look();
  // A pointer press outside the chooser closes the list.
  btn.click();doc.body.dispatchEvent(new EventImpl('pointerdown',{bubbles:true}));
  report.outside=look();
  return report;
}
function lines(page){
  const {doc,win,svg,A}=page,P=svg.page;
  doc.querySelector('[data-mode="trace"]').click();runFrames(win);
  const seq=()=>svg.querySelectorAll('.seq-line').map(l=>({cls:l.getAttribute('class'),
    stroke:l.getAttribute('stroke'),head:l.getAttribute('marker-end')}));
  const flows=()=>svg.querySelectorAll('path.flow').map(p=>({edge:+p.dataset.edge,
    stroke:p.getAttribute('stroke'),head:p.getAttribute('marker-end'),
    hot:p.classList.contains('hot')}));
  const report={whole:{seq:seq(),flows:flows(),
    legend:doc.getElementById('map-legend').innerHTML}};
  P.journey.step(1);runFrames(win);
  const hl=svg.querySelector('.flowhl');
  report.steps={seq:seq(),flows:flows(),state:P.journey.state(),
    halo:hl?+hl.getAttribute('data-edge'):-1,legend:doc.getElementById('map-legend').innerHTML};
  report.edges=A.journeys[0].steps.map(st=>st.edge);
  A.inspectFlow(0);runFrames(win);
  report.selected=flows();
  return report;
}
function phone(page){
  const {doc,win,svg}=page,P=svg.page;
  const where=()=>doc.getElementById('seqpick').parentNode.parentNode.id;
  const report={start:where()};
  doc.querySelector('[data-mode="trace"]').click();runFrames(win);
  report.trace={where:where(),phone:doc.body.dataset.phone,state:P.journey.state()};
  return report;
}
"""


def three_sequences(meaning: Meaning) -> Meaning:
    """Give the sample meaning with two more sequences, so that the list has three."""
    more = (
        Journey(
            "parse",
            "Parse an input",
            steps=(
                Step(("Reader",), (), ("Reader", "Parser"), "The reader calls the parser."),
                Step(("Parser",), (), ("Parser", "Writer"), "The parser gives the parts."),
            ),
        ),
        Journey(
            "history",
            "Read the history",
            steps=(Step(("Ledger",), (), ("Ledger", "Parser"), "The ledger gives the history."),),
        ),
    )
    return dataclasses.replace(meaning, journeys=(*meaning.journeys, *more))


def build(sample: Sample, meaning: Meaning | None = None) -> str:
    return page.build(
        sample.cfg, sample.model, meaning or sample.meaning, sample.theme, sample.facts, {}
    )


def run(sample: Sample, tmp_path: Path, name: str, viewport: str = "1600x900") -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("The JavaScript test requires Node.")
    html = tmp_path / "map.html"
    html.write_text(build(sample, three_sequences(sample.meaning)), encoding="utf-8")
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, " + name + "};",
    )
    harness = tmp_path / f"{name}.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", name, "--viewport", viewport, "--phone"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, object] = json.loads(result.stdout)
    return report


def test_chooser_is_a_button_that_opens_a_listbox(sample: Sample) -> None:
    html = build(sample)
    assert '<select id="journey"' not in html and 'id="phone-seq"><option' not in html
    row = re.search(r'<div class="trace-controls" id="tracecontrols"[^>]*>(.*?)<div class="seq-seg"', html)
    assert row, "the chooser is first in the Sequences toolbar"
    assert '<span class="trace-controls__label" id="seqpick-label">Sequence</span>' in row[1]
    button = re.search(r'<button type="button" class="seq-choose__btn" id="seqpick"([^>]*)>', row[1])
    assert button
    for attr in (
        'aria-haspopup="listbox"',
        'aria-expanded="false"',
        'aria-controls="seqpick-list"',
        'aria-labelledby="seqpick-label seqpick"',
    ):
        assert attr in button[1], attr
    name = sample.meaning.journeys[0].label
    assert f'<span class="seq-choose__name">{name}</span><svg class="icon"' in row[1]
    assert (
        '<div class="seq-choose__list" id="seqpick-list" role="listbox" '
        'aria-labelledby="seqpick-label" hidden></div>' in row[1]
    )
    # The phone head has a place for the same chooser, not a second control.
    assert '<div class="phone-seq" id="phone-seq"></div>' in html
    assert html.count('class="seq-choose"') == 1


def test_chooser_without_sequences_is_off(sample: Sample) -> None:
    html = build(sample, dataclasses.replace(sample.meaning, journeys=()))
    button = re.search(r'<button type="button" class="seq-choose__btn" id="seqpick"[^>]*>', html)
    assert button and button[0].endswith(" disabled>")
    assert '<span class="seq-choose__name">No sequences</span>' in html


def test_chooser_keyboard_and_selection(sample: Sample, tmp_path: Path) -> None:
    report = run(sample, tmp_path, "chooser")
    labels = [j.label for j in three_sequences(sample.meaning).journeys]
    assert report["trace"]["hidden"] is True and report["trace"]["expanded"] == "false"
    assert report["trace"]["name"] == labels[0]
    opened = report["open"]
    assert opened["hidden"] is False and opened["expanded"] == "true"
    assert opened["focus"] == "0", "the current sequence has the focus"
    options = report["options"]
    assert [o["label"] for o in options] == labels
    assert [o["selected"] for o in options] == ["true", "false", "false"]
    assert all(o["tabindex"] == "-1" and o["glyph"] for o in options)
    assert options[1]["meta"].endswith("2 steps") and options[2]["meta"].endswith("1 step")
    # Arrow keys, End and Home move the focus and stop at the ends. A letter
    # goes to the next name with that letter.
    assert (report["down"], report["end"], report["endDown"]) == ("1", "2", "2")
    assert (report["home"], report["homeUp"], report["letter"]) == ("0", "0", "2")
    # Keys in the list do not step the sequence or change the layer.
    assert report["rightPrevented"] is False
    assert report["afterRight"]["state"] == opened["state"]
    assert report["afterRight"]["layer"] == opened["layer"]
    # Escape closes the list and gives the focus back. The sequence stays.
    escape = report["escape"]
    assert escape["hidden"] is True and escape["expanded"] == "false"
    assert escape["focus"] == "seqpick" and escape["state"]["j"] == 0
    assert report["arrowOpens"]["hidden"] is False
    assert report["tab"]["hidden"] is True
    # A new sequence keeps the view and starts at step 1.
    assert report["enter"]["state"] == {"j": 1, "s": 0, "view": "steps"}
    assert report["enter"]["name"] == labels[1] and report["enter"]["focus"] == "seqpick"
    assert report["click"]["state"] == {"j": 2, "s": 0, "view": "whole"}
    assert report["click"]["hidden"] is True
    assert report["same"]["state"] == report["click"]["state"]
    assert report["outside"]["hidden"] is True


def test_phone_moves_the_chooser_into_the_phone_head(sample: Sample, tmp_path: Path) -> None:
    report = run(sample, tmp_path, "phone", viewport="390x844")
    assert report["start"] == "phone-seq"
    trace = report["trace"]
    assert trace["where"] == "phone-seq" and trace["phone"] == "step"
    assert trace["state"]["j"] == 0
    wide = run(sample, tmp_path, "phone")
    assert wide["start"] == "tracecontrols"


def test_sequence_lines_keep_the_color_of_their_flow_kind(sample: Sample, tmp_path: Path) -> None:
    report = run(sample, tmp_path, "lines")
    edges = report["edges"]
    assert isinstance(edges, list) and len(edges) == 4
    for state in ("whole", "steps"):
        flows = {f["edge"]: f for f in report[state]["flows"]}
        for line in report[state]["seq"]:
            assert "var(--accent)" not in (line["stroke"] or "")
        assert all(f["stroke"].startswith("var(--l-") for f in flows.values())
        assert all("-m-selected" not in (f["head"] or "") for f in flows.values())
    whole = report["whole"]["seq"]
    assert [line["cls"] for line in whole] == ["seq-line seq-line--route"] * len(whole)
    flows = {f["edge"]: f for f in report["steps"]["flows"]}
    kinds = sorted({line["stroke"] for line in report["steps"]["seq"]})
    assert kinds and all(k.startswith("var(--l-") for k in kinds)
    steps = report["steps"]
    assert steps["state"] == {"j": 0, "s": 1, "view": "steps"}
    hot = [e for e, f in flows.items() if f["hot"]]
    assert hot == [edges[1]] and steps["halo"] == edges[1]
    classes = [line["cls"] for line in steps["seq"]]
    assert classes.count("seq-line seq-line--was") == 1
    assert classes.count("seq-line seq-line--later") == 2
    # The legend names the flow kinds of the route and the step marks.
    for legend in (report["whole"]["legend"], steps["legend"]):
        assert 'class="lg__line" style="--c:var(--l-data)"' in legend
    assert "seq-lg-now" in steps["legend"] and "seq-lg-later" in steps["legend"]
    assert "Route" not in report["whole"]["legend"]
    # A selected flow on the Map view keeps its kind color.
    selected = [f for f in report["selected"] if f["hot"]]
    assert len(selected) == 1 and selected[0]["stroke"].startswith("var(--l-")


def test_one_line_width_scale(sample: Sample) -> None:
    html = build(sample)
    assert "#schematic .flow.hot{stroke-opacity:1;stroke-width:2.6}" in html
    assert "#schematic .flow{stroke-width:1.6;stroke-opacity:1}" in html
    assert ".focused .flow{stroke-width" not in html
    assert "#schematic.card-peek .flow.card-lit{stroke-width:2.6}" in html
    line = re.search(r"#schematic \.seq-line\{([^}]*)\}", html)
    assert line and "stroke-width:1.6" in line[1] and "vector-effect:non-scaling-stroke" in line[1]
    assert "#schematic .seq-line--later{opacity:.4}" in html
    for gone in ("seq-line--was{", "seq-line--route{", "stroke-width:2.2", "stroke-width:1.3"):
        assert gone not in html, gone
    assert "-m-selected" not in html
    # The halo: amber in Ink, the yellow highlighter in Paper.
    assert ':root:not([data-theme="light"]) #schematic .flowhl{stroke:var(--accent)' in html
    assert re.search(r"#schematic \.flowhl\{fill:none;stroke:var\(--hl,", html)


def test_phone_step_fills_the_screen(sample: Sample) -> None:
    html = build(sample)
    assert 'body[data-phone="step"]{display:flex;flex-direction:column}' in html
    assert (
        'body[data-phone="step"] .main{flex:1;display:flex;flex-direction:column;padding-bottom:0}'
        in html
    )
    rule = re.search(r'body\[data-phone="step"\] \.map,[^{]*\{([^}]*)\}', html)
    assert rule and "flex:1" in rule[1] and "height:auto" in rule[1]
    assert "height:340px" not in html
    assert ".phone-step{flex-direction:column;padding-bottom:max(16px,env(safe-area-inset-bottom))}" in html
