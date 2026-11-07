"""The Changes view of the canvas page: the change marks, the lost flows and the roll-up.

`page_canvas` joins this part after the list of the tree (`page_canvas_tree`). It reads the
change keys of the canvas data (`canvas_changes`) and puts its functions in
`VIEWS.changes`, the seam of the view part (`page_canvas_view`). The view follows the change
map of the linked page (`schematic_change`):

- A card with changed source has a ring of 2 px in the change color and the filled tag
  CHANGED. A card with only changed tests has a ring of 1.2 px and the outlined tag TESTS.
  A card that imports changed source has a dashed ring of 1.2 px and the tag IMPORTS with a
  dashed outline.
- The other end of a lost flow has the opacity 0.6, and each other card has the opacity
  0.32. A card that is "changed inside" keeps the full opacity. When a card that opens a
  map opens, its opacity goes to 1 (`drawOpening`). Then the cards of its map show their
  own marks.
- Only the lost flows show: the flows of a card with changed source that have structural
  or declared evidence. They have the change color and the dash of their evidence.
- A card that opens a map with a change inside it (the roll-up) has a second outline on
  its back card, in the change color, and the note "changed inside" on the lower edge of
  its back card, at the right. The note shows only when the card is wider than the note.
  It fades in with the width of the card.
- A map without a revision comparison does not change in this view.
- A bar under the header gives the comparison and the roll-up of the current map in words
  (`chgHere`): the map changes, the cards that are "changed inside", or the reason that the
  map changes are not known. Thus a person sees these words also at the fit of a large map,
  where the notes are too small, and when the roll-up is not known. The bar is part of the
  top band of the screen (`band`), as the toolbar of the Sequences view is.

The values of each card and each flow are constant. Thus the part makes them one time,
and a frame only reads them. The seam fades each change: 0.2 or less in one frame, and 1 in
160 ms or more, and at one time with reduced motion. The seam also draws the marks, and it
puts the epoch of the view in the key of each image of a large map.

A page without a revision comparison has no change keys. Its Changes view shows the text
and the command of the linked page (`page_changes.empty`) in a DOM element over the canvas,
in place of the bar. The bar and that element fade in and out in 160 ms, and at one time
with reduced motion.
The list of the tree and the live region give the change words of each card and each map
in the Changes view (`facts` and `say`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from systemap import page_changes

CHANGES = r"""
// ---- the Changes view ---------------------------------------------------------------
var CHG_DIM = {end: 0.6, none: QUIET};
var CHG_WORDS = {changed: 'changed source', tests: 'only tests changed', imports: 'imports changed source'};
var CHG_RING = {changed: {c: '--change', w: 2}, tests: {c: '--change', w: 1.2}, imports: {c: '--change', w: 1.2, d: 'a'}};
var CHG_TAG = {changed: {s: 'CHANGED', c: '--change', t: '--on-change'},
  tests: {s: 'TESTS', c: '--map', t: '--change', o: {c: '--change'}},
  imports: {s: 'IMPORTS', c: '--map', t: '--ink-2', o: {c: '--change', d: 'r'}}};
