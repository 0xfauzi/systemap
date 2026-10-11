"""The header and the full-screen control of the map page.

Acceptance: the header has no hidden menu. Each header control is a button
with a name, a tooltip and an icon, and it is in the tab order. The page has no
Reference view and no Text view. Full screen opens from one button and the F
key in Map and Changes, with a visible exit and Escape. In Sequences the same
button and key open the step overlay. The DOM harness examines data and
controls. It does not measure browser geometry.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import Sample
from test_map_view import run_scenario

from systemap import page


def header_of(sample: Sample) -> str:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    return html.split("</header>")[0].split('<header class="bar">')[1]


def test_the_header_controls_are_named_icons_and_no_menu_hides_them(sample: Sample) -> None:
    header = header_of(sample)
    assert "<details" not in header and "⋯" not in header
    tools = re.findall(
        r'<button type="button" class="tool" id="([\w-]+)"([^>]*)>(<svg[^>]*>)', header
    )
    names = {id_: attrs for id_, attrs, _svg in tools}
    assert list(names) == [
        "scheme-dark",
        "scheme-light",
        "reduce-motion",
        "keys-open",
        "panel-toggle",
    ]
    for id_, attrs, svg in tools:
        label = re.search(r'aria-label="([^"]+)"', attrs)
        assert label and f'title="{label[1]}"' in attrs, id_
        assert 'aria-hidden="true"' in svg, id_
    assert 'aria-label="Details"' in names["panel-toggle"]
    assert 'aria-controls="readpanel"' in names["panel-toggle"]
    assert 'aria-keyshortcuts="D"' in names["panel-toggle"]
    assert 'aria-pressed="false"' in names["reduce-motion"]
    assert 'aria-keyshortcuts="?"' in names["keys-open"]
    # The screen reader summary of the map stays in the header.
    assert '<p class="sr-only">System map: ' in header


def test_the_page_has_no_reference_and_no_text_view(sample: Sample) -> None:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    for gone in (
        'data-mode="review"',
        'id="reference"',
        'id="atlas"',
        'id="view-reading"',
        "Text view",
        'id="theme-menu"',
        "Work with the source code",
        'id="read-toggle"',
    ):
        assert gone not in html, gone
    # The rules and the help are in the Map panel. The commit opens the source records.
    assert 'id="invariants"' in html and 'id="mapkey"' in html
    assert 'id="snap" aria-expanded="false" aria-controls="snap-pop"' in html


FULL = r"""
function fullscreen(page){
  const {doc,win,A,key}=page,btn=doc.getElementById('full-toggle');
  const state=()=>({full:doc.body.dataset.full||'',pressed:btn.getAttribute('aria-pressed'),
    panel:doc.body.dataset.panel,present:!doc.getElementById('present').hidden,
    disabled:btn.disabled});
  const view=m=>{doc.querySelector('.views [data-mode="'+m+'"]').click();runFrames(win);};
  const report={button:{label:btn.getAttribute('aria-label'),title:btn.getAttribute('title'),
    keys:btn.getAttribute('aria-keyshortcuts'),exit:btn.textContent},start:state()};
  key('f');report.mapKey=state();
  key('Escape');report.mapEscape=state();
  btn.click();report.mapButton=state();
  btn.click();report.mapButtonAgain=state();
  view('change');key('f');report.changeNoComparison=state();
  view('trace');key('f');report.traceKey=state();
  key('Escape');report.traceEscape=state();
  view('understand');key('f');
  A.select(Object.keys(A.detail).filter(id=>id!=='_meta')[0]);runFrames(win);
  report.selection=state();
  key('Escape');report.selectionEscape={full:doc.body.dataset.full||'',focus:A.state.focus};
  return report;
}
"""


def test_full_screen_in_each_view(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "fullscreen", FULL)
    assert report["button"] == {
        "label": "Full screen",
        "title": "Full screen (F)",
        "keys": "F",
        "exit": "Exit full screenEsc",
    }
    assert report["start"] == {
        "full": "",
        "pressed": "false",
        "panel": "open",
        "present": False,
        "disabled": False,
    }
    on = {"full": "true", "pressed": "true", "panel": "closed", "present": False, "disabled": False}
    assert report["mapKey"] == on
    # Escape ends full screen and the panel comes back as it was.
    assert report["mapEscape"] == report["start"]
    assert report["mapButton"] == on and report["mapButtonAgain"] == report["start"]
    # Changes without a comparison has no map to show.
    no_map = report["changeNoComparison"]
    assert isinstance(no_map, dict) and no_map["full"] == "" and no_map["disabled"]
    # In Sequences the same key opens the step overlay. Escape closes it.
    trace = report["traceKey"]
    assert isinstance(trace, dict) and trace["present"] and trace["full"] == ""
    escape = report["traceEscape"]
    assert isinstance(escape, dict) and not escape["present"]
    # A selection in full screen opens the panel. Escape ends full screen first.
    selection = report["selection"]
    assert isinstance(selection, dict) and selection["full"] == "true"
    assert selection["panel"] == "open"
    after = report["selectionEscape"]
    assert isinstance(after, dict) and after["full"] == "" and after["focus"]
