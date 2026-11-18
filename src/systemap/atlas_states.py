"""The States view of the atlas page: the list of the machines, the board and the keys.

`atlas_script` joins the script of this part after the Sequences part (`atlas_sequences`).
The rules are the section "The other views: the rules" of docs/design/atlas.md, and the
study (docs/design/atlas/study-script.html, `drawMachine`):

- The view shows only when a map of the tree has a state machine (`sm` in the page data,
  from `canvas_states`). Then the header has the button States (`atlas_header`).
- The list at the left gives the machines, each with its count of states. When more than
  one map has machines, the list has one group for each map, in tree order. On a narrow
  screen the list is a row of names under the headline.
- The headline gives "State machine", the component of the machine, the label of the
  machine, and the counts of states and transitions.
- The board. Each state has a column and a row (`states.layout`). A state has round ends,
  because a state is not a component. It shows its ID and the short form of its source
  symbol: the last two parts. The first state has a dot and a short line before it.
- A straight transition goes from the edge of its source state to the edge of its target
  state, and its label is above the line. Two or more transitions between the same two
  states bend apart, each to a different side, with their labels at the outer sides
  (`bendsOf`). A straight transition that goes through a different state goes around the
  states, at the right side of its direction (`blocked`, `aroundShape`). A transition from
  a state to the same state is a loop above the state.
- Pointing at a state or a transition, or the keyboard focus on it, lights it and the items
  that touch it. The other states and transitions go back. The reading line (`atlas-say`)
  gives the cause of a transition, and the meaning of a state. For a state it also gives
  "This is the first state." and the findings of the machine for that state
  (`states.findings`). A click or a tap keeps the light and the reading line of the item.
  A click on the ground, a second click on the same item and Esc remove them. A click on a
  different item keeps the light of that item.
- The keyboard. Tab goes through the states and then the transitions. In this view the
  arrow keys move the keyboard focus to the next item (right and down) and to the previous
  item (left and up), also while a button of the list has the focus. Home and End go to the
  first and to the last item. Enter and Space keep the light of the focused item, as a
  click does. Esc removes it. The arrow keys do not move the map.
- The board is in the free part of the screen: at the right of the list on a wide screen,
  under the row of the list on a phone, and above the reading line. Its scale is SM_MIN or
  more, so that its text can be read: on a phone the symbol of a state has a larger font, so
  that each text is 7 px high or more at SM_MIN. When the board is larger than its part of
  the screen at SM_MIN (a phone), that part scrolls.

The board is SVG, not canvas: it does not zoom (docs/design/atlas.md, "The architecture").
The script makes it with DOM functions (`sv` in `atlas_sequences`). It draws the board
again at a change of the machine and of the screen size. While the board shows, the canvas
does not show and draws only the ground (`draw` in `atlas_input`).
"""

from __future__ import annotations

HTML = (
    '<nav class="rail srail" id="atlas-srail" aria-label="State machines">'
    '<div class="rail__list" id="atlas-srail-list"></div></nav>'
    '<div id="atlas-sboard" class="sboard" role="group" aria-label="State machine">'
    '<svg id="atlas-ssvg"><g id="atlas-sworld"></g></svg></div>'
)

