"""The History view of the atlas page: where the source files of each component changed, and when.

`atlas_script` joins the script of this part after the Focus part (`atlas_focus`). The rules
are the section "The other views: the rules" of docs/design/atlas.md, and the study
(docs/design/atlas/study-script.html, `drawHistory`). The data comes from `history_data`, in
its own element of the page (`atlas-history`, `atlas_page`):

- The view shows only when the page has history data. Then the header has the button History
  (`atlas_header`).
- One row for each component of the top map with a change, in the order of the cards of the
  page data, and one column for each equal part of the time. The opacity of a cell is
  the square root of the changed lines of the cell divided by the changed lines of the
  largest cell, as the specification gives it. The study adds 0.1 and multiplies by 0.82;
  the specification applies. Each cell has a faint tint below it. Thus a cell with a change
  and no changed line (a binary file) has the tint and no ink, as a cell with no change. Its
  reading line and its name for a screen reader give its file changes. A dot marks a cell with
  a new source module. Bars at the top give the changed lines of each column. The count at
  the right of a row is its count of file changes.
- The headline gives "History", the question "Where did the system change, and when?", the
  count of commits, the dates and, for a shallow clone, the words "the clone is shallow,
  earlier commits are not in it". On a phone the headline also gives the counts. For a
  shallow clone, the board also has a dashed line at the left of the first column with the
  words "Clone starts" and "no earlier commits" (`hsEdge`).
- Pointing at a cell, or the keyboard focus on it, writes the reading line: the component,
  the dates of the part, the count of file changes and changed lines, and the new modules
  (four names at most, and then the count of the others). A click or Enter on a cell keeps
  the reading line (aria-pressed "true"). A second click, a click on the ground and Esc
  remove it.
- The name of a row is a button: it shows the Map view with that card selected.
- The keyboard. The board has one stop of Tab: the cell or the name of the keyboard focus.
  The arrow keys move the keyboard focus through the names and the cells, Home goes to the
  name of the row, and End to the last cell of the row. The map keys do not operate.

The board is SVG, not canvas: it does not zoom (docs/design/atlas.md, "The architecture"). It
is at the right of the headline on a screen wider than 1180 px, and under the headline on the
other screens. Its scale is HS_MIN or more, and on a phone HS_MIN_PHONE or more: then a name of a row is
7.8 px high. On a phone the columns are narrower (HS_PHONE_CW). When the board is larger than its part of the screen at its scale, that part
scrolls. While the board shows, the canvas does not show and draws only the ground (`draw` in
`atlas_input`).
"""

from __future__ import annotations

HTML = (
    '<div id="atlas-hboard" class="hboard" role="group" aria-label="History">'
    '<svg id="atlas-hsvg"><g id="atlas-hworld"></g></svg></div>'
)

# From the study, with the fixed header of the atlas page and the fonts of the product.
CSS = """
body[data-mode="history"] #canvas{visibility:hidden}
body[data-mode="history"] .zoom,body[data-mode="history"] .key,body[data-mode="history"] .note,body[data-mode="history"] .tabs{display:none}
.hboard{position:fixed;left:var(--hb-x,0px);top:var(--hb-y,0px);width:var(--hb-w,100%);height:var(--hb-h,100%);display:none;
overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;z-index:1}
.hboard svg{display:block}
body[data-mode="history"] .hboard{display:block}
.hcell{cursor:pointer;outline:none}
.hcell rect{fill:var(--ink);transition:stroke .12s}
.hcell.none rect,.hcell .hbase{fill:var(--tint)}
.hcell:hover rect,.hcell.lit rect{stroke:var(--focus);stroke-width:2}
.hcell:focus-visible rect{stroke:var(--focus);stroke-width:2.6}
.hborn{fill:var(--brand);pointer-events:none}
.hbar{fill:var(--line-2)}
.hrow{cursor:pointer;outline:none}
.hrow text{font:500 11.5px/1 var(--fs);fill:var(--ink-2);text-anchor:end}
.hrow rect{fill:transparent}
.hrow:hover text,.hrow.lit text{fill:var(--ink)}
.hrow:focus-visible rect{stroke:var(--focus);stroke-width:2}
.hsum{font:400 10.5px/1 var(--fm);fill:var(--ink-3);font-variant-numeric:tabular-nums}
.haxis{font:400 10px/1 var(--fm);fill:var(--ink-3);text-anchor:middle}
.hedge path{stroke:var(--ink-3);stroke-width:1;stroke-dasharray:3 3;fill:none}
.hedge text{font:400 10.5px/1 var(--fs);fill:var(--ink-3);text-anchor:end}
@media (min-width:1181px){body[data-mode="history"] .ask{max-width:290px}}
@media (max-width:720px){body[data-mode="history"] .ask__n{display:block;margin-top:4px}}
"""

