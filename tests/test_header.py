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


PALETTE = r"""
function palette(page){
  const {doc,win,svg,A,key}=page,box=doc.getElementById('palette');
  const input=doc.getElementById('pal-input'),button=doc.getElementById('find-open');
  const rows=()=>doc.getElementById('pal-list').querySelectorAll('[data-k]').map(o=>({
    group:o.parentNode.querySelector('.pal__g').textContent,
    title:o.querySelector('.pal__t').textContent,
    keys:o.querySelectorAll('kbd').map(k=>k.textContent),
    selected:o.getAttribute('aria-selected')}));
  const groups=()=>rows().map(r=>r.group).filter((g,i,a)=>a.indexOf(g)===i);
  const at=()=>rows().findIndex(r=>r.selected==='true');
  const type=q=>{input.value=q;input.dispatchEvent(new EventImpl('input',{bubbles:true}));};
  const ctrl=target=>{const ev=new EventImpl('keydown',{key:'k',ctrlKey:true,bubbles:true});
    dispatch(target||doc.body,ev);runFrames(win);return ev.defaultPrevented;};
  const ask=q=>{button.click();type(q);key('Enter',input);runFrames(win);};
  const report={};
  // Ctrl+K opens the palette and closes it again.
  report.ctrlOpen=ctrl()&&!box.hidden&&doc.activeElement===input;
  report.empty={groups:groups(),rows:rows()};
  key('ArrowDown',input);report.down=at();
  key('ArrowUp',input);key('ArrowUp',input);report.wrap=at();report.count=rows().length;
  report.ctrlClose=ctrl(input)&&box.hidden;
  // The Find button opens it. Escape closes it and gives the focus back.
  button.focus();button.click();
  report.button={open:!box.hidden,expanded:button.getAttribute('aria-expanded')};
  type('wri');report.wri=rows()[0];
  type('par');report.par=rows()[0];
  type('rule');report.ruleGroups=groups();
  key('Escape',input);
  report.escape={open:!box.hidden,focus:doc.activeElement===button,
    expanded:button.getAttribute('aria-expanded')};
  // Enter does the action of the first result with the page functions.
  ask('Ledger');report.component={focus:A.state.focus,open:!box.hidden};
  A.clear();runFrames(win);
  ask('memory');report.layer=A.state.layer;
  ask('history');report.flow=A.state.edge;
  A.clear();runFrames(win);
  ask('input becomes');report.sequence={mode:doc.body.dataset.mode,j:svg.workspace.state().j};
  ask('splits it');report.step=svg.workspace.state();
  ask('every record');
  report.rule={mode:doc.body.dataset.mode,panel:doc.body.dataset.panel,
    open:doc.getElementById('invariants').hasAttribute('open'),focus:doc.activeElement.id};
  ask('paper');report.theme=doc.documentElement.getAttribute('data-theme');
  ask('reduce');report.motion=doc.documentElement.dataset.reduceMotion;
  return report;
}
"""


def test_the_find_palette_ranks_and_acts(sample: Sample, tmp_path: Path) -> None:
    report = run_scenario(sample, tmp_path, "palette", PALETTE)
    assert report["ctrlOpen"] and report["ctrlClose"]
    # With no text: the views, the layers, the sequences and the actions.
    empty = report["empty"]
    assert isinstance(empty, dict)
    assert empty["groups"] == ["Views", "Layers", "Sequences", "Actions"]
    layers = [r for r in empty["rows"] if r["group"] == "Layers"]
    assert [r["keys"] for r in layers] == [[str(k + 1)] for k in range(len(layers))]
    actions = {r["title"]: r["keys"] for r in empty["rows"] if r["group"] == "Actions"}
    assert actions == {
        "Use the Paper theme": [],
        "Reduce motion": [],
        "Full screen": ["F"],
        "Close the details panel": ["D"],
        "Keyboard keys": ["?"],
    }
    # The arrow keys move the selection and go round at the ends.
    assert report["down"] == 1 and report["wrap"] == report["count"] - 1
    assert report["button"] == {"open": True, "expanded": "true"}
    assert report["escape"] == {"open": False, "focus": True, "expanded": "false"}
    # The start of a name comes first, then the start of a word, then other text.
    # A group name is a match too: "rule" gives the rules first.
    assert report["wri"] == {
        "group": "Components",
        "title": "Writer",
        "keys": [],
        "selected": "true",
    }
    par = report["par"]
    assert isinstance(par, dict) and par["title"] == "Parser"
    groups = report["ruleGroups"]
    assert isinstance(groups, list) and groups[0] == "Rules"
    # Enter selects a component, a layer, a flow, a sequence, a step or a rule.
    assert report["component"] == {"focus": "Ledger", "open": False}
    assert report["layer"] == "memory"
    assert report["flow"] == 4
    assert report["sequence"] == {"mode": "trace", "j": 0}
    assert report["step"] == {"mode": "trace", "j": 0, "s": 2}
    assert report["rule"] == {
        "mode": "understand",
        "panel": "open",
        "open": True,
        "focus": "rule-2",
    }
    # The actions use the header controls.
    assert report["theme"] == "light"
    assert report["motion"] == "true"