# From the study, with the fixed header of the atlas page and the fonts of the product. The
# list has the look of the list of the Sequences view (`.rail` in `atlas_sequences`).
CSS = """
body[data-mode="seq"] .srail{display:none}
body[data-mode="states"] .srail{display:flex}
body[data-mode="states"] #canvas{visibility:hidden}
body[data-mode="states"] .zoom,body[data-mode="states"] .key,body[data-mode="states"] .note,body[data-mode="states"] .tabs{display:none}
.sboard{position:fixed;left:var(--sb-x,0px);top:var(--sb-y,0px);width:var(--sb-w,100%);height:var(--sb-h,100%);display:none;
overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;z-index:1}
.sboard svg{display:block}
body[data-mode="states"] .sboard{display:block}
.snode{cursor:pointer;outline:none;transition:opacity .2s}
.snode rect{fill:var(--card);stroke:var(--ink-3);stroke-width:1;transition:stroke .16s,stroke-width .16s}
.snode .nm{font:600 15px/1 var(--fs);letter-spacing:-.01em;fill:var(--ink);text-anchor:middle}
.snode .gap{font-size:0}
.snode .sy{font:400 10.5px/1 var(--fm);fill:var(--ink-3);text-anchor:middle}
.snode:hover rect,.snode.lit rect{stroke:var(--ink);stroke-width:1.6}
.snode:focus-visible rect{stroke:var(--brand);stroke-width:2.4}
.sstart{fill:var(--ink-3)}
.sstart-l{fill:none;stroke:var(--ink-3);stroke-width:1.3}
.tedge{outline:none;transition:opacity .2s}
.tedge path.wire{fill:none;stroke:var(--wire);stroke-width:1.3;transition:stroke .16s,stroke-width .16s}
.tedge path.hit{fill:none;stroke:transparent;stroke-width:16;cursor:pointer;pointer-events:stroke}
.tedge polygon{fill:var(--ink-3);transition:fill .16s}
.tedge text{font:500 12px/1 var(--fs);fill:var(--ink-2);text-anchor:middle;paint-order:stroke;stroke:var(--map);stroke-width:6px;
stroke-linejoin:round;pointer-events:none}
.tedge text.end{text-anchor:end}.tedge text.start{text-anchor:start}
.tedge.lit path.wire{stroke:var(--ink);stroke-width:2.2}
.tedge.lit polygon{fill:var(--ink)}
.tedge.lit text{fill:var(--ink)}
.tedge.kf path.wire{stroke:var(--brand);stroke-width:2.6}
.tedge.kf polygon{fill:var(--brand)}
.sfocus .tedge:not(.lit),.sfocus .snode:not(.lit){opacity:.38}
@media (min-width:1181px){body[data-mode="states"] .ask{max-width:290px}}
@media (max-width:720px){.snode .sy{font-size:12px}}
@media (min-width:721px) and (max-width:1180px){
body[data-mode="states"] .srail{top:calc(var(--ask-b,248px) + 24px);bottom:96px}
}
"""

