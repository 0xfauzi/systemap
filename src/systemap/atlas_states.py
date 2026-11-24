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
  state. Its label is above the line when the line is horizontal, at the upper side of the
  line when the line is diagonal, and at the right side when the line is vertical. Two or
  more transitions between the same two states bend apart, each to a different side, with
  their labels at the outer sides (`bendsOf`). When the straight line between two states
  goes through a different state, each transition between the two states goes around the
  states, the first two at the two sides (`blocked`, `aroundShape`). Such a line gets a
  larger depth, or goes to the other side, until it goes through no other state (`clear`). A
  transition from a state to the same state is a loop above the state.
- Each end of a line is on the outline of its state, in the direction of the control point
  of the line (`rim`). A state is as wide as its widest ID or symbol, and SM_NW0 or more
  (`smSize`). Thus a state shows its full ID.
- Each label goes to the first place that covers no state, no label before it and no line:
  the middle of its line, then nearer to the ends of its line, then farther out
  (`placeLabels`).
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
  under the row of the list on a phone, and above the reading line. Its scale is SM_MAX or
  less, as in the study. The distance of a label box to its line grows with the scale. At
  SM_MAX it is already more than 12 px on 4 of 7 machines (17.0, 17.5, 17.5 and 49.3 px,
  record C4 of T0 in bench/jev/README.md, bench/jev/t0_states_T0.txt). Its scale is SM_MIN or
  more, so that its text can be read: on a phone the symbol of a state has a larger font, so
  that each text is 7 px high or more at SM_MIN. When the board does not fit at SM_MIN and
  the board with the columns as rows gives a larger scale (a phone), the columns go down
  the screen (`smTurn`). When the board is still larger than its part of the screen, that
  part scrolls, and a mark "More" at a bottom corner tells that a part is out of view at
  the right or below. A click on the mark scrolls the board (`smMore`).