HISTORY = r"""
// ---- the History view ----------------------------------------------------------------------
var HS_DATA = (function () {
  var e = document.getElementById('atlas-history');
  try { return e ? JSON.parse(e.textContent) : null; } catch (x) { return null; }
})();
var HS = {hot: null, pin: null, items: [], rows: [], scale: 0, free: null, at: null}, HS_MIN = 0.75, HS_MIN_PHONE = 0.68, HS_PHONE_CW = 26;
var HBOARD = document.getElementById('atlas-hboard'), HSVG = document.getElementById('atlas-hsvg'), HWORLD = document.getElementById('atlas-hworld');
function hsOn() { return VIEW.mode === 'history' && !!HS_DATA; }
// The rows: the cards of the top map with a change, in the order of the cards.
function hsRows() { return HS_DATA ? TOP.cards.filter(function (c) { return HS_DATA.cells[c.id]; }) : []; }
function hsHead() {
  var h = HS_DATA;
  return {k: 'History', q: 'Where did the system change, and when?',
    n: counted(h.commits, 'commit') + ' · ' + h.from + ' to ' + h.to + ' · changed source files, by component' + (h.shallow ? ' · the clone is shallow, earlier commits are not in it' : '')};
}
function hsWords() {
  var h = HS_DATA;
  return 'History. ' + counted(h.commits, 'commit') + ' from ' + h.from + ' to ' + h.to + '. ' + counted(hsRows().length, 'component') + ' with a change.' +
    (h.shallow ? ' The clone is shallow. Earlier commits are not in it.' : '');
}
function hsShow() { cv.tabIndex = -1; SAID_KEY = ''; HS.hot = null; HS.pin = null; headSync(true); hsDraw(); say(hsWords()); }
function hsHide() { HS.hot = null; HS.pin = null; if (SAY) { SAY.classList.remove('on'); SAY.replaceChildren(); } SAID_KEY = ''; }

// ---- the board -----------------------------------------------------------------------------
// The free part of the screen: at the right of the headline on a wide screen, under the
// headline on the other screens, and above the reading line.
function hsFree() {
  askBottom();
  var r = ASK_EL ? ASK_EL.getBoundingClientRect() : {right: 0, bottom: HEAD_H};
  var wide = W > 1180, left = wide ? r.right + 40 : 16, top = wide ? HEAD_H + 24 : r.bottom + 16;
  return {x0: left, y0: top, x1: W - 16, y1: Math.max(top + 1, H - (W > WIDE ? 70 : 84))};
}
function hsCells(id) { return HS_DATA.cells[id]; }
function hsWordsOf(it) {
  var p = HS_DATA.parts[it.j];
  if (it.kind === 'r') return [el('span', {'class': 'sr-only'}, 'Component '), el('b', null, it.id), el('span', null, counted(it.files, 'file change') + ' in all · select to show it on the map')];
  var x = it.cell, n = x[2], words = x[0] ? counted(x[0], 'file change') + ', ' + counted(x[1], 'line') : 'no change';
  if (n.length) words += ' · new: ' + n.slice(0, 4).join(', ') + (n.length > 4 ? ' and ' + (n.length - 4) + ' more' : '');
  return [el('span', {'class': 'sr-only'}, 'Component '), el('b', null, it.id), el('code', null, p[0] + ' to ' + p[1]), el('span', null, words)];
}
function hsLabel(it) {
  if (it.kind === 'r') return it.id + ', ' + counted(it.files, 'file change') + '. Select to show it on the map.';
  var p = HS_DATA.parts[it.j], x = it.cell;
  return it.id + ', ' + p[0] + ' to ' + p[1] + ', ' + (x[0] ? counted(x[0], 'file change') + ', ' + counted(x[1], 'line') : 'no change') +
    (x[2].length ? ', ' + counted(x[2].length, 'new module') : '') + '.';
}
function hsDraw() {
  if (!HWORLD || !hsOn()) return;
  var had = HBOARD.contains(document.activeElement) ? document.activeElement.getAttribute('data-item') : null;
  HWORLD.replaceChildren(); HWORLD.removeAttribute('transform');
  var g = hsFree(), aw = Math.max(1, g.x1 - g.x0), ah = Math.max(1, g.y1 - g.y0), phone = W <= WIDE;
  [['--hb-x', g.x0], ['--hb-y', g.y0], ['--hb-w', aw], ['--hb-h', ah]].forEach(function (v) { document.body.style.setProperty(v[0], v[1] + 'px'); });
  var rows = hsRows(), N = HS_DATA.parts.length, CW = phone ? HS_PHONE_CW : 46, CH = 24, LAB = phone ? 106 : 150, BAR = 46, max = 1, tot = [], every = phone ? 3 : 2;
  rows.forEach(function (c) { hsCells(c.id).forEach(function (x, i) { max = Math.max(max, x[1]); tot[i] = (tot[i] || 0) + x[1]; }); });
  var tmax = Math.max.apply(null, tot.concat([1])), items = [];
  HS_DATA.parts.forEach(function (b, i) {
    var hh = Math.max(1, (tot[i] || 0) / tmax * BAR);
    sv('rect', {x: LAB + i * CW + 3, y: BAR - hh, width: CW - 6, height: hh, rx: 2, 'class': 'hbar'}, HWORLD);
    if (i % every === 0) sv('text', {x: LAB + i * CW + CW / 2, y: BAR + 16, 'class': 'haxis'}, HWORLD, b[0]);
  });
  sv('text', {x: LAB + N * CW + 12, y: BAR + 16, 'class': 'hsum'}, HWORLD, 'files');
  if (HS_DATA.shallow) hsEdge(LAB, BAR + 26 + rows.length * CH);
  rows.forEach(function (c, ri) {
    var y = BAR + 26 + ri * CH, cells = hsCells(c.id), files = 0;
    cells.forEach(function (x) { files += x[0]; });
    var rg = sv('g', {'class': 'hrow', tabindex: '-1', role: 'button', 'data-item': 'r' + ri}, HWORLD);
    sv('rect', {x: 0, y: y + 2, width: LAB - 6, height: CH - 4, rx: 4}, rg);
    fitText(sv('text', {x: LAB - 12, y: y + CH / 2 + 4}, rg, c.id), LAB - 18);
    var row = {kind: 'r', id: c.id, card: c, i: ri, j: -1, files: files, g: rg};
    rg.setAttribute('aria-label', hsLabel(row));
    items.push(row);
    cells.forEach(function (x, i) {
      var cg = sv('g', {'class': 'hcell' + (x[0] ? '' : ' none'), tabindex: '-1', role: 'button', 'aria-pressed': 'false', 'data-item': 'c' + ri + ':' + i}, HWORLD);
      var box = {x: LAB + i * CW + 2, y: y + 2, width: CW - 4, height: CH - 4, rx: phone ? 3 : 4};
      // The tint is under each cell, so that a cell with few lines keeps its place.
      if (x[0]) sv('rect', Object.assign({'class': 'hbase'}, box), cg);
      var r = sv('rect', box, cg);
      if (x[0]) r.setAttribute('fill-opacity', Math.sqrt(x[1] / max).toFixed(2));
      if (x[2].length) sv('circle', {cx: LAB + i * CW + CW - (phone ? 7 : 9), cy: y + 8, r: 3, 'class': 'hborn'}, cg);
      var it = {kind: 'c', id: c.id, card: c, i: ri, j: i, cell: x, g: cg};
      cg.setAttribute('aria-label', hsLabel(it));
      items.push(it);
    });
    sv('text', {x: LAB + N * CW + 12, y: y + CH / 2 + 4, 'class': 'hsum'}, HWORLD, String(files));
  });
  items.forEach(hsWire);
  var bb = HWORLD.getBBox(), k = Math.min(1.25, (aw - 9) / bb.width, (ah - 9) / bb.height);
  if (k < (phone ? HS_MIN_PHONE : HS_MIN)) k = phone ? HS_MIN_PHONE : HS_MIN;
  var tx = Math.max(4, (aw - bb.width * k) / 2), ty = W > 1180 ? Math.max(4, (ah - bb.height * k) / 2) : 4;
  HSVG.setAttribute('width', Math.ceil(Math.max(aw, tx * 2 + bb.width * k)));
  HSVG.setAttribute('height', Math.ceil(Math.max(ah, ty * 2 + bb.height * k)));
  HWORLD.setAttribute('transform', 'translate(' + (tx - bb.x * k) + ' ' + (ty - bb.y * k) + ') scale(' + k + ')');
  HS.items = items; HS.rows = rows; HS.scale = k; HS.free = g; HS.n = N;
  var back = HS.at && HWORLD.querySelector('[data-item="' + HS.at + '"]') ? HS.at : items.length ? items[0].g.getAttribute('data-item') : null;
  hsRove(back, had !== null);
  hsLight(); hsSay();
}
// The mark of a shallow clone: a dashed line at the left of the first column, from the top
// of the bars to the last row, and two words at its left. The clone has no commit before
// this line.
function hsEdge(x, y1) {
  var g = sv('g', {'class': 'hedge', 'aria-hidden': 'true'}, HWORLD);
  sv('path', {d: 'M' + x + ' 0V' + y1}, g);
  sv('text', {x: x - 8, y: 12}, g, 'Clone starts');
  sv('text', {x: x - 8, y: 26}, g, 'no earlier commits');
}
// The one stop of Tab: the item `key`. `focus` gives it the keyboard focus.
function hsRove(key, focus) {
  HS.at = key;
  HS.items.forEach(function (o) {
    var on = o.g.getAttribute('data-item') === key;
    o.g.tabIndex = on ? 0 : -1;
    if (on && focus) o.g.focus({preventScroll: false});
  });
}
function hsWire(it) {
  var g = it.g;
  g.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') hsPoint(it); });
  g.addEventListener('pointerleave', function () { if (HS.hot === it) hsPoint(null); });
  g.addEventListener('focus', function () { HS.at = g.getAttribute('data-item'); if (g.matches(':focus-visible')) hsPoint(it); });
  g.addEventListener('blur', function () { if (HS.hot === it) hsPoint(null); });
  g.addEventListener('click', function (e) { e.stopPropagation(); hsAct(it, false); });
  g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); hsAct(it, true); } });
}
// A name: the Map view with that card selected. A cell: keep the reading line, or remove it.
function hsAct(it, keyed) {
  if (it.kind === 'r') { setMode('map'); select(it.card, {focus: keyed}); return; }
  HS.pin = HS.pin === it ? null : it; hsLight(); hsSay();
}
function hsPoint(it) { HS.hot = it; hsLight(); hsSay(); }
function hsItem() { return HS.hot || HS.pin; }
function hsLight() {
  var it = hsItem();
  HS.items.forEach(function (o) {
    o.g.classList.toggle('lit', !!it && (o === it || (o.kind === 'r' && o.i === it.i)));
    if (o.kind === 'c') o.g.setAttribute('aria-pressed', HS.pin === o ? 'true' : 'false');
  });
}
function hsSay() {
  if (!SAY) return;
  var it = hsItem();
  SAID_KEY = '';
  if (!it) { SAY.classList.remove('on'); SAY.replaceChildren(); return; }
  SAY.replaceChildren.apply(SAY, hsWordsOf(it));
  SAY.classList.add('on');
}
document.addEventListener('click', function (e) {
  if (VIEW.mode === 'history' && HS.pin && !(e.target.closest && e.target.closest('button, a, input, #atlas-say'))) { HS.pin = null; hsLight(); hsSay(); }
});
if (window.ResizeObserver && ASK_BOX) new ResizeObserver(function () {
  if (!hsOn()) return;
  var g = hsFree();
  if (!HS.free || Math.abs(g.x0 - HS.free.x0) > 0.5 || Math.abs(g.y0 - HS.free.y0) > 0.5) hsDraw();
}).observe(ASK_BOX);

// ---- the keys ------------------------------------------------------------------------------
var HS_KEYS = {ArrowLeft: true, ArrowUp: true, ArrowRight: true, ArrowDown: true, Home: true, End: true, Escape: true};
// The keys of the view (`atlas_input`): give true for a key of the view.
function hsKey(e) {
  if (VIEW.mode !== 'history' || !(e.key in HS_KEYS) || !HS.items.length) return false;
  if (e.key === 'Escape') { HS.pin = null; if (HBOARD.contains(document.activeElement)) document.activeElement.blur(); hsPoint(null); return true; }
  var from = null;
  HS.items.forEach(function (o) { if (o.g === document.activeElement) from = o; });
  if (!from) { HS.items.forEach(function (o) { if (o.g.getAttribute('data-item') === HS.at) from = o; }); }
  from = from || HS.items[0];
  var i = from.i, j = from.j, last = HS.rows.length - 1;
  if (e.key === 'ArrowUp') i = Math.max(0, i - 1);
  else if (e.key === 'ArrowDown') i = Math.min(last, i + 1);
  else if (e.key === 'ArrowLeft') j = Math.max(-1, j - 1);
  else if (e.key === 'ArrowRight') j = Math.min(HS.n - 1, j + 1);
  else if (e.key === 'Home') j = -1;
  else if (e.key === 'End') j = HS.n - 1;
  hsRove(j < 0 ? 'r' + i : 'c' + i + ':' + j, true);
  return true;
}
// The state of the view for the tests.
function hsState() {
  var box = function (e) { return e ? e.getBoundingClientRect().toJSON() : null; };
  return {mode: VIEW.mode, on: hsOn() && !!HBOARD && getComputedStyle(HBOARD).display !== 'none', has: !!HS_DATA, data: HS_DATA, scale: HS.scale,
    view: box(HBOARD), scroll: HBOARD ? [HBOARD.scrollWidth, HBOARD.scrollHeight, HBOARD.clientWidth, HBOARD.clientHeight] : null,
    pin: HS.pin ? HS.pin.g.getAttribute('data-item') : null, at: HS.at,
    active: document.activeElement ? document.activeElement.getAttribute('data-item') : null,
    label: HBOARD ? HBOARD.getAttribute('aria-label') : null,
    bars: HWORLD ? Array.prototype.map.call(HWORLD.querySelectorAll('.hbar'), function (b) { return {h: +b.getAttribute('height'), box: box(b)}; }) : [],
    axis: HWORLD ? Array.prototype.map.call(HWORLD.querySelectorAll('.haxis'), function (t) { return t.textContent; }) : [],
    sums: HWORLD ? Array.prototype.map.call(HWORLD.querySelectorAll('.hsum'), function (t) { return t.textContent; }) : [],
    edge: HWORLD ? Array.prototype.map.call(HWORLD.querySelectorAll('.hedge text'), function (t) { return {text: t.textContent, box: box(t)}; }) : [],
    items: HS.items.map(function (o) {
      var r = o.g.querySelector('rect:last-of-type'), t = o.g.querySelector('text');
      return {kind: o.kind, id: o.id, i: o.i, j: o.j, key: o.g.getAttribute('data-item'), label: o.g.getAttribute('aria-label'), lit: o.g.classList.contains('lit'),
        cls: o.g.getAttribute('class'), tab: o.g.tabIndex, opacity: r.getAttribute('fill-opacity'), dot: !!o.g.querySelector('.hborn'), rect: box(r),
        text: t ? {text: t.textContent, px: parseFloat(getComputedStyle(t).fontSize) * HS.scale} : null};
    })};
}
"""
