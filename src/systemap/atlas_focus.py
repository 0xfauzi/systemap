"""The Focus view of the atlas page: the list of the cards, the board, the reach and the keys.

`atlas_script` joins the script of this part after the States part (`atlas_states`). The
rules are the section "The other views: the rules" of docs/design/atlas.md, and the study
(docs/design/atlas/study-script.html, `drawFocus`, `reach` and `rail`):

- The view shows only when a map of the tree has a flow between two of its parts. Then the
  header has the button Focus (`atlas_header`).
- The parts of a map are its cards, but not the neighbours of a nested map (`upCard` in
  `atlas_lit`). A neighbour is a card of the map above. The view of a nested map uses only
  the parts and the flows between two parts: the list, the board, the counts and the
  reach. It does not follow the flows of the map above. Thus a nested map with flows only
  to its neighbours has no Focus view, and the button Focus then shows the map above. The
  counts of a nested map count parts, for example "through flows, a change here can reach
  1 of 1 other part · modules of 0 other parts import modules of this part".
- The headline of a nested map gives the path. A part of the path is a button only when
  that map has the Focus view: the button focuses on the card of that map with the most
  flows. Each other part of the path is text.
- One card is in the middle of the board. The cards that give to it are at its left, and
  the cards that it gives to are at its right, two steps deep: one column for each step.
  A card at two steps has no fill. A line connects two cards in adjacent columns for each
  pair of cards that has a flow (`fcEdges`). The lines of the middle card are thicker than
  the lines between the outer columns.
- A column shows FC_MAX (nine) cards at most, and then the text "+ N more" with the count
  of the other cards of that step.
- The reach (`reachOf`) is the set of the other cards on a path of flows from a card, each
  with its count of steps. A card is not in its own reach, also when a path of flows goes
  back to it (a cycle). The importers are the other cards with a module that imports a
  module of the card directly, one step only (`fcImports`). The page computes them from the
  module imports of the facts that the Uses and Used by lists of the details use. It reads
  no answer. A path of imports with more steps is not counted: on a framework it gets to
  almost each card, and thus it does not inform the reader. The two counts have different
  meanings, thus the page does not add them. The board shows only the flows.
- The headline gives "Focus", the question "What does X use, and what uses X?", and the
  counts: the cards that the card receives from, the cards that it gives to, the reach and
  the importers, for example "through flows, a change here can reach 15 of 36 other cards ·
  modules of 18 other cards import modules of this card". The total is the count of the cards of the map
  less one, as the headline of the Map view counts them (`countWords` in `atlas_view`). On
  a phone the headline also gives the counts.
- The list at the left gives the cards of the map that have a flow, with their count of
  flows, the largest count first. On a narrow screen the list is a row of names under the
  headline. The current card has aria-current "true".
- Selecting a card of the board or of the list focuses on it. The view opens on the card
  with the most flows, or on the card of the details: the details of a card with a flow
  have the button "Focus on this card" (`atlas_details`). The button Focus of the header
  opens the view on the selected card of the Map view, when that card has a flow in the view. After that button and after a
  part of the path, the keyboard focus is on the middle card. The current button of the
  list moves into view (with no smooth scroll when the motion is reduced).
- On a screen of 1180 px or less the view shows one step at each side.
- Pointing at a card or a line, or the keyboard focus on it, lights it and the lines and
  the cards that touch it. The other lines go back. The reading line (`atlas-say`) gives
  the card, its short name and its place, or the two cards of a line with the artifacts
  and the relation sentence of the model. A click or a tap on a line keeps its light. A
  click on the ground, a second click on the same line and Esc remove it.
- The reading line does not cover the board. On a screen of 720 px or less the board is
  at the top of its part of the screen. While the reading line gives a kept line or the
  item of the keyboard focus, the board ends above the reading line and it scrolls
  (`fcFit`).
- The keyboard. Each card and each line is a button: Tab goes through the cards and then
  through the lines. The up and down arrow keys go to the card above and below in the same
  column. The left and right arrow keys go to the nearest card in the adjacent column.
  Home goes to the middle card. Enter and Space on a card focus on it, and the keyboard
  focus goes to the new middle card. Esc removes the light. The map keys do not operate.

The board is SVG, not canvas: it does not zoom (docs/design/atlas.md, "The architecture").
The script makes it with DOM functions (`sv` in `atlas_sequences`) and sets the color of a
kind with the style object (`--k`). It draws the board again at a change of the card and of
the screen size. Its scale is FC_MIN or more. When the board is larger than its part of the
screen at that scale, that part scrolls. While the board shows, the canvas does not show
and draws only the ground (`draw` in `atlas_input`).
"""

from __future__ import annotations