STATES = r"""
// ---- the States view ---------------------------------------------------------------------
var SM_MAPS = ORDER.filter(function (m) { return m.sm && m.sm.length; });
var SM = {m: null, k: 0, hot: null, pin: null, items: [], scale: 0}, SM_MIN = 0.6;
var SM_CW = 290, SM_CH = 170, SM_NW = 200, SM_NH = 62;
var SRAIL = document.getElementById('atlas-srail'), SRAIL_LIST = document.getElementById('atlas-srail-list');
var SBOARD = document.getElementById('atlas-sboard'), SSVG = document.getElementById('atlas-ssvg'), SWORLD = document.getElementById('atlas-sworld');
function smX() { return SM.m ? SM.m.sm[SM.k] : null; }
function smOn() { return VIEW.mode === 'states' && !!SM.m; }
// The headline of the view: the kind and the component, the label, and the counts.
function smHead() {
  var x = smX();
  return {k: 'State machine' + (x.of ? ' · of ' + x.of : ''), q: x.n, n: counted(x.st.length, 'state') + ' · ' + counted(x.tr.length, 'transition')};
}
function smWords() {
  var x = smX();
  return 'State machine: ' + x.n + (x.of ? ', of ' + x.of : '') + '. ' + counted(x.st.length, 'state') + ', ' + counted(x.tr.length, 'transition') + '. Map: ' + mapName(SM.m) + '.';
}
// The short form of a source symbol: its last two parts.
function shortSym(s) { return (s || '').split('.').slice(-2).join('.'); }

// ---- the list ----------------------------------------------------------------------------
function smRailWrite() {
  if (!SRAIL_LIST) return;
  var out = [];
  SM_MAPS.forEach(function (m) {
    if (SM_MAPS.length > 1) out.push(el('p', {'class': 'rail__g'}, mapName(m)));
    m.sm.forEach(function (x, k) {
      var b = el('button', {type: 'button', 'data-m': m.oi, 'data-k': k, 'aria-current': 'false'}, el('span', null, x.n), el('i', {'aria-hidden': 'true'}, String(x.st.length)),
        el('span', {'class': 'sr-only'}, ', ' + counted(x.st.length, 'state')));
      b.addEventListener('click', function () { smChoose(m, k); });
      out.push(b);
    });
  });
  SRAIL_LIST.replaceChildren.apply(SRAIL_LIST, out);
}
function smRailSync() {
  if (!SRAIL_LIST) return;
  Array.prototype.forEach.call(SRAIL_LIST.querySelectorAll('button'), function (b) {
    b.setAttribute('aria-current', SM.m && +b.getAttribute('data-m') === SM.m.oi && +b.getAttribute('data-k') === SM.k ? 'true' : 'false');
  });
}
// Show machine k of map m.
function smChoose(m, k) {
  SM.m = m; SM.k = k; SM.hot = null; SM.pin = null;
  smRailSync(); headSync(true); smDraw(); smSay();
  say(smWords());
}
// Show the view (`setMode` in `atlas_sequences`): the machine of the current map, else the
// machine on show, else the first machine.
function smShow() {
  var m = currentMap();
  if (!SM.m || (SM.m !== m && SM_MAPS.indexOf(m) >= 0)) { SM.m = SM_MAPS.indexOf(m) >= 0 ? m : SM_MAPS[0]; SM.k = 0; }
  SM.hot = null; SM.pin = null; SAID_KEY = '';
  smRailSync(); smDraw(); smSay();
  say(smWords());
}
// Leave the view: the reading line of the view goes.
function smHide() { SM.hot = null; SM.pin = null; if (SAY) { SAY.classList.remove('on'); SAY.replaceChildren(); } SAID_KEY = ''; }

// ---- the geometry --------------------------------------------------------------------------
// The bend of each transition. The transitions between the same two states bend apart: in
// the frame of the pair, the offsets are 30, -30, 60, -60 and so on. A transition in the
// other direction has the opposite sign in its own frame, so a pair in two directions goes to
// two sides. A single straight transition that goes through a different state goes around
// the states (AROUND): it is marked with a bend of AROUND, and `aroundShape` draws it.
var AROUND = 999;
function bendsOf(x, pos) {
  var groups = Object.create(null), out = x.tr.map(function () { return 0; });
  x.tr.forEach(function (t, i) {
    if (t.a === t.b) return;
    var key = Math.min(t.a, t.b) + ':' + Math.max(t.a, t.b);
    (groups[key] = groups[key] || []).push(i);
  });
  Object.keys(groups).forEach(function (key) {
    var list = groups[key];
    list.forEach(function (i, j) {
      var t = x.tr[i], s = t.a < t.b ? 1 : -1, o = list.length > 1 ? 30 * (1 + (j >> 1)) * (j % 2 ? -1 : 1) : 0;
      out[i] = list.length === 1 && blocked(x, pos, t) ? AROUND : o * s;
    });
  });
  return out;
}
// True when the straight line of transition t goes through a state that is not one of its
// ends. The box of each state has a margin of 8.
function blocked(x, pos, t) {
  var a = pos[t.a], b = pos[t.b];
  return x.st.some(function (s, i) {
    if (i === t.a || i === t.b) return false;
    var p = pos[i], hw = SM_NW / 2 + 8, hh = SM_NH / 2 + 8;
    for (var n = 1; n < 40; n++) {
      var u = n / 40, qx = a[0] + (b[0] - a[0]) * u, qy = a[1] + (b[1] - a[1]) * u;
      if (Math.abs(qx - p[0]) < hw && Math.abs(qy - p[1]) < hh) return true;
    }
    return false;
  });
}
// The path, the arrowhead and the label of a transition from the point a to the point b
// with the bend `bend`, as in the study: the line starts and ends at the edge of the two
// states. The label of a straight line is above the line. The label of a bent line is at
// the outer side of the bend.
function edgeShape(a, b, bend) {
  var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  var ea = Math.min(Math.abs(ux) > 0.01 ? SM_NW / 2 / Math.abs(ux) : 1e9, Math.abs(uy) > 0.01 ? SM_NH / 2 / Math.abs(uy) : 1e9) + 3;
  var p0 = [a[0] + ux * ea - uy * bend * 0.45, a[1] + uy * ea + ux * bend * 0.45], p1 = [b[0] - ux * (ea + 4) - uy * bend * 0.45, b[1] - uy * (ea + 4) + ux * bend * 0.45];
  var mx = (p0[0] + p1[0]) / 2 - uy * bend, my = (p0[1] + p1[1]) / 2 + ux * bend;
  var tx = p1[0] - mx, ty = p1[1] - my, tl = Math.hypot(tx, ty) || 1;
  tx /= tl; ty /= tl;
  var lx = (p0[0] + 2 * mx + p1[0]) / 4, ly = (p0[1] + 2 * my + p1[1]) / 4;
  return {d: 'M' + p0[0] + ' ' + p0[1] + 'Q' + mx + ' ' + my + ' ' + p1[0] + ' ' + p1[1], tip: [p1[0] + tx * 4, p1[1] + ty * 4], dir: [tx, ty],
    label: bend ? outerLabel(lx, ly, -uy * Math.sign(bend), ux * Math.sign(bend)) : {x: lx, y: ly - 12, cls: null}};
}
// The label of a bent line at the middle (x, y) of the line, at the outer side (nx, ny): 14
// to the side or 12 up or down, as in the study.
function outerLabel(x, y, nx, ny) {
  return {x: x + nx * 14, y: y + ny * 12 + 4, cls: Math.abs(nx) < 0.3 ? null : nx < 0 ? 'end' : 'start'};
}
// A transition around the states between its two states: it leaves the side of its source
// state that faces the side of the bend, near the target, and comes into the same side of
// its target state, near the source. The middle of the line is 40 from the boxes of the two
// states, so that it does not touch a state between them.
function aroundShape(a, b) {
  var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len, nx = -uy, ny = ux;
  var ext = Math.abs(nx) * SM_NW / 2 + Math.abs(ny) * SM_NH / 2 + 3, along = Math.abs(ux) * (SM_NW / 2 - 40) + Math.abs(uy) * (SM_NH / 2 - 12);
  var p0 = [a[0] + nx * ext + ux * along, a[1] + ny * ext + uy * along], p1 = [b[0] + nx * (ext + 4) - ux * along, b[1] + ny * (ext + 4) - uy * along];
  var mx = (p0[0] + p1[0]) / 2 + nx * 80, my = (p0[1] + p1[1]) / 2 + ny * 80;
  var tx = p1[0] - mx, ty = p1[1] - my, tl = Math.hypot(tx, ty) || 1;
  tx /= tl; ty /= tl;
  var lx = (p0[0] + 2 * mx + p1[0]) / 4, ly = (p0[1] + 2 * my + p1[1]) / 4;
  return {d: 'M' + p0[0] + ' ' + p0[1] + 'Q' + mx + ' ' + my + ' ' + p1[0] + ' ' + p1[1], tip: [p1[0] + tx * 4, p1[1] + ty * 4], dir: [tx, ty], label: outerLabel(lx, ly, nx, ny)};
}
// A loop from a state to the same state, above the state.
function loopShape(a) {
  var top = a[1] - SM_NH / 2;
  return {d: 'M' + (a[0] - 22) + ' ' + (top - 3) + 'C' + (a[0] - 34) + ' ' + (top - 56) + ' ' + (a[0] + 34) + ' ' + (top - 56) + ' ' + (a[0] + 22) + ' ' + (top - 7),
    tip: [a[0] + 21, top - 3], dir: [-0.22, 0.98], label: {x: a[0], y: top - 50, cls: null}};
}
function arrowPoints(tip, d) {
  var tx = d[0], ty = d[1];
  return [tip[0], tip[1], tip[0] - tx * 9 - ty * 4.2, tip[1] - ty * 9 + tx * 4.2, tip[0] - tx * 9 + ty * 4.2, tip[1] - ty * 9 - tx * 4.2].join(' ');
}

// ---- the board -----------------------------------------------------------------------------
// The free part of the screen: at the right of the list on a wide screen, under the row of
// the list on a phone, and above the reading line.
function smFree() {
  askBottom();
  var top = HEAD_H + 16, left = 16, bottom = H - (W > WIDE ? 96 : 120);
  if (shownEl(SRAIL)) {
    var r = SRAIL.getBoundingClientRect();
    if (W > WIDE) left = r.right + 14; else top = r.bottom + 10;
  }
  if (W > 1180) top = Math.max(top, HEAD_H + 24);
  else if (W > WIDE && ASK_EL) top = Math.max(top, ASK_EL.getBoundingClientRect().bottom + 16);
  return {x0: left, y0: top, x1: W - 16, y1: Math.max(top + 1, bottom)};
}
function smDraw() {
  if (!SWORLD || !smOn()) return;
  var x = smX(), had = SBOARD.contains(document.activeElement) ? document.activeElement.getAttribute('data-item') : null;
  SWORLD.replaceChildren(); SWORLD.setAttribute('class', '');
  SBOARD.setAttribute('aria-label', 'State machine: ' + x.n);
  var cols = 1, rows = 1, loops = x.tr.some(function (t) { return t.a === t.b; }) ? 60 : 0;
  x.st.forEach(function (s) { cols = Math.max(cols, s.c + 1); rows = Math.max(rows, s.r + 1); });
  var first = x.st.some(function (s) { return s.first; }) ? 40 : 0;
  var bw = (cols - 1) * SM_CW + SM_NW + first, bh = (rows - 1) * SM_CH + SM_NH + loops, g = smFree();
  var aw = Math.max(1, g.x1 - g.x0), ah = Math.max(1, g.y1 - g.y0);
  var k = Math.max(SM_MIN, Math.min(1.25, (aw - 1) / (bw + 80), (ah - 1) / (bh + 60)));
  var tx = Math.max(40 * k, (aw - bw * k) / 2), ty = Math.max(30 * k, (ah - bh * k) / 2);
  [['--sb-x', g.x0], ['--sb-y', g.y0], ['--sb-w', aw], ['--sb-h', ah]].forEach(function (v) { SBOARD.style.setProperty(v[0], v[1] + 'px'); });
  SSVG.setAttribute('width', Math.ceil(Math.max(aw, tx + (bw + 40) * k)));
  SSVG.setAttribute('height', Math.ceil(Math.max(ah, ty + (bh + 30) * k)));
  SWORLD.setAttribute('transform', 'translate(' + (tx + first * k) + ' ' + (ty + loops * k) + ') scale(' + k + ')');
  SM.scale = k;
  var pos = x.st.map(function (s) { return [s.c * SM_CW + SM_NW / 2, s.r * SM_CH + SM_NH / 2]; }), bends = bendsOf(x, pos);
  var gE = sv('g', null, SWORLD), gN = sv('g', null, SWORLD), gT = sv('g', null, SWORLD), items = [];
  x.st.forEach(function (s, i) { items.push(smState(x, s, i, pos[i], gN)); });
  x.tr.forEach(function (t, i) { items.push(smEdge(x, t, i, pos, bends[i], gE, gT)); });
  SM.items = items;
  smLight();
  if (had !== null) { var back = SWORLD.querySelector('[data-item="' + had + '"]'); if (back) back.focus({preventScroll: true}); }
}
function smState(x, s, i, p, parent) {
  // The name starts with the visible text: the ID and the short symbol.
  var words = s.id + (s.sym ? ' ' + shortSym(s.sym) : '') + '. State. ' + (s.y || 'The model gives no meaning for this state.') + (s.first ? ' This is the first state.' : '');
  var g = sv('g', {'class': 'snode', tabindex: '0', role: 'button', 'data-item': 's' + i, 'aria-label': words}, parent);
  if (s.first) {
    sv('circle', {cx: p[0] - SM_NW / 2 - 34, cy: p[1], r: 4, 'class': 'sstart'}, g);
    sv('path', {d: 'M' + (p[0] - SM_NW / 2 - 30) + ' ' + p[1] + 'H' + (p[0] - SM_NW / 2 - 6), 'class': 'sstart-l'}, g);
  }
  sv('rect', {x: p[0] - SM_NW / 2, y: p[1] - SM_NH / 2, width: SM_NW, height: SM_NH, rx: SM_NH / 2}, g);
  // One text element with the ID and the symbol, with a space between them, so that the
  // visible text is the start of the name of the state. The space has no width, so that
  // the ID stays at the middle.
  var tx = sv('text', null, g);
  fitText(sv('tspan', {x: p[0], y: s.sym ? p[1] - 1 : p[1] + 5, 'class': 'nm'}, tx, s.id), SM_NW - 28);
  if (s.sym) { sv('tspan', {'class': 'gap'}, tx, ' '); fitText(sv('tspan', {x: p[0], y: p[1] + 16, 'class': 'sy'}, tx, shortSym(s.sym)), SM_NW - 28); }
  var item = {kind: 's', i: i, g: g, s: s};
  smWire(item, g);
  return item;
}
// The transition: its line, arrowhead and label below the states, and its target for the
// pointer and the keyboard after the states, so that Tab gives the states first.
function smEdge(x, t, i, pos, bend, below, above) {
  var shape = t.a === t.b ? loopShape(pos[t.a]) : bend === AROUND ? aroundShape(pos[t.a], pos[t.b]) : edgeShape(pos[t.a], pos[t.b], bend), from = x.st[t.a].id, to = x.st[t.b].id;
  var look = sv('g', {'class': 'tedge', 'aria-hidden': 'true'}, below);
  sv('path', {d: shape.d, 'class': 'wire'}, look);
  sv('polygon', {points: arrowPoints(shape.tip, shape.dir)}, look);
  sv('text', {x: shape.label.x, y: shape.label.y, 'class': shape.label.cls}, look, t.l);
  var words = 'Transition from ' + from + ' to ' + to + ': ' + t.l + '. ' + (t.c || 'The model gives no cause for this transition.');
  var g = sv('g', {'class': 'tedge', tabindex: '0', role: 'button', 'data-item': 't' + i, 'aria-label': words}, above);
  sv('path', {d: shape.d, 'class': 'hit'}, g);
  var item = {kind: 't', i: i, g: g, look: look, t: t, bend: bend, shape: shape};
  smWire(item, g);
  return item;
}
// Shorten the text element e with "..." when it is wider than w.
function fitText(e, w) {
  var s = e.textContent;
  if (!e.getComputedTextLength || e.getComputedTextLength() <= w) return;
  while (s.length > 1 && e.getComputedTextLength() > w) { s = s.slice(0, -1); e.textContent = s + '...'; }
}
function smWire(item, g) {
  g.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') smPoint(item); });
  g.addEventListener('pointerleave', function () { if (SM.hot === item) smPoint(null); });
  // The look of a transition is not its target: the focus ring of a transition is on its line.
  // A focus from a pointer gives no light: the pointer gives it (`pointerenter`).
  g.addEventListener('focus', function () { if (!g.matches(':focus-visible')) return; if (item.look) item.look.classList.add('kf'); smPoint(item); });
  g.addEventListener('blur', function () { if (item.look) item.look.classList.remove('kf'); if (SM.hot === item) smPoint(null); });
  g.addEventListener('click', function (e) { e.stopPropagation(); smPin(item); });
  g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); smPin(item); } });
}
function smPoint(item) { SM.hot = item; smLight(); smSay(); }
function smPin(item) { SM.pin = SM.pin === item ? null : item; smLight(); smSay(); }
// The item that gives the light and the reading line: the pointed or focused item, else
// the kept item.
function smItem() { return SM.hot || SM.pin; }
// Light the item and the items that touch it: a state, its transitions and their states; a
// transition and its two states.
function smLight() {
  var it = smItem(), x = smX(), states = Object.create(null), edges = Object.create(null);
  if (it && it.kind === 's') {
    states[it.i] = true;
    x.tr.forEach(function (t, i) { if (t.a === it.i || t.b === it.i) { edges[i] = true; states[t.a] = true; states[t.b] = true; } });
  } else if (it) { edges[it.i] = true; states[it.t.a] = true; states[it.t.b] = true; }
  SWORLD.setAttribute('class', it ? 'sfocus' : '');
  SM.items.forEach(function (o) {
    var on = o.kind === 's' ? !!states[o.i] : !!edges[o.i];
    o.g.classList.toggle('lit', on);
    if (o.look) o.look.classList.toggle('lit', on);
  });
}
// The lines of the findings of the machine for state s.
function smFindings(x, s) { return (x.fd || []).filter(function (f) { return f.indexOf('"' + s.id + '"') >= 0; }); }
function smSay() {
  if (!SAY) return;
  var it = smItem(), x = smX();
  SAID_KEY = '';
  if (!it || !x) { SAY.classList.remove('on'); SAY.replaceChildren(); return; }
  var parts;
  if (it.kind === 's') {
    var s = it.s;
    parts = [el('span', {'class': 'sr-only'}, 'State '), el('b', null, s.id),
      el('span', null, [s.y || 'The model gives no meaning for this state.'].concat(s.first ? ['This is the first state.'] : [], smFindings(x, s)).join(' '))];
  } else {
    var t = it.t;
    parts = [el('span', {'class': 'sr-only'}, 'Transition '), el('b', null, x.st[t.a].id, el('span', {'class': 'arr', 'aria-hidden': 'true'}, '→'), el('span', {'class': 'sr-only'}, ' to '), x.st[t.b].id),
      el('code', null, t.l), el('span', null, t.c || 'The model gives no cause for this transition.')];
  }
  SAY.replaceChildren.apply(SAY, parts);
  SAY.classList.add('on');
}
// A click on the ground (not on an item, a control or the reading line) removes the kept light.
document.addEventListener('click', function (e) {
  if (VIEW.mode === 'states' && SM.pin && !(e.target.closest && e.target.closest('button, a, input, #atlas-say'))) smPin(null);
});
if (window.ResizeObserver && ASK_BOX) new ResizeObserver(function () { if (smOn() && askBottom()) smDraw(); }).observe(ASK_BOX);

// ---- the keys ------------------------------------------------------------------------------
var SM_KEYS = {ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1, Home: 0, End: 0, Escape: 0};
// The keys of the view (`atlas_input`): give true for a key of the view.
function smKey(e) {
  if (VIEW.mode !== 'states' || !(e.key in SM_KEYS) || !SM.items.length) return false;
  if (e.key === 'Escape') { SM.pin = null; if (SBOARD.contains(document.activeElement)) document.activeElement.blur(); smPoint(null); return true; }
  var at = -1, n = SM.items.length;
  SM.items.forEach(function (o, i) { if (o.g === document.activeElement) at = i; });
  var to = e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : at < 0 ? (SM_KEYS[e.key] > 0 ? 0 : n - 1) : clamp(at + SM_KEYS[e.key], 0, n - 1);
  SM.items[to].g.focus();
  return true;
}
if (SM_MAPS.length) smRailWrite();
// The state of the view for the tests.
function smState2() {
  var x = smX(), view = SBOARD ? SBOARD.getBoundingClientRect().toJSON() : null;
  return {mode: VIEW.mode, map: SM.m ? SM.m.id : null, k: SM.k, id: x ? x.id : null, scale: SM.scale, view: view,
    on: smOn() && !!SBOARD && getComputedStyle(SBOARD).display !== 'none', cls: SWORLD ? SWORLD.getAttribute('class') : '',
    scroll: SBOARD ? [SBOARD.scrollWidth, SBOARD.scrollHeight, SBOARD.clientWidth, SBOARD.clientHeight] : null,
    rail: SRAIL_LIST ? Array.prototype.map.call(SRAIL_LIST.querySelectorAll('button'), function (b) { return {text: b.textContent, on: b.getAttribute('aria-current') === 'true'}; }) : [],
    railBox: SRAIL ? SRAIL.getBoundingClientRect().toJSON() : null,
    pin: SM.pin ? SM.pin.kind + SM.pin.i : null, hot: SM.hot ? SM.hot.kind + SM.hot.i : null,
    active: document.activeElement ? document.activeElement.getAttribute('data-item') : null,
    items: SM.items.map(function (o) {
      var box = function (e) { return e ? e.getBoundingClientRect().toJSON() : null; };
      if (o.kind === 's') {
        var r = o.g.querySelector('rect'), dot = o.g.querySelector('.sstart');
        return {kind: 's', i: o.i, id: o.s.id, label: o.g.getAttribute('aria-label'), lit: o.g.classList.contains('lit'), opacity: getComputedStyle(o.g).opacity,
          rect: box(r), rx: +r.getAttribute('rx'), h: +r.getAttribute('height'), dot: box(dot), dotLine: box(o.g.querySelector('.sstart-l')),
          texts: Array.prototype.map.call(o.g.querySelectorAll('.nm, .sy'), function (t) { return {text: t.textContent, box: box(t), px: parseFloat(getComputedStyle(t).fontSize) * SM.scale}; })};
      }
      var w = o.look.querySelector('path.wire'), tl = w.getTotalLength(), ctm = w.getScreenCTM(), pts = [];
      for (var s = 0; s <= 16; s++) { var q = w.getPointAtLength(tl * s / 16), sp = new DOMPoint(q.x, q.y).matrixTransform(ctm); pts.push([sp.x, sp.y]); }
      var lt = o.look.querySelector('text');
      return {kind: 't', i: o.i, a: o.t.a, b: o.t.b, l: o.t.l, bend: o.bend, label: o.g.getAttribute('aria-label'), lit: o.look.classList.contains('lit'),
        opacity: getComputedStyle(o.look).opacity, wire: getComputedStyle(w).stroke, points: pts, text: {text: lt.textContent, box: box(lt), px: parseFloat(getComputedStyle(lt).fontSize) * SM.scale},
        tip: box(o.look.querySelector('polygon'))};
    })};
}
"""