var CHG_BACK = {c: '--change', w: 1.2}, CHG_NOTE = {s: 'changed inside', c: '--raised', t: '--ink-2', o: {c: '--change'}};
var CHG_LOST = {a: 1, color: '--change'};
var CHG = {compared: false, m: null};
// The values of the view for each card of a map with a comparison (`_chg`).
function chgValues(c) {
  var dim = CHG_DIM[c.cg], a = c.ci || dim === undefined ? 1 : dim;
  return {a: a, ring: CHG_RING[c.cg] || null, tag: CHG_TAG[c.cg] || null, back: c.ci ? CHG_BACK : null, note: c.ci ? CHG_NOTE : null};
}
ORDER.forEach(function (m) {
  if (!m.ch) return;
  CHG.compared = true;
  var marks = m.cm || {};
  m.cards.forEach(function (c) { c.cg = marks[c.id] || 'none'; });
  (m.ci || []).forEach(function (id) { if (m.byId[id]) m.byId[id].ci = true; });
  (m.cl || []).forEach(function (i) { if (m.flows[i]) m.flows[i].lo = true; });
  m.cards.forEach(function (c) { c._chg = chgValues(c); });
});
// The bar under the header (`HTML`) and the text for a page without a revision comparison
// (`page_changes.empty`). Each one fades in and out in 160 ms, as the toolbar of the
// Sequences view does. A page with a comparison shows the bar, and a page without one shows
// the text.
var CHG_BAR = document.getElementById('cchg'), CHG_EMPTY = document.getElementById('canvas-changes-empty'), CHG_BAR_H = 0;
var CHG_PANEL = CHG.compared ? CHG_BAR : CHG_EMPTY;
function chgShow(on) {
  var el = CHG_PANEL;
  if (!el) return;
  if (on) {
    // The element comes into the page. The read of its box makes the browser give it its
    // style before the fade starts.
    el.hidden = false;
    var h = el.getBoundingClientRect().height;
    if (el === CHG_BAR) CHG_BAR_H = h;
    el.classList.add('on');
    return;
  }
  el.classList.remove('on');
  if (reduced()) el.hidden = true;
  else setTimeout(function () { if (VIEW.mode !== 'changes') el.hidden = true; }, 170);
}
VIEWS.changes = {
  card: function (c) { return c._chg || null; },
  flow: function (f) { return f.map.ch ? (f.lo ? CHG_LOST : FLOW_OFF) : null; },
  enter: function () { chgHere(currentMap()); chgShow(true); },
  leave: function () { chgShow(false); },
  // The bar gives the changes of the current map (`relabel`).
  here: function (m) { chgHere(m); },
  band: function (fresh) {
    if (!CHG.compared || !CHG_BAR) return 0;
    if ((fresh || !CHG_BAR_H) && !CHG_BAR.hidden) CHG_BAR_H = CHG_BAR.getBoundingClientRect().height;
    return CHG_BAR_H;
  },
  facts: function (c) {
    var out = [];
    if (CHG_WORDS[c.cg]) out.push('Change: ' + CHG_WORDS[c.cg] + '.');
    if (c.ci) out.push('Changed inside: the map of this card or a map below it has map changes.');
    var r = c.child && c.child.cr;
    if (r && r.e) out.push('The map changes of the map of this card are not known.');
    else if (r && r.n) out.push('Map changes in the map of this card: ' + r.w + '.');
    return out.join(' ');
  },
  say: function (m) { return ' ' + chgMapWords(m); }
};
// The reason of a roll-up that is not known, with no period at its end: the words put it
// in a sentence.
function chgReason(r) { return String(r.e).replace(/[\s.]+$/, ''); }
// The words of the roll-up of map m: its map changes, or the reason that they are not known.
function chgRollWords(m) {
  var r = m.cr || {};
  if (r.e) return 'The map changes are not known, because ' + chgReason(r) + '.';
  var out = r.n ? 'Map changes: ' + r.w + '.' : 'No map change in this map.';
  return out + ((m.ci || []).length ? ' Changed inside: ' + m.ci.join(', ') + '.' : '');
}
// The words of the changes of a map, for the live region and the list of the tree.
function chgMapWords(m) {
  if (!CHG.compared) return 'This page has no revision comparison. Make the page again with ' + CHG_COMMAND + '.';
  if (!m.ch) return 'The map ' + mapName(m) + ' has no revision comparison.';
  var n = {changed: 0, tests: 0, imports: 0};
  m.cards.forEach(function (c) { if (n[c.cg] !== undefined) n[c.cg]++; });
  return 'Compare ' + m.ch.base + ' to ' + m.ch.head + '. Changed source: ' + counted(n.changed, 'card') +
    '. Only tests changed: ' + counted(n.tests, 'card') + '. Imports changed source: ' + counted(n.imports, 'card') + '. ' + chgRollWords(m);
}
// The text of the bar for map m: the comparison and the roll-up. The text changes only when
// the current map changes, and the bar has a constant height.
function chgHere(m) {
  if (!CHG.compared || !CHG_BAR || m === CHG.m) return;
  CHG.m = m;
  CHG_BAR.textContent = m.ch ? 'Compare ' + m.ch.base + ' to ' + m.ch.head + '. ' + chgRollWords(m) : 'The map ' + mapName(m) + ' has no revision comparison.';
}
if (CHG_EMPTY) {
  var copy = CHG_EMPTY.querySelector('button[data-copy]');
  if (copy) copy.addEventListener('click', function () {
    var done = function () { say('The page copied the command ' + CHG_COMMAND + '.'); };
    var not = function () { say('The browser did not copy the command. Select the command and copy it.'); };
    try { navigator.clipboard.writeText(CHG_COMMAND).then(done, not); } catch (e) { not(); }
  });
}
// The state of the Changes view for the tests: the fade of the view, the bar or the text
// for a page without a comparison, and the mark, the roll-up and the alpha on the screen of
// each card of a map.
function changeState(mapId) {
  var m = MAPS[mapId || ''];
  return {t: VIEW_SHOW.changes, compared: CHG.compared, panel: !!CHG_EMPTY && !CHG_EMPTY.hidden,
    bar: CHG_BAR && !CHG_BAR.hidden ? CHG_BAR.textContent : null,
    cards: m ? m.cards.map(function (c) { return {id: c.id, mark: c.cg || '', inside: !!c.ci, alpha: c._v && c._vAt >= drawn - 1 ? c._v.a : cardAim(c).a}; }) : []};
}
"""

# The bar of the Changes view. It is in the header element, but it is fixed under it, as the
# toolbar of the Sequences view (`page_canvas_sequences`). Its height is constant for a
# screen: one line, or two lines on a narrow screen. Thus a new text does not move the top
# band of the screen. A text that is too long ends with three dots, and the live region and
# the list of the tree give all of it. On a narrow screen the bar has no padding at the
# bottom, so that the edge of the bar cuts the text after the second line.
HTML = '<p class="cchg" id="cchg" hidden></p>'

CSS = """
.cbar .cchg{position:fixed;left:0;right:0;top:48px;z-index:4;box-sizing:border-box;
height:33px;margin:0;padding:0 16px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;
font:13px/32px var(--fs);color:var(--ink-2);border-bottom:1px solid var(--line);
background:var(--surface);visibility:hidden;opacity:0;
transition:opacity .16s ease-out,visibility 0s linear .16s}
.cbar .cchg.on{visibility:visible;opacity:1;transition:opacity .16s ease-out}
.cbar .cchg[hidden]{display:none}
@media (max-width:820px){.cbar .cchg{display:-webkit-box;height:49px;padding:6px 8px 0;
white-space:normal;line-height:21px;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
@media (pointer:coarse){.cbar .cchg{top:56px}}
.cv-empty{position:fixed;left:50%;top:50%;z-index:2;box-sizing:border-box;
width:min(460px,calc(100% - 32px));max-height:calc(100% - 32px);overflow:auto;
transform:translate(-50%,-50%);padding:20px 24px;font:14px/20px var(--fs);color:var(--ink);
background:var(--raised);border:1px solid var(--line-2);border-radius:12px;
visibility:hidden;opacity:0;transition:opacity .16s ease-out,visibility 0s linear .16s}
.cv-empty.on{visibility:visible;opacity:1;transition:opacity .16s ease-out}
.cv-empty[hidden]{display:none}
.cv-empty h2{margin:0 0 8px;font:600 16px/22px var(--fs)}
.cv-empty p{margin:0 0 12px;color:var(--ink-2)}
.cv-empty .chg-cmd{display:flex;align-items:center;gap:8px;margin:0 0 12px;flex-wrap:wrap}
.cv-empty code{font:13px/20px var(--fm);overflow-wrap:anywhere;color:var(--ink)}
.cv-empty button{min-width:44px;min-height:44px;padding:0 14px;font:600 14px/20px var(--fs);
color:var(--ink);background:var(--surface);border:1px solid var(--line-2);border-radius:8px;
cursor:pointer}
.cv-empty button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){.cbar .cchg,.cbar .cchg.on,.cv-empty,.cv-empty.on{transition:none}}
:root[data-reduce-motion="true"] .cbar .cchg,:root[data-reduce-motion="true"] .cv-empty{transition:none}
"""


def has_comparison(data: Mapping[str, Any]) -> bool:
    """Tell if a map of the canvas data has a revision comparison."""
    return any("ch" in m for m in data.get("maps", ()))


def empty_html(data: Mapping[str, Any]) -> str:
    """Give the element of the Changes view for a page without a revision comparison, or
    nothing for a page with a comparison. The element is hidden until the Changes view."""
    if has_comparison(data):
        return ""
    return (
        '<section id="canvas-changes-empty" class="cv-empty" '
        'aria-label="This page has no revision comparison" hidden>'
        + page_changes.empty()
        + "</section>"
    )


# The command of the text for a page without a comparison, as a JavaScript string.
PART = "var CHG_COMMAND = " + json.dumps(page_changes.COMMAND) + ";\n" + CHANGES