HTML = (
    '<nav class="rail frail" id="atlas-frail" aria-label="Cards">'
    '<div class="rail__list" id="atlas-frail-list"></div></nav>'
    '<div id="atlas-fboard" class="fboard" role="group" aria-label="Focus">'
    '<svg id="atlas-fsvg"><g id="atlas-fworld"></g></svg></div>'
)

# From the study, with the fixed header of the atlas page and the fonts of the product. The
# list has the look of the list of the Sequences view (`.rail` in `atlas_sequences`).
CSS = """
body[data-mode="seq"] .frail{display:none}
body[data-mode="focus"] .frail{display:flex}
body[data-mode="focus"] #canvas{visibility:hidden}
body[data-mode="focus"] .zoom,body[data-mode="focus"] .key,body[data-mode="focus"] .note,body[data-mode="focus"] .tabs{display:none}
.fboard{position:fixed;left:var(--fb-x,0px);top:var(--fb-y,0px);width:var(--fb-w,100%);height:var(--fb-h,100%);display:none;
overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;z-index:1}
.fboard svg{display:block}
body[data-mode="focus"] .fboard{display:block}
.fcard{cursor:pointer;outline:none}
.fcard rect{fill:var(--card);stroke:var(--line-2);stroke-width:1;transition:stroke .16s}
.fcard text{font:600 13px/1 var(--fs);fill:var(--ink);text-anchor:middle;pointer-events:none}
.fcard.far rect{fill:transparent}.fcard.far text{font-weight:500;fill:var(--ink-2)}
.fcard.mid{cursor:default}
.fcard.mid rect{stroke:var(--ink);stroke-width:1.6}
.fcard.mid text{font-size:16px}
.fcard:hover rect,.fcard.lit rect{stroke:var(--ink)}
.fcard:focus-visible rect{stroke:var(--focus);stroke-width:2.4}
.fcol{font:500 9.5px/1 var(--fm);letter-spacing:.1em;text-transform:uppercase;fill:var(--ink-3);text-anchor:middle}
.fmore{font:400 11px/1 var(--fs);fill:var(--ink-3);text-anchor:middle}
.fedge{outline:none;transition:opacity .2s}
.fedge path.wire{fill:none;stroke:var(--wire);stroke-width:1.3;transition:stroke .16s,stroke-width .16s}
.fedge.thin path.wire{stroke-opacity:.55;stroke-width:1}
.fedge polygon{fill:var(--ink-3);transition:fill .16s}
.fedge path.hit{fill:none;stroke:transparent;stroke-width:12;cursor:pointer;pointer-events:stroke}
.fedge.lit path.wire{stroke:var(--k,var(--ink));stroke-opacity:1;stroke-width:2}
.fedge.lit polygon{fill:var(--k,var(--ink))}
.fedge.kf path.wire{stroke:var(--focus);stroke-width:2.6}
.ffocus .fedge:not(.lit){opacity:.38}
.side__body .fgo{margin-top:0}
@media (min-width:1181px){body[data-mode="focus"] .ask{max-width:290px}}
@media (min-width:721px){body[data-mode="focus"] .frail{top:calc(var(--ask-b,248px) + 24px)}}
@media (max-width:720px){body[data-mode="focus"] .ask__n{display:block;margin-top:4px}}
"""

REACH = r"""
// The reach of card `id` along the list of flows `flows`: each card on a path of flows from
// `id`, with its count of steps (1 for a card at the other end of a flow of `id`). With
// `from` 's' and `to` 't' the paths go in the direction of the flows (the cards that a
// change of `id` can reach). With 't' and 's' they go back (the cards that `id` uses). Each
// card has its smallest count of steps. The card `id` is not in its reach, also on a cycle.
function reachOf(flows, id, from, to) {
  var dist = Object.create(null), edge = [id], d = 0;
  while (edge.length) {
    d++;
    var at = Object.create(null), next = [];
    edge.forEach(function (x) { at[x] = true; });
    flows.forEach(function (f) {
      var y = f[to];
      if (at[f[from]] && y !== id && !(y in dist)) { dist[y] = d; next.push(y); }
    });
    edge = next;
  }
  return dist;
}
// The cards of a reach at d steps, in the order of the reach.
function atSteps(dist, d) { return Object.keys(dist).filter(function (k) { return dist[k] === d; }); }
"""

