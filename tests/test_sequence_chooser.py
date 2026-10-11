"""The Sequences view: the line colors.

Acceptance:
- A sequence line keeps the color and the arrowhead of its flow kind. The
  current step is the selected line of the map. No line is drawn in amber.
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
        [node, str(harness), str(html), "--scenario", name, "--viewport", viewport],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, object] = json.loads(result.stdout)
    return report


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