- On a phone the headline also gives the counts, as in the Sequences view.
- Each state and each transition is a button for a screen reader. Its aria-pressed is
  "true" while its light is kept.

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
    '<button type="button" class="smore smore--r" id="atlas-smore-r" hidden'
    ' aria-label="More of the machine at the right">More <span aria-hidden="true">→</span></button>'
    '<button type="button" class="smore smore--d" id="atlas-smore-d" hidden'
    ' aria-label="More of the machine below">More <span aria-hidden="true">↓</span></button>'
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
.smore{position:fixed;z-index:2;height:30px;padding:0 10px;border:1px solid var(--line);border-radius:15px;background:var(--surface);
color:var(--ink-2);font:500 12px/1 var(--fs);box-shadow:0 1px 6px rgba(0,0,0,.12)}
.smore:hover{color:var(--ink)}
.smore--r{left:calc(var(--sb-x,0px) + var(--sb-w,100%) - 76px);top:calc(var(--sb-y,0px) + var(--sb-h,100%) - 38px)}
.smore--d{left:calc(var(--sb-x,0px) + 8px);top:calc(var(--sb-y,0px) + var(--sb-h,100%) - 38px)}
body:not([data-mode="states"]) .smore{display:none}
body[data-mode="states"] .sboard{display:block}
.snode{cursor:pointer;outline:none;transition:opacity .2s}
.snode rect{fill:var(--card);stroke:var(--ink-3);stroke-width:1;transition:stroke .16s,stroke-width .16s}
.snode .nm{font:600 15px/1 var(--fs);letter-spacing:-.01em;fill:var(--ink);text-anchor:middle}
.snode .gap{font-size:0}
.snode .sy{font:400 10.5px/1 var(--fm);fill:var(--ink-3);text-anchor:middle}
.snode:hover rect,.snode.lit rect{stroke:var(--ink);stroke-width:1.6}
.snode:focus-visible rect{stroke:var(--focus);stroke-width:2.4}
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
.tedge.kf path.wire{stroke:var(--focus);stroke-width:2.6}
.tedge.kf polygon{fill:var(--focus)}
.sfocus .tedge:not(.lit),.sfocus .snode:not(.lit){opacity:.38}
@media (min-width:1181px){body[data-mode="states"] .ask{max-width:290px}}
@media (max-width:720px){.snode .sy{font-size:12px}body[data-mode="states"] .ask__n{display:block;margin-top:4px}}
@media (min-width:721px) and (max-width:1180px){
body[data-mode="states"] .srail{top:calc(var(--ask-b,248px) + 24px);bottom:96px}
}
"""

STATES = r"""
// ---- the States view ---------------------------------------------------------------------
var SM_MAPS = ORDER.filter(function (m) { return m.sm && m.sm.length; });
var SM = {m: null, k: 0, hot: null, pin: null, items: [], scale: 0}, SM_MIN = 0.6, SM_MAX = 1.25;
var SM_CW0 = 290, SM_NW0 = 200, SM_CW = SM_CW0, SM_CH = 170, SM_NW = SM_NW0, SM_NH = 62;
var SRAIL = document.getElementById('atlas-srail'), SRAIL_LIST = document.getElementById('atlas-srail-list');
var SMORE_R = document.getElementById('atlas-smore-r'), SMORE_D = document.getElementById('atlas-smore-d');
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
// The shape of each transition. The transitions between the same two states bend apart: in
// the frame of the pair, the offsets are 30, -30, 60, -60 and so on. A transition in the
// other direction has the opposite sign in its own frame, so a pair in two directions goes to
// two sides. When the straight line between two states goes through a different state, all
// the transitions between the two states go around the states (`aroundShape`): the first at
// the right side of its direction, the second at the other side, and the next ones farther
// out. `bend` is the bend of a line, or `side` and `depth` give a line around the states.
function bendsOf(x, pos) {
  var groups = Object.create(null), out = x.tr.map(function () { return {bend: 0}; });
  x.tr.forEach(function (t, i) {
    if (t.a === t.b) return;
    var key = Math.min(t.a, t.b) + ':' + Math.max(t.a, t.b);
    (groups[key] = groups[key] || []).push(i);
  });
  Object.keys(groups).forEach(function (key) {
    var list = groups[key], t0 = x.tr[list[0]], s0 = t0.a < t0.b ? 1 : -1, around = blocked(x, pos, t0);
    list.forEach(function (i, j) {
      var s = x.tr[i].a < x.tr[i].b ? 1 : -1, side = j % 2 ? -1 : 1, level = 1 + (j >> 1);
      out[i] = around ? {side: side * s * s0, depth: 20 + 60 * level} : {bend: list.length > 1 ? 30 * level * side * s : 0};
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
// The end of a quadratic line from p0 through the control point m to p1: the arrowhead and
// the data of the label (`labelAt`).
function curve(p0, m, p1, n, flat) {
  var tx = p1[0] - m[0], ty = p1[1] - m[1], tl = Math.hypot(tx, ty) || 1;
  tx /= tl; ty /= tl;
  return {d: 'M' + p0[0] + ' ' + p0[1] + 'Q' + m[0] + ' ' + m[1] + ' ' + p1[0] + ' ' + p1[1], tip: [p1[0] + tx * 4, p1[1] + ty * 4], dir: [tx, ty],
    p0: p0, m: m, p1: p1, n: n, flat: flat};
}
// The shape of a transition from the point a to the point b with the bend `bend`, as in the
// study: the line starts and ends at the edge of the two states. The label of a horizontal
// straight line is above the line. The label of a different straight line is at its upper
// side, or at its right side when the line is vertical. The label of a bent line is at the
// outer side of the bend.
function edgeShape(a, b, bend) {
  var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  var m = [(a[0] + b[0]) / 2 - uy * bend, (a[1] + b[1]) / 2 + ux * bend], k = Math.sign(bend);
  // The ends are on the outlines of the two states, toward the control point (`rim`).
  var p0 = rim(a, bend ? m : b, 3), p1 = rim(b, bend ? m : a, 7);
  if (bend) return curve(p0, m, p1, [-uy * k, ux * k], false);
  var up = ux < -1e-9 || (Math.abs(ux) <= 1e-9 && uy < 0) ? -1 : 1;
  return curve(p0, m, p1, [uy * up, -ux * up], Math.abs(uy) < 0.01);
}
// A transition around the states between its two states: it leaves the side of its source
// state that faces the side of the line (`side` 1 is the right side of its direction), near
// the target, and comes into the same side of its target state, near the source. The middle
// of the line is depth / 2 from the boxes of the two states, so that it does not touch a
// state between them.
// The depth grows, first at the side `side` and then at the other side, until the line goes
// through no other state (`clear`). When no depth gives such a line, the line has the first
// depth at `side`. The two ends are on the outlines of the two states, in the direction of
// the control point (`rim`).
function aroundShape(a, b, side, depth, pos) {
  var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  function shape(sd, d) {
    var nx = -uy * sd, ny = ux * sd, m = [(a[0] + b[0]) / 2 + nx * d, (a[1] + b[1]) / 2 + ny * d];
    return curve(rim(a, m, 3), m, rim(b, m, 7), [nx, ny], false);
  }
  for (var n = 0; n < 16; n++) {
    for (var k = 0; k < 2; k++) {
      var sh = shape(k ? -side : side, depth + 40 * n);
      if (clear(sh, pos, a, b)) return sh;
    }
  }
  return shape(side, depth);
}
// The point of the outline of the state at c (a box with round ends) in the direction of the
// point `to`, `gap` farther out. A point that the old rule gave (the middle of the side that
// faces the normal of a diagonal line) is not on the outline: it was up to 60 units from it.
function rim(c, to, gap) {
  var dx = to[0] - c[0], dy = to[1] - c[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
  var r = SM_NH / 2, L = SM_NW / 2 - r, t = Math.abs(uy) > 1e-9 ? r / Math.abs(uy) : Infinity;
  if (Math.abs(ux * t) > L) { var e = Math.sign(ux) * L, bq = ux * e; t = bq + Math.sqrt(bq * bq - e * e + r * r); }
  return [c[0] + ux * (t + gap), c[1] + uy * (t + gap)];
}
// True when the quadratic line of shape sh goes through no state other than its two ends at
// a and b. The box of each state has a margin of 8, as in `blocked`.
function clear(sh, pos, a, b) {
  return pos.every(function (p) {
    if (p === a || p === b) return true;
    for (var n = 1; n < 40; n++) {
      var u = n / 40, v = 1 - u, qx = v * v * sh.p0[0] + 2 * u * v * sh.m[0] + u * u * sh.p1[0], qy = v * v * sh.p0[1] + 2 * u * v * sh.m[1] + u * u * sh.p1[1];
      if (Math.abs(qx - p[0]) < SM_NW / 2 + 8 && Math.abs(qy - p[1]) < SM_NH / 2 + 8) return false;
    }
    return true;
  });
}
// A loop from a state to the same state, above the state.
function loopShape(a) {
  var top = a[1] - SM_NH / 2, at = [a[0], top - 38];
  return {d: 'M' + (a[0] - 22) + ' ' + (top - 3) + 'C' + (a[0] - 34) + ' ' + (top - 56) + ' ' + (a[0] + 34) + ' ' + (top - 56) + ' ' + (a[0] + 22) + ' ' + (top - 7),
    tip: [a[0] + 21, top - 3], dir: [-0.22, 0.98], p0: at, m: at, p1: at, n: [0, -1], flat: true};
}
function arrowPoints(tip, d) {
  var tx = d[0], ty = d[1];
  return [tip[0], tip[1], tip[0] - tx * 9 - ty * 4.2, tip[1] - ty * 9 + tx * 4.2, tip[0] - tx * 9 + ty * 4.2, tip[1] - ty * 9 - tx * 4.2].join(' ');
}
// The label of a transition at the point u of its line (0 at the start, 1 at the end), and
// `extra` farther out. A flat label is 12 above its point. A different label is at the side n
// of the line: 14 to the side or 12 up or down, as in the study.
function labelAt(sh, u, extra) {
  var v = 1 - u, x = v * v * sh.p0[0] + 2 * u * v * sh.m[0] + u * u * sh.p1[0], y = v * v * sh.p0[1] + 2 * u * v * sh.m[1] + u * u * sh.p1[1];
  if (sh.flat) return {x: x, y: y - 12 - extra, cls: null};
  var nx = sh.n[0], ny = sh.n[1];
  return {x: x + nx * (14 + extra), y: y + ny * (12 + extra) + 4, cls: Math.abs(nx) < 0.3 ? null : nx < 0 ? 'end' : 'start'};
}
function setLabel(e, at) {
  e.setAttribute('x', at.x); e.setAttribute('y', at.y);
  if (at.cls) e.setAttribute('class', at.cls); else e.removeAttribute('class');
}
// Put each label, in model order, at the first place that covers no state, no label before
// it and no line: the middle of its line, then nearer to the ends of its line, then farther
// out. When no place is free, the label stays at the middle of its line.
var SM_AT = [0.5, 0.38, 0.62, 0.26, 0.74], SM_OUT = [0, 10, 22, 36];
function placeLabels(pos, items) {
  var edges = items.filter(function (o) { return o.kind === 't'; }), dots = [];
  var boxes = pos.map(function (p) { return [p[0] - SM_NW / 2 - 2, p[1] - SM_NH / 2 - 2, p[0] + SM_NW / 2 + 2, p[1] + SM_NH / 2 + 2]; });
  edges.forEach(function (o) {
    var w = o.look.querySelector('path.wire'), n = w.getTotalLength();
    for (var s = 0; s <= 48; s++) { var q = w.getPointAtLength(n * s / 48); dots.push([q.x, q.y]); }
  });
  var free = function (r) {
    return !boxes.some(function (b) { return r[0] < b[2] && b[0] < r[2] && r[1] < b[3] && b[1] < r[3]; }) &&
      !dots.some(function (d) { return d[0] > r[0] && d[0] < r[2] && d[1] > r[1] && d[1] < r[3]; });
  };
  edges.forEach(function (o) {
    var text = o.look.querySelector('text'), done = false;
    for (var i = 0; i < SM_OUT.length * SM_AT.length && !done; i++) {
      setLabel(text, labelAt(o.shape, SM_AT[i % SM_AT.length], SM_OUT[Math.floor(i / SM_AT.length)]));
      var b = text.getBBox(), r = [b.x - 2, b.y - 1, b.x + b.width + 2, b.y + b.height + 1];
      if (free(r)) { boxes.push(r); done = true; }
    }
    if (!done) setLabel(text, labelAt(o.shape, 0.5, 0));
  });
}

// ---- the board -----------------------------------------------------------------------------
// The free part of the screen: at the right of the list on a wide screen, under the row of
// the list on a phone, and above the reading line.
function smFree() {
  // The bar of a nested map is under the header (`insideSync` in `atlas_inside`).
  var head = insideSync();
  askBottom();
  var top = head + 16, left = 16, bottom = H - (W > WIDE ? 96 : 120);
  if (shownEl(SRAIL)) {
    var r = SRAIL.getBoundingClientRect();
    if (W > WIDE) left = r.right + 14; else top = r.bottom + 10;
  }
  if (W > 1180) top = Math.max(top, head + 24);
  else if (W > WIDE && ASK_EL) top = Math.max(top, ASK_EL.getBoundingClientRect().bottom + 16);
  return {x0: left, y0: top, x1: W - 16, y1: Math.max(top + 1, bottom)};
}
// True when the board does not fit at SM_MIN and the board with the columns as rows gives a
// larger scale: on a phone, the columns then go down the screen.
function smTurn(x, aw, ah) {
  var cols = 1, rows = 1;
  x.st.forEach(function (s) { cols = Math.max(cols, s.c + 1); rows = Math.max(rows, s.r + 1); });
  var fit = function (c, r) { return Math.min((aw - 1) / ((c - 1) * SM_CW + SM_NW + 120), (ah - 1) / ((r - 1) * SM_CH + SM_NH + 120)); };
  return fit(cols, rows) < SM_MIN && fit(rows, cols) > fit(cols, rows);
}
// The width of the states of machine x: SM_NW0, or more when the ID or the symbol of a state
// is wider, so that each ID and symbol shows in full. The columns keep the gap of SM_CW0 and
// SM_NW0 between them. A long ID made the state cut it with "...": the width was a constant.
function smSize(x) {
  // The styles of the ID and the symbol apply inside a state (`.snode`).
  var box = sv('g', {'class': 'snode'}, SWORLD), tx = sv('text', null, box), most = 0;
  x.st.forEach(function (s) {
    [['nm', s.id], ['sy', s.sym ? shortSym(s.sym) : '']].forEach(function (v) {
      if (!v[1]) return;
      var e = sv('tspan', {'class': v[0]}, tx, v[1]);
      most = Math.max(most, e.getComputedTextLength ? e.getComputedTextLength() : 0);
    });
  });
  SWORLD.removeChild(box);
  SM_NW = Math.max(SM_NW0, Math.ceil(most) + 28); SM_CW = SM_NW + SM_CW0 - SM_NW0;
}
function smDraw() {
  if (!SWORLD || !smOn()) return;
  var x = smX(), had = SBOARD.contains(document.activeElement) ? document.activeElement.getAttribute('data-item') : null;
  SWORLD.replaceChildren(); SWORLD.setAttribute('class', ''); SWORLD.removeAttribute('transform');
  SBOARD.setAttribute('aria-label', 'State machine: ' + x.n);
  smSize(x);
  var g = smFree(), aw = Math.max(1, g.x1 - g.x0), ah = Math.max(1, g.y1 - g.y0), turn = smTurn(x, aw, ah);
  [['--sb-x', g.x0], ['--sb-y', g.y0], ['--sb-w', aw], ['--sb-h', ah]].forEach(function (v) { document.body.style.setProperty(v[0], v[1] + 'px'); });
  var pos = x.st.map(function (s) { return [(turn ? s.r : s.c) * SM_CW + SM_NW / 2, (turn ? s.c : s.r) * SM_CH + SM_NH / 2]; }), shapes = bendsOf(x, pos);
  var gE = sv('g', null, SWORLD), gN = sv('g', null, SWORLD), gT = sv('g', null, SWORLD), items = [];
  x.st.forEach(function (s, i) { items.push(smState(x, s, i, pos[i], gN)); });
  x.tr.forEach(function (t, i) { items.push(smEdge(x, t, i, pos, shapes[i], gE, gT)); });
  placeLabels(pos, items);
  // The scale and the place come from the box of the full board, with its labels. When the
  // board with its margins is larger than its part of the screen, the margins become 12 px.
  var bb = SWORLD.getBBox(), k = Math.min(SM_MAX, (aw - 1) / (bb.width + 80), (ah - 1) / (bb.height + 60));
  if (k < SM_MIN) k = Math.max(SM_MIN, Math.min((aw - 24) / bb.width, (ah - 24) / bb.height));
  var tx = Math.max(12, (aw - bb.width * k) / 2), ty = Math.max(12, (ah - bb.height * k) / 2);
  boardSize(SBOARD, SSVG, aw, ah, bb.width * k + 24, bb.height * k + 24, tx * 2 + bb.width * k, ty * 2 + bb.height * k);
  SWORLD.setAttribute('transform', 'translate(' + (tx - bb.x * k) + ' ' + (ty - bb.y * k) + ') scale(' + k + ')');
  SM.scale = k; SM.turn = turn; SM.items = items;
  SBOARD.scrollTo(0, 0);
  smLight(); smMore();
  if (had !== null) { var back = SWORLD.querySelector('[data-item="' + had + '"]'); if (back) back.focus({preventScroll: true}); }
}
// The mark "More" at the bottom right corner of the board shows while a part of the board is
// out of view at the right. The mark at the bottom left corner shows while a part is out of
// view below. A corner is usually empty, because the board is at the middle. A click on a
// mark scrolls the board.
function smMore() {
  var o = SBOARD, gap = 2;
  if (SMORE_R) SMORE_R.hidden = !(smOn() && o.scrollLeft + o.clientWidth < o.scrollWidth - gap);
  if (SMORE_D) SMORE_D.hidden = !(smOn() && o.scrollTop + o.clientHeight < o.scrollHeight - gap);
}
function smScroll(dx, dy) { SBOARD.scrollBy({left: dx * SBOARD.clientWidth * 0.8, top: dy * SBOARD.clientHeight * 0.8, behavior: reduced() ? 'auto' : 'smooth'}); }
if (SBOARD) SBOARD.addEventListener('scroll', smMore, {passive: true});
if (SMORE_R) SMORE_R.addEventListener('click', function (e) { e.stopPropagation(); smScroll(1, 0); });
if (SMORE_D) SMORE_D.addEventListener('click', function (e) { e.stopPropagation(); smScroll(0, 1); });
function smState(x, s, i, p, parent) {
  // The name starts with the visible text: the ID and the short symbol.
  var words = s.id + (s.sym ? ' ' + shortSym(s.sym) : '') + '. State. ' + (s.y || 'The model gives no meaning for this state.') + (s.first ? ' This is the first state.' : '');
  var g = sv('g', {'class': 'snode', tabindex: '0', role: 'button', 'aria-pressed': 'false', 'data-item': 's' + i, 'aria-label': words}, parent);
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
function smEdge(x, t, i, pos, how, below, above) {
  var a = pos[t.a], b = pos[t.b], from = x.st[t.a].id, to = x.st[t.b].id;
  var shape = t.a === t.b ? loopShape(a) : how.depth ? aroundShape(a, b, how.side, how.depth, pos) : edgeShape(a, b, how.bend), label = labelAt(shape, 0.5, 0);
  var look = sv('g', {'class': 'tedge', 'aria-hidden': 'true'}, below);
  sv('path', {d: shape.d, 'class': 'wire'}, look);
  sv('polygon', {points: arrowPoints(shape.tip, shape.dir)}, look);
  sv('text', {x: label.x, y: label.y, 'class': label.cls}, look, t.l);
  var words = 'Transition from ' + from + ' to ' + to + ': ' + t.l + '. ' + (t.c || 'The model gives no cause for this transition.');
  var g = sv('g', {'class': 'tedge', tabindex: '0', role: 'button', 'aria-pressed': 'false', 'data-item': 't' + i, 'aria-label': words}, above);
  sv('path', {d: shape.d, 'class': 'hit'}, g);
  var item = {kind: 't', i: i, g: g, look: look, t: t, bend: how.depth ? how.side * how.depth : how.bend, shape: shape};
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
    o.g.setAttribute('aria-pressed', SM.pin === o ? 'true' : 'false');
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
  // With no light and no keyboard focus in the board, Esc goes out of a nested map (`goOut`).
  if (e.key === 'Escape' && !SM.pin && !SBOARD.contains(document.activeElement) && insideMap()) { goOut(); return true; }
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
  var mark = function (e) { return e && !e.hidden ? e.getBoundingClientRect().toJSON() : null; };
  return {mode: VIEW.mode, map: SM.m ? SM.m.id : null, k: SM.k, id: x ? x.id : null, scale: SM.scale, turn: !!SM.turn, view: view,
    more: [mark(SMORE_R), mark(SMORE_D)], scrollAt: SBOARD ? [SBOARD.scrollLeft, SBOARD.scrollTop] : null,
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
        return {kind: 's', i: o.i, id: o.s.id, label: o.g.getAttribute('aria-label'), pressed: o.g.getAttribute('aria-pressed'), lit: o.g.classList.contains('lit'), opacity: getComputedStyle(o.g).opacity,
          rect: box(r), rx: +r.getAttribute('rx'), h: +r.getAttribute('height'), dot: box(dot), dotLine: box(o.g.querySelector('.sstart-l')),
          texts: Array.prototype.map.call(o.g.querySelectorAll('.nm, .sy'), function (t) { return {text: t.textContent, box: box(t), px: parseFloat(getComputedStyle(t).fontSize) * SM.scale}; })};
      }
      var w = o.look.querySelector('path.wire'), tl = w.getTotalLength(), ctm = w.getScreenCTM(), pts = [];
      for (var s = 0; s <= 16; s++) { var q = w.getPointAtLength(tl * s / 16), sp = new DOMPoint(q.x, q.y).matrixTransform(ctm); pts.push([sp.x, sp.y]); }
      var lt = o.look.querySelector('text');
      return {kind: 't', i: o.i, a: o.t.a, b: o.t.b, l: o.t.l, bend: o.bend, label: o.g.getAttribute('aria-label'), pressed: o.g.getAttribute('aria-pressed'), lit: o.look.classList.contains('lit'),
        opacity: getComputedStyle(o.look).opacity, wire: getComputedStyle(w).stroke, points: pts, text: {text: lt.textContent, box: box(lt), px: parseFloat(getComputedStyle(lt).fontSize) * SM.scale},
        tip: box(o.look.querySelector('polygon'))};
    })};
}
"""