FOCUS = (
    REACH
    + r"""
// ---- the Focus view ----------------------------------------------------------------------
// True for a part of map m: a card of m that is not a neighbour of a nested map.
function fcPart(m, id) { var c = m.byId[id]; return !!c && !upCard(c); }
// The flows of map m between two different parts of m.
function fcFlows(m) {
  if (!m._ff) m._ff = m.flows.filter(function (f) { return f.s !== f.t && fcPart(m, f.s) && fcPart(m, f.t); });
  return m._ff;
}
// The import links of map m between two different parts: {s: A, t: B} when a module of B
// imports a module of A. Thus a change of A can reach B. The page has these imports for the
// Uses and Used by lists of the details (`ownersOf` and `importerIds` in `atlas_details`).
function fcImports(m) {
  if (m._fi) return m._fi;
  var own = ownersOf(m), seen = Object.create(null), out = [];
  (m.md || []).forEach(function (x, j) {
    var a = own[j];
    if (a === undefined || !fcPart(m, a)) return;
    importerIds(m, j).forEach(function (y) {
      var b = typeof y === 'number' ? own[y] : undefined;
      if (b === undefined || b === a || !fcPart(m, b) || seen[a + '|' + b]) return;
      seen[a + '|' + b] = true;
      out.push({s: a, t: b});
    });
  });
  m._fi = out;
  return out;
}
// The count of the parts of map m, and the word for a part.
function fcParts(m) { return m.cards.filter(function (c) { return !upCard(c); }).length; }
function fcNoun(m) { return m.owner ? 'part' : 'card'; }
// The count of flows of each card of map m.
function fcDegree(m) {
  if (m._fd) return m._fd;
  var deg = Object.create(null);
  fcFlows(m).forEach(function (f) { deg[f.s] = (deg[f.s] || 0) + 1; deg[f.t] = (deg[f.t] || 0) + 1; });
  m._fd = deg;
  return deg;
}
var FC_MAPS = ORDER.filter(function (m) { return fcFlows(m).length > 0; });
var FC = {m: null, id: '', hot: null, pin: null, items: [], scale: 0, cols: []}, FC_MIN = 0.6, FC_MAX = 9;
var FRAIL = document.getElementById('atlas-frail'), FRAIL_LIST = document.getElementById('atlas-frail-list'), FRAIL_M = null;
var FBOARD = document.getElementById('atlas-fboard'), FSVG = document.getElementById('atlas-fsvg'), FWORLD = document.getElementById('atlas-fworld');
function fcOn() { return VIEW.mode === 'focus' && !!FC.m; }
function fcCard() { return FC.m ? FC.m.byId[FC.id] || null : null; }
// The cards of map m with a flow, the largest count of flows first, else in model order.
function fcRanked(m) {
  var deg = fcDegree(m);
  return m.cards.filter(function (c) { return deg[c.id]; }).sort(function (a, b) { return deg[b.id] - deg[a.id] || a.i - b.i; });
}
// The reach of card c: `up` gives the cards that c receives from, and `dn` the cards that c
// gives to, each with its count of steps.
function fcReach(c) {
  var memo = c.map._fr || (c.map._fr = Object.create(null));
  if (!memo[c.id]) memo[c.id] = {up: reachOf(fcFlows(c.map), c.id, 't', 's'), dn: reachOf(fcFlows(c.map), c.id, 's', 't')};
  return memo[c.id];
}
// `reach` is the count of the cards on a path of flows from c. `imports` is the count of the
// other cards that import c directly. The two counts have different meanings: the page does
// not add them.
function fcCounts(c) {
  var r = fcReach(c), by = fcImports(c.map).filter(function (x) { return x.s === c.id; }).length;
  return {from: atSteps(r.up, 1).length, to: atSteps(r.dn, 1).length, reach: Object.keys(r.dn).length, imports: by, of: fcParts(c.map) - 1};
}
// The two parts of the reach sentence: the reach through flows and the direct importers.
function fcReachWords(c, n) {
  var w = fcNoun(c.map);
  return ['through flows, a change here can reach ' + n.reach + ' of ' + n.of + ' other ' + w + (n.of === 1 ? '' : 's'),
    'modules of ' + n.imports + ' other ' + w + (n.imports === 1 ? '' : 's') + ' import modules of this ' + w];
}
function fcHead() {
  var c = fcCard(), n = fcCounts(c), r = fcReachWords(c, n);
  return {k: 'Focus', q: 'What does ' + c.id + ' use, and what uses ' + c.id + '?',
    n: 'receives from ' + n.from + ' · gives to ' + n.to + ' · ' + r[0] + ' · ' + r[1]};
}
function fcWords() {
  var c = fcCard(), n = fcCounts(c), r = fcReachWords(c, n);
  var w = fcNoun(c.map);
  return 'Focus on ' + c.id + '. It receives from ' + counted(n.from, w) + ' and gives to ' + counted(n.to, w) +
    '. T' + r[0].slice(1) + '. M' + r[1].slice(1) + '. Map: ' + mapName(c.map) + '.';
}

// ---- the list ----------------------------------------------------------------------------
function fcRailWrite() {
  if (!FRAIL_LIST || FRAIL_M === FC.m) return;
  var m = FC.m, deg = fcDegree(m), out = FC_MAPS.length > 1 ? [el('p', {'class': 'rail__g'}, mapName(m))] : [];
  FRAIL_M = m;
  fcRanked(m).forEach(function (c) {
    var b = el('button', {type: 'button', 'data-card': c.id, 'aria-current': 'false'}, el('span', null, c.id), el('i', {'aria-hidden': 'true'}, String(deg[c.id])),
      el('span', {'class': 'sr-only'}, ', ' + counted(deg[c.id], 'flow')));
    b.addEventListener('click', function () { fcChoose(m, c.id); });
    out.push(b);
  });
  FRAIL_LIST.replaceChildren.apply(FRAIL_LIST, out);
}
function fcRailSync() {
  if (!FRAIL_LIST) return;
  fcRailWrite();
  var cur = null;
  Array.prototype.forEach.call(FRAIL_LIST.querySelectorAll('button'), function (b) {
    var on = b.getAttribute('data-card') === FC.id;
    b.setAttribute('aria-current', on ? 'true' : 'false');
    if (on) cur = b;
  });
  if (cur) fcRailShow(cur);
}
// Move the button b of the list into view. The list scrolls down on a wide screen, and the
// row of the list scrolls to the side on a narrow screen.
function fcRailShow(b) {
  [FRAIL_LIST, FRAIL].forEach(function (box) {
    var o = box.getBoundingClientRect(), r = b.getBoundingClientRect(), dx = 0, dy = 0;
    if (box.scrollHeight > box.clientHeight + 1) dy = r.top < o.top ? r.top - o.top - 8 : r.bottom > o.bottom ? r.bottom - o.bottom + 8 : 0;
    if (box.scrollWidth > box.clientWidth + 1) dx = r.left < o.left ? r.left - o.left - 8 : r.right > o.right ? r.right - o.right + 8 : 0;
    if (dx || dy) box.scrollBy({left: dx, top: dy, behavior: reduced() ? 'auto' : 'smooth'});
  });
}
// Focus on card `id` of map m. `keyed` gives the keyboard focus to the new middle card.
function fcChoose(m, id, keyed) {
  if (!fcPart(m, id)) return;
  FC.m = m; FC.id = id; FC.hot = null; FC.pin = null;
  fcRailSync(); headSync(true); fcDraw(keyed); fcSay();
  say(fcWords());
}
// Show the view (`setMode` in `atlas_sequences`): the card of the details (`fcEnter`), else
// the selected card `sel` of the Map view when it has a flow in the view, else the card on
// show in the current map, else the card with the most flows of the current map, else of
// the map on show before, else of the first map with flows. The card of the details gets
// the keyboard focus. Before, the button Focus of the header did not use the selected card,
// and the view showed the card with the most flows.
function fcShow(c, sel) {
  var pick = c || (sel && fcDegree(sel.map)[sel.id] ? sel : null), m = pick ? pick.map : currentMap();
  if (FC_MAPS.indexOf(m) < 0) m = FC.m || FC_MAPS[0];
  var id = pick && pick.map === m ? pick.id : FC.m === m && FC.id ? FC.id : fcRanked(m)[0].id;
  cv.tabIndex = -1; SAID_KEY = '';
  fcChoose(m, id, !!c);
}
// The button "Focus on this card" of the details.
function fcEnter(c) {
  if (VIEW.mode === 'focus') fcChoose(c.map, c.id, true); else { FC_FROM = c; setMode('focus'); }
}
// The action of the part of the path of the headline for map x (`pathButtons` in
// `atlas_view`): focus on the card of x with the most flows. Null when x has no Focus view.
function fcPathGo(x) {
  return FC_MAPS.indexOf(x) < 0 ? null : function () { fcChoose(x, FC.m === x ? FC.id : fcRanked(x)[0].id, true); };
}
var FC_FROM = null;
function fcHide() { FC.hot = null; FC.pin = null; if (SAY) { SAY.classList.remove('on'); SAY.replaceChildren(); } SAID_KEY = ''; }

// ---- the board -----------------------------------------------------------------------------
// The free part of the screen: at the right of the list on a wide screen, under the row of
// the list on a phone, and above the reading line.
function fcFree() {
  // The bar of a nested map is under the header (`insideSync` in `atlas_inside`).
  var head = insideSync();
  askBottom();
  var top = head + 16, left = 16, bottom = H - (W > WIDE ? 70 : 84);
  if (shownEl(FRAIL)) {
    var r = FRAIL.getBoundingClientRect();
    if (W > WIDE) left = r.right + 14; else top = r.bottom + 10;
  }
  if (W > 1180) top = Math.max(top, head + 24);
  else if (W > WIDE && ASK_EL) top = Math.max(top, ASK_EL.getBoundingClientRect().bottom + 16);
  return {x0: left, y0: top, x1: W - 16, y1: Math.max(top + 1, bottom)};
}
// The columns of the board: j is -2 to 2, without 0. Each column has its cards (nine at
// most) and the count of the other cards of its step. A screen of 1180 px or less shows
// one step at each side.
function fcColumns(c) {
  var r = fcReach(c), two = W > 1180;
  return [[-2, r.up, 2, 'Two steps before'], [-1, r.up, 1, 'Gives to ' + c.id], [1, r.dn, 1, c.id + ' gives to'], [2, r.dn, 2, 'Two steps after']].map(function (d) {
    var ids = atSteps(d[1], d[2]);
    return {j: d[0], ids: ids.slice(0, FC_MAX), more: Math.max(0, ids.length - FC_MAX), name: d[3]};
  }).filter(function (col) { return col.ids.length && (two || Math.abs(col.j) === 1); });
}
function fcDraw(keyed) {
  if (!FWORLD || !fcOn()) return;
  var c = fcCard(), m = FC.m, phone = W <= WIDE, had = FBOARD.contains(document.activeElement) ? document.activeElement.getAttribute('data-item') : null;
  FWORLD.replaceChildren(); FWORLD.setAttribute('class', ''); FWORLD.removeAttribute('transform');
  FBOARD.setAttribute('aria-label', 'Focus on ' + c.id);
  var g = fcFree(), aw = Math.max(1, g.x1 - g.x0), ah = Math.max(1, g.y1 - g.y0);
  [['--fb-x', g.x0], ['--fb-y', g.y0], ['--fb-w', aw], ['--fb-h', ah]].forEach(function (v) { document.body.style.setProperty(v[0], v[1] + 'px'); });
  var CW = phone ? 198 : 250, NW = phone ? 144 : 168, NH = 40, RH = 52, cols = fcColumns(c);
  var rows = Math.max.apply(null, cols.map(function (col) { return col.ids.length + (col.more ? 1 : 0); }).concat([1]));
  var gE = sv('g', null, FWORLD), gN = sv('g', null, FWORLD), gH = sv('g', null, FWORLD), at = Object.create(null), items = [];
  var pos = function (j, i, n) { return [j * CW, (i - (n - 1) / 2) * RH]; };
  var add = function (key, id, p, j, i) {
    var it = fcNode(m.byId[id], key, p, j, i, j === 0 ? NW + 24 : NW, j === 0 ? NH + 10 : NH, gN);
    at[key] = it; items.push(it);
  };
  add('0', c.id, [0, 0], 0, 0);
  cols.forEach(function (col) {
    var n = col.ids.length + (col.more ? 1 : 0);
    sv('text', {x: col.j * CW, y: -(rows * RH) / 2 - 14, 'class': 'fcol'}, FWORLD, col.name);
    col.ids.forEach(function (id, i) { add(col.j + ':' + id, id, pos(col.j, i, n), col.j, i); });
    if (col.more) { var p = pos(col.j, n - 1, n); sv('text', {x: p[0], y: p[1] + 4, 'class': 'fmore'}, FWORLD, '+ ' + col.more + ' more'); }
  });
  fcEdges(m, at, gE, gH).forEach(function (e) { items.push(e); });
  var bb = FWORLD.getBBox(), k = Math.min(1.2, (aw - 1) / (bb.width + 40), (ah - 1) / (bb.height + 40));
  if (k < FC_MIN) k = Math.max(FC_MIN, Math.min((aw - 24) / bb.width, (ah - 24) / bb.height));
  var tx = Math.max(12, (aw - bb.width * k) / 2), ty = phone ? 12 : Math.max(12, (ah - bb.height * k) / 2);
  boardSize(FBOARD, FSVG, aw, ah, bb.width * k + 24, bb.height * k + 24, tx * 2 + bb.width * k, ty * 2 + bb.height * k);
  FWORLD.setAttribute('transform', 'translate(' + (tx - bb.x * k) + ' ' + (ty - bb.y * k) + ') scale(' + k + ')');
  FC.scale = k; FC.items = items; FC.cols = cols; FC.free = g;
  FBOARD.scrollTo(0, 0);
  fcLight();
  var back = keyed ? 'n0' : had, e = back === null ? null : FWORLD.querySelector('[data-item="' + back + '"]');
  if (e) e.focus({preventScroll: true});
  fcFit();
}
// The board ends above the reading line while the reading line gives a kept line or the item
// of the keyboard focus. Then the item of the keyboard focus moves into the board.
function fcFit() {
  var g = FC.free;
  if (!g || !SAY) return;
  var h = g.y1 - g.y0, a = document.activeElement, keyed = FBOARD.contains(a) && a !== FBOARD;
  if (SAY.classList.contains('on') && (FC.pin || keyed)) {
    var top = H - parseFloat(getComputedStyle(SAY).bottom) - SAY.offsetHeight;
    h = Math.max(80, Math.min(h, top - 8 - g.y0));
  }
  document.body.style.setProperty('--fb-h', h + 'px');
  if (!keyed) return;
  var o = FBOARD.getBoundingClientRect(), r = a.getBoundingClientRect();
  if (r.bottom > o.bottom) FBOARD.scrollTop += r.bottom - o.bottom + 8;
  else if (r.top < o.top) FBOARD.scrollTop -= o.top - r.top + 8;
}
// The words of the place of the card at column j for the card c in the middle.
function fcPlace(j, c) {
  return j === 0 ? 'The card in focus' : j === -1 ? 'Gives to ' + c.id : j === 1 ? c.id + ' gives to it' : j === -2 ? 'Two steps before ' + c.id : 'Two steps after ' + c.id;
}
function fcNode(card, key, p, j, i, w, h, parent) {
  var mid = j === 0, words = card.id + '. ' + fcPlace(j, fcCard()) + '.' + (mid ? '' : ' Select to focus on it.');
  var g = sv('g', {'class': 'fcard' + (mid ? ' mid' : Math.abs(j) === 2 ? ' far' : ''), tabindex: '0', role: 'button', 'data-item': 'n' + key,
    'aria-label': words, 'aria-current': mid ? 'true' : null}, parent);
  var round = card.k === 'actor';
  if (mid) sv('rect', {x: p[0] - w / 2 - 4, y: p[1] - h / 2 - 4, width: w + 8, height: h + 8, rx: round ? h / 2 + 4 : 13}, g);
  sv('rect', {x: p[0] - w / 2, y: p[1] - h / 2, width: w, height: h, rx: round ? h / 2 : 9}, g);
  fitText(sv('text', {x: p[0], y: p[1] + (mid ? 5.5 : 4.5)}, g, card.id), w - 20);
  var item = {kind: 'n', key: key, id: card.id, card: card, j: j, i: i, p: p, w: w, g: g};
  fcWire(item, g);
  return item;
}
// One line for each pair of cards in adjacent columns that has a flow. The line has the color
// of the kind of its first flow, and the words of all its flows.
function fcEdges(m, at, below, above) {
  var by = Object.create(null), out = [];
  fcFlows(m).forEach(function (f) {
    [[-2, -1], [-1, 0], [0, 1], [1, 2]].forEach(function (pair) {
      var ka = pair[0] === 0 ? '0' : pair[0] + ':' + f.s, kb = pair[1] === 0 ? '0' : pair[1] + ':' + f.t, a = at[ka], b = at[kb];
      if (!a || !b || a.id !== f.s || b.id !== f.t) return;
      var key = ka + '>' + kb;
      if (by[key]) { by[key].flows.push(f); return; }
      by[key] = {kind: 'e', a: ka, b: kb, flows: [f], near: pair[0] === 0 || pair[1] === 0, pa: a, pb: b};
      out.push(by[key]);
    });
  });
  out.forEach(function (e, i) { fcEdge(e, i, below, above); });
  return out;
}
function fcEdge(e, i, below, above) {
  var a = e.pa, b = e.pb, f = e.flows[0], p0 = [a.p[0] + a.w / 2 + 3, a.p[1]], p1 = [b.p[0] - b.w / 2 - 9, b.p[1]], dx = (p1[0] - p0[0]) * 0.5;
  var d = 'M' + p0[0] + ' ' + p0[1] + 'C' + (p0[0] + dx) + ' ' + p0[1] + ' ' + (p1[0] - dx) + ' ' + p1[1] + ' ' + p1[0] + ' ' + p1[1];
  var look = sv('g', {'class': 'fedge' + (e.near ? '' : ' thin'), 'aria-hidden': 'true'}, below);
  look.style.setProperty('--k', 'var(' + (KIND[f.k] || '--ink-2') + ')');
  sv('path', {d: d, 'class': 'wire'}, look);
  sv('polygon', {points: [p1[0] + 7, p1[1], p1[0] - 1, p1[1] - 4, p1[0] - 1, p1[1] + 4].join(' ')}, look);
  var words = 'Flow from ' + f.s + ' to ' + f.t + ': ' + e.flows.map(function (x) { return x.a; }).join(', ') + '.';
  var g = sv('g', {'class': 'fedge', tabindex: '0', role: 'button', 'aria-pressed': 'false', 'data-item': 'e' + i, 'aria-label': words}, above);
  sv('path', {d: d, 'class': 'hit'}, g);
  e.i = i; e.g = g; e.look = look;
  fcWire(e, g);
}
function fcWire(item, g) {
  g.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') fcPoint(item); });
  g.addEventListener('pointerleave', function () { if (FC.hot === item) fcPoint(null); });
  // A focus from a pointer gives no light: the pointer gives it (`pointerenter`).
  g.addEventListener('focus', function () { if (!g.matches(':focus-visible')) return; if (item.look) item.look.classList.add('kf'); fcPoint(item); });
  g.addEventListener('blur', function () { if (item.look) item.look.classList.remove('kf'); if (FC.hot === item) fcPoint(null); });
  g.addEventListener('click', function (e) { e.stopPropagation(); fcAct(item, false); });
  g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fcAct(item, true); } });
}
// A card of the board: focus on it. A line: keep its light, or remove it.
function fcAct(item, keyed) {
  if (item.kind === 'n') { if (item.j !== 0) fcChoose(FC.m, item.id, keyed); return; }
  FC.pin = FC.pin === item ? null : item; fcLight(); fcSay();
}
function fcPoint(item) { FC.hot = item; fcLight(); fcSay(); }
function fcItem() { return FC.hot || FC.pin; }
// Light the item and the items that touch it: a card, its lines and the cards at their
// other ends; a line and its two cards.
function fcLight() {
  var it = fcItem(), keys = Object.create(null), lines = [];
  if (it && it.kind === 'n') {
    keys[it.key] = true;
    FC.items.forEach(function (o) { if (o.kind === 'e' && (o.a === it.key || o.b === it.key)) { lines.push(o); keys[o.a] = true; keys[o.b] = true; } });
  } else if (it) { lines.push(it); keys[it.a] = true; keys[it.b] = true; }
  FWORLD.setAttribute('class', lines.length ? 'ffocus' : '');
  FC.items.forEach(function (o) {
    var on = o.kind === 'n' ? !!keys[o.key] : lines.indexOf(o) >= 0;
    o.g.classList.toggle('lit', on);
    if (o.look) { o.look.classList.toggle('lit', on); o.g.setAttribute('aria-pressed', FC.pin === o ? 'true' : 'false'); }
  });
}
function fcSay() {
  if (!SAY) return;
  var it = fcItem(), c = fcCard();
  SAID_KEY = '';
  if (!it || !c) { SAY.classList.remove('on'); SAY.replaceChildren(); fcFit(); return; }
  var parts;
  if (it.kind === 'n') {
    parts = [el('span', {'class': 'sr-only'}, 'Card '), el('b', null, it.id), el('span', null, (it.card.p ? it.card.p + ' · ' : '') + fcPlace(it.j, c) + (it.j === 0 ? '' : ' · select to focus on it'))];
  } else {
    var f = it.flows[0];
    parts = [el('span', {'class': 'sr-only'}, 'Flow '), el('b', null, f.s, el('span', {'class': 'arr', 'aria-hidden': 'true'}, '→'), el('span', {'class': 'sr-only'}, ' to '), f.t)];
    it.flows.forEach(function (x) { var code = el('code', null, x.a); code.style.setProperty('--k', 'var(' + (KIND[x.k] || '--ink-2') + ')'); parts.push(code); });
    if (it.flows.length === 1 && f.y) parts.push(el('span', null, f.y));
  }
  SAY.replaceChildren.apply(SAY, parts);
  SAY.classList.add('on');
  fcFit();
}
// A click on the ground (not on an item, a control or the reading line) removes the kept light.
document.addEventListener('click', function (e) {
  if (VIEW.mode === 'focus' && FC.pin && !(e.target.closest && e.target.closest('button, a, input, #atlas-say'))) { FC.pin = null; fcLight(); fcSay(); }
});
// The headline changes its text a short time after a choice (`headSync`). When its new height
// moves the free part of the screen, the board is made again. A different part of the page can
// read the new bottom of the headline first (`askBottom`), so this compares the free part.
if (window.ResizeObserver && ASK_BOX) new ResizeObserver(function () {
  if (!fcOn()) return;
  var g = fcFree();
  if (!FC.free || Math.abs(g.x0 - FC.free.x0) > 0.5 || Math.abs(g.y0 - FC.free.y0) > 0.5) fcDraw();
}).observe(ASK_BOX);

// ---- the keys ------------------------------------------------------------------------------
var FC_KEYS = {ArrowLeft: true, ArrowUp: true, ArrowRight: true, ArrowDown: true, Home: true, Escape: true};
// The card that the key `key` goes to from the card `from` (null: the middle card).
function fcNext(from, key) {
  var cards = FC.items.filter(function (o) { return o.kind === 'n'; }), mid = cards[0];
  if (!from || key === 'Home') return mid;
  if (key === 'ArrowUp' || key === 'ArrowDown') {
    var d = key === 'ArrowUp' ? -1 : 1;
    return cards.filter(function (o) { return o.j === from.j && o.i === from.i + d; })[0] || from;
  }
  var js = [0].concat(FC.cols.map(function (col) { return col.j; })).sort(function (a, b) { return a - b; });
  var to = js[js.indexOf(from.j) + (key === 'ArrowLeft' ? -1 : 1)];
  if (to === undefined) return from;
  return cards.filter(function (o) { return o.j === to; }).sort(function (a, b) { return Math.abs(a.p[1] - from.p[1]) - Math.abs(b.p[1] - from.p[1]); })[0] || from;
}
// The keys of the view (`atlas_input`): give true for a key of the view.
function fcKey(e) {
  if (VIEW.mode !== 'focus' || !(e.key in FC_KEYS) || !FC.items.length) return false;
  // With no light and no keyboard focus in the board, Esc goes out of a nested map (`goOut`).
  if (e.key === 'Escape' && !FC.pin && !FBOARD.contains(document.activeElement) && insideMap()) { goOut(); return true; }
  if (e.key === 'Escape') { FC.pin = null; if (FBOARD.contains(document.activeElement)) document.activeElement.blur(); fcPoint(null); return true; }
  var from = null;
  FC.items.forEach(function (o) { if (o.kind === 'n' && o.g === document.activeElement) from = o; });
  fcNext(from, e.key).g.focus();
  return true;
}
// The state of the view for the tests.
function fcState() {
  var c = fcCard(), box = function (e) { return e ? e.getBoundingClientRect().toJSON() : null; };
  return {mode: VIEW.mode, map: FC.m ? FC.m.id : null, id: FC.id, scale: FC.scale, on: fcOn() && !!FBOARD && getComputedStyle(FBOARD).display !== 'none',
    view: box(FBOARD), scroll: FBOARD ? [FBOARD.scrollWidth, FBOARD.scrollHeight, FBOARD.clientWidth, FBOARD.clientHeight] : null,
    counts: c ? fcCounts(c) : null, cls: FWORLD ? FWORLD.getAttribute('class') : '', pin: FC.pin ? 'e' + FC.pin.i : null,
    active: document.activeElement ? document.activeElement.getAttribute('data-item') : null,
    rail: FRAIL_LIST ? Array.prototype.map.call(FRAIL_LIST.querySelectorAll('button'), function (b) { return {id: b.getAttribute('data-card'), text: b.textContent, on: b.getAttribute('aria-current') === 'true'}; }) : [],
    railBox: box(FRAIL), listBox: box(FRAIL_LIST), cur: box(FRAIL_LIST ? FRAIL_LIST.querySelector('[aria-current="true"]') : null), sayBox: box(SAY),
    label: FBOARD ? FBOARD.getAttribute('aria-label') : null,
    cols: FWORLD ? Array.prototype.map.call(FWORLD.querySelectorAll('.fcol'), function (t) { return {text: t.textContent, box: box(t)}; }) : [],
    more: FWORLD ? Array.prototype.map.call(FWORLD.querySelectorAll('.fmore'), function (t) { return {text: t.textContent, box: box(t)}; }) : [],
    items: FC.items.map(function (o) {
      if (o.kind === 'n') {
        var t = o.g.querySelector('text');
        return {kind: 'n', key: o.key, id: o.id, j: o.j, i: o.i, cls: o.g.getAttribute('class'), label: o.g.getAttribute('aria-label'), current: o.g.getAttribute('aria-current'), lit: o.g.classList.contains('lit'),
          rect: box(o.g.querySelector('rect:last-of-type')), text: {text: t.textContent, box: box(t), px: parseFloat(getComputedStyle(t).fontSize) * FC.scale}};
      }
      return {kind: 'e', i: o.i, a: o.a, b: o.b, s: o.flows[0].s, t: o.flows[0].t, n: o.flows.length, near: o.near, label: o.g.getAttribute('aria-label'),
        lit: o.look.classList.contains('lit'), pressed: o.g.getAttribute('aria-pressed'), opacity: getComputedStyle(o.look).opacity,
        wire: getComputedStyle(o.look.querySelector('path.wire')).stroke, box: box(o.look.querySelector('path.wire'))};
    })};
}
"""
)
