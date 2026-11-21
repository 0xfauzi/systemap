"""The details part of the atlas page: the selected card, the reading line and Reduce motion.

`atlas_script` joins the script of this part after the keyboard part (`atlas_keys`). The
rules are the section "Map view: the rules" of docs/design/atlas.md:

- Selecting a card. A click, a tap or Enter selects a card. The details open at the side,
  and the map moves to keep its full frame in view (`sideRight` in the fit of
  `atlas_input`). On a phone (720 px or less), the details are a sheet at the bottom, and
  the selected card goes to the part of the screen above the sheet (`showAbove`). While the
  sheet is open, the headline does not show, because the map goes under it. A click
  with a mouse opens the details after OPEN_MS ms, so that a double-click goes into a
  card and opens no details. With reduced motion, they open at once, except for a card that
  opens a map: it keeps the wait, because the camera goes to the selection at once, and the
  second click of a double-click would land on the details.
  After Enter, the keyboard focus goes to the heading of the details. A selection hides
  the help note at the bottom left, as a pointer on the map does (`atlas_lit`).
- The details keep the content of the canvas page (`page_canvas_details`): the kind, the
  short name, the assurance level and the freshness (under the name in the words of the
  study, for example "Claims examined against the source, current": `claimWords`), the description, the note, the flows
  in and out with the evidence state and the relation sentence, the sequences that use the
  card, the source modules, the source records and the rules of the map (invariants and
  import rules). The flows are the flows of the layer of the map. The details give the count
  of the flows in other layers, with a button that shows all layers.
- The "Uses" and "Used by" lists of a card that is not an actor: one row for each other
  card that a module of this card imports, and for each other card with a module that
  imports a module of this card. The page calculates them from the page data of the
  Details panel (`sr.mo`, `md[].im`, `importers`) and the flows of the map. It reads no
  answer. A row tells the first flow between the two cards, or "no flow". The rows with no
  flow come first, then the rows with the most importing modules. The list shows
  USES_SHOWN rows and a button that shows all. A click on a row selects the card. The lists
  include imports for type checks, and the text below each list says it.
- Each flow row lights its flow on the map (`point` in `atlas_lit`). A click on a row
  selects the card at its other end. A neighbour of a nested map goes out to its card.
- A card that opens a map has a button that goes into that map. A card with a flow has the
  button "Focus on this card", which shows the card in the Focus view (`atlas_focus`).
- Esc and the Close button close the details. The keyboard focus goes back to the card.

The script writes the details with DOM functions (`el` in `atlas_tree`), not with HTML
text. Thus no text of the page data goes to an HTML parser. The details change only at a
change of the selected card or of the layer (`sideSync`).

The reading line (`atlas-say`) is a polite live region at the bottom of the map
(`speak` in `atlas_lit`). It is one line of text: a long last part ends with an ellipsis on
the screen, and a screen reader gets the full text. While the details are open at the side,
the reading line is in the middle of the part of the screen at the left of the details,
clear of the zoom control. While the reading line shows, the key does not show, because
the reading line can cover it. The Reduce motion button of the header sets
`data-reduce-motion` and keeps the setting with the key of the linked page
(`page.MOTION_KEY`). The setting of the device for reduced motion also applies.
"""

from __future__ import annotations

import json

from systemap import page
from systemap.evidence import READER_TEXT

_CLOSE = (
    '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
    '<path d="M2 2l8 8M10 2l-8 8" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'
)

HTML = (
    '<aside class="side" id="atlas-side" aria-label="Details" hidden>'
    '<div class="side__head"><div class="side__k"><span id="atlas-side-k"></span>'
    '<button type="button" id="atlas-side-x" aria-label="Close the details" '
    f'title="Close (Esc)">{_CLOSE}</button></div>'
    '<h2 id="atlas-side-h" tabindex="-1"></h2><div class="side__p" id="atlas-side-p"></div>'
    '<div class="side__state" id="atlas-side-s"></div></div>'
    '<div class="side__body" id="atlas-side-b"></div></aside>'
    '<div class="say" id="atlas-say" aria-live="polite"></div>'
)

CSS = """
.say{position:fixed;left:50%;bottom:max(22px,env(safe-area-inset-bottom,0px));transform:translate(-50%,6px);
max-width:min(760px,calc(100% - 32px));box-sizing:border-box;display:flex;align-items:baseline;gap:10px;flex-wrap:nowrap;
white-space:nowrap;justify-content:center;padding:10px 16px;border-radius:12px;background:var(--surface);border:1px solid var(--line);
box-shadow:var(--shadow);opacity:0;pointer-events:none;transition:opacity .14s,transform .14s;text-align:center;z-index:2}
.say.on{opacity:1;transform:translate(-50%,0)}
.say b{font:600 13px/1.3 var(--fs);letter-spacing:-.01em;white-space:nowrap}
.say .arr{color:var(--ink-3);margin:0 4px}
.say code{font:500 11px/1 var(--fm);padding:3px 6px;border-radius:5px;background:var(--tint);border:1px solid var(--line);white-space:nowrap}
.say code::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px;background:var(--k,var(--wire));vertical-align:1px}
.say span{color:var(--ink-2);min-width:0}
.say>span:last-child{overflow:hidden;text-overflow:ellipsis;flex:0 1 auto}
.say b,.say code{flex:none}
.note{transition:opacity .2s}.note.gone{opacity:0}
.bar__end{margin-left:auto;display:flex;align-items:center;gap:4px;flex:none}
.tool{display:grid;place-items:center;width:32px;height:32px;border-radius:8px;color:var(--ink-3)}
.tool:hover{background:var(--tint);color:var(--ink)}
.tool[aria-pressed="true"]{color:var(--ink);background:var(--tint)}
.side{position:fixed;top:48px;right:0;bottom:0;z-index:3;width:380px;max-width:100%;box-sizing:border-box;
background:var(--surface);border-left:1px solid var(--line);box-shadow:var(--shadow);transform:translateX(102%);
transition:transform .26s cubic-bezier(.2,.8,.2,1);display:flex;flex-direction:column;min-width:0}
.side.on{transform:none}
.side[hidden]{display:none}
.side__head{padding:20px 22px 16px;border-bottom:1px solid var(--line);display:grid;gap:6px}
.side__k{display:flex;align-items:center;gap:8px;font:500 10.5px/1 var(--fm);letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3)}
.side__k button{margin-left:auto;width:26px;height:26px;border-radius:7px;display:grid;place-items:center;color:var(--ink-2)}
.side__k button:hover{background:var(--tint);color:var(--ink)}
.side h2{margin:0;font:600 21px/1.2 var(--fs);letter-spacing:-.02em;overflow-wrap:anywhere;outline:none}
.side__p{color:var(--ink-2)}
.side__state{display:flex;gap:6px;align-items:center;color:var(--ink-3);font-size:11.5px;margin-top:2px}
.side__state:empty{display:none}
.side__state i{width:7px;height:7px;border-radius:50%;background:var(--data)}
.side__state i.no{background:var(--line-2)}
.side__body{overflow:auto;padding:16px 22px 28px;display:grid;gap:22px;align-content:start;grid-auto-rows:max-content;min-height:0;overscroll-behavior:contain;
scrollbar-width:thin;scrollbar-color:var(--line-2) transparent}
.side__d{margin:0;color:var(--ink-2);max-width:62ch}
.side__d.clip{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.side p{margin:0}
.more{color:var(--ink-3);font-size:12px;text-decoration:underline;text-underline-offset:3px;justify-self:start;margin-top:-16px}
.more:hover{color:var(--ink)}
.side__body>.more:first-child,.sec .more{margin-top:0}
.sec .more+.side__d{margin-top:8px}
.enter{justify-self:start;display:inline-flex;align-items:center;gap:8px;height:34px;padding:0 14px;border-radius:9px;
background:var(--ink);color:var(--surface);font:600 12.5px/1 var(--fs);transition:transform .12s}
.enter:hover{transform:translateY(-1px)}
.enter svg{display:block}
.sec h3{margin:0 0 6px;display:flex;justify-content:space-between;font:500 10.5px/1 var(--fm);letter-spacing:.09em;
text-transform:uppercase;color:var(--ink-3)}
.sec h3 span{font-variant-numeric:tabular-nums}
.sec ul{margin:0;padding:0;list-style:none}
.sec li{margin:0 0 4px;color:var(--ink-2)}
.sec li b{color:var(--ink);font-weight:600}
.row{display:grid;grid-template-columns:14px minmax(0,1fr);gap:2px 10px;width:calc(100% + 16px);box-sizing:border-box;
text-align:left;padding:9px 8px;margin:0 -8px;border-radius:8px;transition:background .12s}
.row:hover,.row:focus-visible,.row.on{background:var(--tint)}
.row i{grid-row:1/4;width:10px;height:2px;border-radius:2px;background:var(--k);margin-top:9px}
.row b{font:600 13px/1.35 var(--fs);letter-spacing:-.01em;overflow-wrap:anywhere}
.row b em{font-style:normal;font-weight:400;color:var(--ink-3)}
.row small{font-size:12px;color:var(--ink-2);line-height:1.45}
.row small.ev{color:var(--ink-3)}
.row[hidden]{display:none}
.mods{display:flex;flex-wrap:wrap;gap:5px}
.mods code,.side .rec code{font:400 10.5px/1.4 var(--fm);padding:3px 6px;border-radius:5px;border:1px solid var(--line);
color:var(--ink-2);overflow-wrap:anywhere}
.side details{color:var(--ink-2)}
.side details p{margin:6px 0}
.side details details{margin-left:12px}
.side summary{min-height:28px;padding:4px 0;cursor:pointer;color:var(--ink-2)}
.side summary:hover{color:var(--ink)}
.side .as{color:var(--ink-3)}
body.open .key{right:400px}
@media (min-width:721px){body.open .say{left:calc((100% - 380px) / 2);max-width:min(760px,calc(100% - 692px))}}
body:has(#atlas-say.on) .key{visibility:hidden}
@media (max-width:720px){
.side{top:auto;height:62%;width:100%;border-left:0;border-top:1px solid var(--line);border-radius:16px 16px 0 0;transform:translateY(104%)}
.say{bottom:max(60px,env(safe-area-inset-bottom,0px))}
body.open .say{bottom:calc(62% + 12px)}
body.open .ask{visibility:hidden}
}
@media (pointer:coarse){.tool,.side__k button{width:44px;height:44px}.row{min-height:44px}.side summary{min-height:44px}}
"""

# The words for each evidence state of a flow (`evidence.READER_TEXT`).
_EVIDENCE = json.dumps(READER_TEXT, sort_keys=True)

_ENTER = "M1.5 4.5v-3h3M11.5 8.5v3h-3M8 1.5h3.5V5M5 11.5H1.5V8"  # the icon of the study

DETAILS = r"""
// ---- the details of the selected card ---------------------------------------------------
var SIDE = document.getElementById('atlas-side'), SIDE_B = document.getElementById('atlas-side-b');
var SIDE_ON = false, SIDE_TIMER = 0, OPEN_WAIT = 0, OPEN_MS = 240, SIDE_W = 380, SIDE_KEY = '', AFTER = null, AFTER_KEY = false;
var EV = EVIDENCE_JSON, FF = DATA.maps[0].ff || 'the facts file';
// The width that the details take from the map at the right of a wide screen, for the fit
// of map m. A flight to a neighbour's card keeps it (`AFTER`).
function sideRight(m) {
  if (W <= WIDE) return 0;
  return (SIDE_ON && SEL && SEL.map === m) || (AFTER && AFTER.map === m) ? SIDE_W : 0;
}
// Select card c, or no card. `how.wait` opens the details after OPEN_MS (a click of a
// mouse). `how.keep` does not move the camera. `how.focus` gives the keyboard focus to the
// heading of the details (Enter on a card), so that Tab goes next into the details.
function select(c, how) {
  how = how || {};
  clearTimeout(OPEN_WAIT);
  var was = SIDE_ON;
  SEL = c || null; PIN = null;
  speak(); lightMoved();
  if (!c) {
    sideShow(false);
    if (was && !how.keep) fitCurrent();
    return;
  }
  var go = function () {
    if (SEL !== c) return;
    sideSync(); sideShow(true);
    say('Selected: ' + c.id + '. The details are open.');
    if (how.focus) document.getElementById('atlas-side-h').focus({preventScroll: true});
    if (how.keep) return;
    if (W <= WIDE) showAbove(c); else if (!was) fitCurrent();
  };
  if (NOTE_EL) NOTE_EL.classList.add('gone');
  if (how.wait && (!reduced() || c.child)) OPEN_WAIT = setTimeout(go, OPEN_MS); else go();
}
// On a phone: move the selected card to the middle of the part of the screen between the
// bars at the top and the sheet, at a scale of 0.62 or more. That part is too short for the
// map, thus other cards go above the selected card. The headline is HTML text over the
// canvas, and it does not show while the sheet is open (`body.open .ask`). Thus no text
// covers a card. The bars at the top are the header, the strip of the layer tabs and the
// bar of a nested map: each has the color of the surface. In the Sequences view the row of
// the list of the sequences is also at the top (`RAIL` in `atlas_sequences`).
function showAbove(c) {
  var rail = VIEW.mode === 'seq' && shownEl(RAIL) ? RAIL.getBoundingClientRect().bottom : 0;
  var b = worldBox(c), top = Math.max(HEAD_H + tabStrip() + insideH(c.map), rail) + 8, low = SIDE.offsetTop - 8;
  var k = clamp(Math.max(cam.k, 0.62 / c.map.T.s), KMIN, Math.min((W - 32) / b[2], Math.max(1, low - top) / b[3], KMAX));
  var cx = W / 2, cy = (top + low) / 2;
  fly({x: b[0] + b[2] / 2 - cx / k, y: b[1] + b[3] / 2 - cy / k, k: k});
}
function sideShow(on) {
  if (!SIDE || on === SIDE_ON) return;
  SIDE_ON = on; clearTimeout(SIDE_TIMER);
  document.body.classList.toggle('open', on);
  if (on) { SIDE.hidden = false; SIDE.getBoundingClientRect(); SIDE.classList.add('on'); return; }
  if (SIDE.contains(document.activeElement)) cv.focus({preventScroll: true});
  SIDE.classList.remove('on'); point(null, null, '');
  if (reduced()) SIDE.hidden = true; else SIDE_TIMER = setTimeout(function () { if (!SIDE_ON) SIDE.hidden = true; }, 300);
}
// Close the details, and give the keyboard focus back to the card on the canvas.
function closeSide() {
  var c = SEL;
  select(null);
  if (c && c.map === currentMap()) { cv.focus({preventScroll: true}); setFocus(c); }
}
// Select a card, or go out to the card of a neighbour. `mouse` waits for a double-click.
// `keyed` is true for Enter: the keyboard focus goes to the details.
function act(c, mouse, keyed) {
  var up = upCard(c);
  if (!up) { select(SEL === c ? null : c, {wait: mouse, focus: keyed}); return; }
  leaveTo(up.map, up, keyed);
}
// When the camera stops in the map of the card of a neighbour, select that card.
function afterFlight() {
  if (!AFTER || currentMap() !== AFTER.map) return;
  var c = AFTER;
  AFTER = null;
  select(c, {keep: W > WIDE, focus: AFTER_KEY});
}
// Go into the map that card c opens. The selection, the pin and the pointed item go, and
// the reading line is empty.
function dive(c) {
  select(null, {keep: true});
  PIN = null; FOCUS = null; FOCUS_MAP = c.child; HOT = {c: null, f: null, from: ''};
  speak();
  zoomMove(c, true, frameOf(c.child));
}

// ---- the text of the details ------------------------------------------------------
function kindWords(c) {
  var o = c.map.owner;
  if (c.k === 'actor') return o ? 'Outside ' + o.id : 'Actor · outside the system';
  if (o) return 'Part of ' + o.id;
  return c.k === 'component' ? 'Component' : c.k;
}
function colorOf(f, e) { e.style.setProperty('--k', 'var(' + (KIND[f.k] || '--ink-2') + ')'); return e; }
function levelWords(o) { return o.as ? 'Assurance level: ' + o.as[0] + '. Freshness: ' + o.as[1] + '.' : ''; }
// The assurance level and the freshness of a card under its name, in the words of the study.
var CLAIM_WORDS = {established: 'Claims established from the source facts', examined: 'Claims examined against the source', unknown: 'Claims not examined'};
function claimWords(o) { return (CLAIM_WORDS[o.as[0]] || 'Claims ' + o.as[0]) + ', ' + o.as[1]; }
// A section of the details: a heading with the count n, and each argument after n as a child.
function section(name, n) {
  var e = el('section', {'class': 'sec'}, el('h3', null, name, n === null ? null : el('span', null, String(n))));
  for (var i = 2; i < arguments.length; i++) addChild(e, arguments[i]);
  return e;
}
// One row of a flow: the line of its kind, the artifact, the card at the other end, the
// relation sentence and the evidence state.
function flowRow(f, word, other) {
  return colorOf(f, el('button', {type: 'button', 'class': 'row', 'data-f': f.i}, el('i'),
    el('b', null, f.a + ' ', el('em', null, word + ' ' + other)), f.y ? el('small', null, f.y) : null,
    el('small', {'class': 'ev'}, 'Evidence: ' + (EV[f.ev] || f.ev) + '.' + (f.as ? ' ' + levelWords(f) : ''))));
}
function flowLists(c) {
  var id = shownLayer(c.map), fl = layerFlags(c.map, id).flow, out = [], other = 0;
  [['Receives', c.ins, 'from', 's'], ['Gives', c.outs, 'to', 't']].forEach(function (g) {
    var list = g[1].filter(function (f) { return fl[f.i]; });
    other += g[1].length - list.length;
    if (list.length) out.push(section(g[0], list.length, list.map(function (f) { return flowRow(f, g[2], f[g[3]]); })));
  });
  if (!out.length) out.push(el('p', {'class': 'side__d'}, 'This card has no flow in the layer ' + layerName(c.map, id) + '.'));
  if (other) out.push(el('p', {'class': 'side__d'}, counted(other, 'flow') + ' of this card ' + (other === 1 ? 'is' : 'are') + ' in other layers. ',
    el('button', {type: 'button', 'class': 'more', 'data-all': ''}, 'Show all layers')));
  return out;
}
function about(d) {
  var p = el('p', {'class': 'side__d' + (d.length > 260 ? ' clip' : '')}, d);
  return d.length > 260 ? [p, el('button', {type: 'button', 'class': 'more', 'data-more': ''}, 'Read all')] : p;
}
// The sequences of the map that use card c, with the numbers of their steps.
function sequencesOf(c) {
  var m = c.map, out = [];
  (m.sq || []).forEach(function (q) {
    var at = [];
    q.s.forEach(function (s, k) {
      var f = s.f >= 0 ? m.flows[s.f] : null;
      if ((f && (f.s === c.id || f.t === c.id)) || (s.a || []).indexOf(c.id) >= 0 || (s.me || []).indexOf(c.id) >= 0) at.push(k + 1);
    });
    if (at.length) out.push(el('li', null, el('b', null, q.n), ': ' + (at.length === 1 ? 'step ' : 'steps ') + at.join(', ') + '.'));
  });
  return section('Sequences', out.length, out.length ? el('ul', null, out) : el('p', {'class': 'side__d'}, 'No sequence of this map uses this card.'));
}
function modules(c) {
  var list = c.m || [];
  if (!list.length) return null;
  return section('Source modules', list.length, el('div', {'class': 'mods'}, list.slice(0, 14).map(function (n) { return el('code', null, n); }),
    list.length > 14 ? el('code', null, '+ ' + (list.length - 14) + ' more') : null));
}
function names(xs) { return xs.length ? xs.map(function (x, i) { return [i ? ', ' : null, el('code', null, x)]; }) : 'none recorded'; }
function fileOf(m, x) { return 'f' in x ? x.f : m.fr ? m.fr[0] + x.i.replace(/\./g, '/') + m.fr[1] : ''; }
function nameOf(m, x) { return typeof x === 'number' ? m.md[x].i : x; }
// The importers of module j: an index for a module of the map, a name for another module.
function importerIds(m, j) {
  var x = m.md[j], out = [];
  if (!x.ia) m.md.forEach(function (o, k) { if ((o.im || []).indexOf(j) >= 0) out.push(k); });
  return out.concat(x.ib || []);
}
function importers(m, j) { return importerIds(m, j).map(function (y) { return nameOf(m, y); }); }
// ---- Uses and Used by: the cards that the modules of a card import, and the reverse ------
var USES_SHOWN = 8;
function ownersOf(m) {
  var own = {};
  Object.keys(m.sr || {}).forEach(function (id) { (m.sr[id].mo || []).forEach(function (k) { own[k] = id; }); });
  return own;
}
function between(m, a, b) { return (m.flows || []).filter(function (f) { return (f.s === a && f.t === b) || (f.s === b && f.t === a); }); }
function size(o) { return Object.keys(o).length; }
// The links of card c: `uses` and `by` give, for each other card, the importing modules
// (a) and the imported modules (b). `out` gives the imported modules outside the map.
// `sr` has no actors, thus no module has an actor as its owner and no row is for an actor.
function useLinks(c) {
  var m = c.map, own = ownersOf(m), mine = ((m.sr || {})[c.id] || {}).mo || [], got = {uses: {}, by: {}, out: {}};
  function add(t, id, a, b) {
    var o = m.byId[id];
    if (id === undefined || id === c.id || !o) return;
    var r = t[id] || (t[id] = {a: {}, b: {}});
    r.a[a] = 1; r.b[b] = 1;
  }
  mine.forEach(function (j) {
    (m.md[j].im || []).forEach(function (y) { if (typeof y === 'number') add(got.uses, own[y], j, y); else got.out[y] = 1; });
    importerIds(m, j).forEach(function (y) { if (typeof y === 'number') add(got.by, own[y], y, j); });
  });
  return got;
}
function linkRow(c, id, r, mine) {
  var fl = between(c.map, c.id, id), a = size(r.a), b = size(r.b), verb = a === 1 ? ' imports ' : ' import ';
  var tag = fl.length ? 'flow: ' + fl[0].a + (fl.length > 1 ? ' and ' + (fl.length - 1) + ' more' : '') : 'no flow';
  var text = mine ? counted(a, 'module') + ' of this card' + verb + counted(b, 'module') + ' of ' + id + '.'
    : counted(a, 'module') + ' of ' + id + verb + counted(b, 'module') + ' of this card.';
  var e = el('button', {type: 'button', 'class': 'row', 'data-c': id}, el('i'), el('b', null, id + ' ', el('em', null, tag)), el('small', null, text));
  if (fl.length) return colorOf(fl[0], e);
  e.style.setProperty('--k', 'var(--line-2)');
  return e;
}
function linkList(c, name, t, mine, empty, extra) {
  var m = c.map, ids = Object.keys(t), flowed = {};
  ids.forEach(function (id) { flowed[id] = between(m, c.id, id).length ? 1 : 0; });
  ids.sort(function (x, y) { return flowed[x] - flowed[y] || size(t[y].a) - size(t[x].a) || (x < y ? -1 : x > y ? 1 : 0); });
  var rows = ids.map(function (id, n) { var e = linkRow(c, id, t[id], mine); if (n >= USES_SHOWN) e.hidden = true; return e; });
  return section(name, ids.length, rows.length ? rows : el('p', {'class': 'side__d'}, empty),
    ids.length > USES_SHOWN ? el('button', {type: 'button', 'class': 'more', 'data-uses': ''}, 'Show all ' + ids.length) : null,
    extra, el('p', {'class': 'side__d'}, 'These lists include imports for type checks.'));
}
function useLists(c) {
  if (c.k === 'actor') return null;
  var got = useLinks(c), n = size(got.out);
  var out = n ? el('p', {'class': 'side__d'}, 'Modules of this card also import ' + counted(n, 'module') + ' outside this map.') : null;
  return [linkList(c, 'Uses', got.uses, true, 'This card imports no module of another card.', out),
    linkList(c, 'Used by', got.by, false, 'No module of another card imports this card.', null)];
}
function moduleRecord(m, j) {
  var x = m.md[j], file = fileOf(m, x);
  return el('details', null, el('summary', null, x.i), el('p', null, file ? el('code', null, file) : 'Source path not recorded.'),
    el('p', null, 'Public names in this module: ' + (x.n ? x.n[0] : 0) + '. Tests with imports of this module: ' + (x.n && x.n[1] || 0) + '.'),
    el('p', null, 'Imports: ', names((x.im || []).map(function (y) { return nameOf(m, y); })), '.'),
    el('p', null, 'Imported by: ', names(importers(m, j)), '.'),
    el('p', null, 'External imports: ', names(x.ex || []), '.'),
    (x.uk || []).map(function (u) { return el('p', null, 'Unknown fact: ' + u); }));
}
// The source records of a card that is not an actor, as on the canvas page.
function records(c) {
  if (c.k === 'actor') return null;
  var m = c.map, r = (m.sr || {})[c.id] || {}, mo = r.mo || [], pt = r.pt || [];
  return el('div', {'class': 'rec'},
    (c.u || []).map(function (u) { return el('p', {'class': 'side__d'}, 'The source data has no source for this module claim: ', el('code', null, u), '.'); }),
    el('details', null, el('summary', null, 'Source records'),
      el('p', null, 'Module claims in the model: ', names(c.m || []), '.'),
      (r.sc || []).map(function (s) { return el('p', null, 'Public name in the model: ', el('code', null, s), '.'); }),
      mo.length ? mo.map(function (j) { return moduleRecord(m, j); }) : el('p', null, 'The source data has no modules for this card.'),
      el('p', null, 'The facts file ', el('code', null, FF), ' gives the module descriptions, the public names and the tests. References do not prove coverage.'),
      el('p', null, el('b', null, 'Entry points.'), ' An entry point is where a program can start.'),
      pt.length ? pt.map(function (p) { return el('p', null, el('code', null, p)); }) : el('p', null, 'No entry points were extracted for these modules.')));
}
// The rules of the map: the invariants and the import rules. `c` keeps only the rules of
// that card. Each rule gives its assurance level and its freshness.
function ruleItems(m, c) {
  var out = [];
  (m.iv || []).forEach(function (r) {
    if (!c || (r.g || []).indexOf(c.id) >= 0) out.push(el('li', null, el('b', null, 'Invariant ' + r.n + '.'), ' ' + r.t + ' ', el('span', {'class': 'as'}, levelWords(r))));
  });
  (m.ir || []).forEach(function (r) {
    var s = r.s || [], t = r.t || [];
    if (!c || !s.length || s.indexOf(c.id) >= 0 || t.indexOf(c.id) >= 0) out.push(el('li', null, el('b', null, 'Import rule ' + r.id + '.'), ' Kind: ' + r.k + '. ', el('span', {'class': 'as'}, levelWords(r))));
  });
  return out;
}
function rules(c) {
  var m = c.map, own = ruleItems(m, c), every = ruleItems(m, null);
  return section('Rules', own.length, own.length ? el('ul', null, own) : el('p', {'class': 'side__d'}, 'No rule of the model names this card.'),
    every.length ? el('details', null, el('summary', null, 'All rules of this map (' + every.length + ')'), el('ul', null, every))
      : el('p', {'class': 'side__d'}, 'The model has no rules for this map.'));
}
function enterButton(c) {
  var icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg'), path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  icon.setAttribute('width', '13'); icon.setAttribute('height', '13'); icon.setAttribute('viewBox', '0 0 13 13'); icon.setAttribute('aria-hidden', 'true');
  path.setAttribute('d', ENTER_PATH); path.setAttribute('fill', 'none'); path.setAttribute('stroke', 'currentColor'); path.setAttribute('stroke-width', '1.5');
  icon.append(path);
  return el('button', {type: 'button', 'class': 'enter', 'data-go': ''}, icon, 'See its ' + counted(partsOf(c), 'part'));
}
// The button that shows the card in the Focus view (`atlas_focus`), for a card with a flow
// that is not a neighbour of a nested map.
function focusButton(c) {
  if (upCard(c) || !fcDegree(c.map)[c.id]) return null;
  return el('button', {type: 'button', 'class': 'more fgo', 'data-focus': ''}, 'Focus on this card');
}
// Write the details of the selected card when the card or the layer changes.
function sideSync() {
  var c = SEL;
  if (!c || !SIDE) return;
  var key = c.map.oi + ':' + c.i + '|' + shownLayer(c.map);
  if (key === SIDE_KEY) return;
  SIDE_KEY = key;
  document.getElementById('atlas-side-k').textContent = kindWords(c);
  document.getElementById('atlas-side-h').textContent = c.id;
  document.getElementById('atlas-side-p').textContent = c.p || '';
  var st = document.getElementById('atlas-side-s');
  st.replaceChildren.apply(st, c.as ? [el('i', {'class': c.as[0] === 'unknown' ? 'no' : null}), claimWords(c)] : []);
  var body = document.createDocumentFragment();
  addChild(body, [c.child ? enterButton(c) : null, focusButton(c), c.d ? about(c.d) : null, c.nt ? el('p', {'class': 'side__d'}, el('b', null, 'Note.'), ' ' + c.nt) : null,
    flowLists(c), useLists(c), sequencesOf(c), modules(c), records(c), rules(c)]);
  if (SIDE.contains(document.activeElement) && SIDE_B.contains(document.activeElement)) document.getElementById('atlas-side-h').focus({preventScroll: true});
  SIDE_B.replaceChildren(body);
  SIDE_B.scrollTop = 0;
}
// The flow of a row of the details, or null.
function rowFlow(t) {
  var b = t && t.closest ? t.closest('[data-f]') : null;
  return b && SEL ? SEL.map.flows[+b.getAttribute('data-f')] : null;
}
if (SIDE) {
  document.getElementById('atlas-side-x').addEventListener('click', closeSide);
  SIDE.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeSide(); } });
  SIDE_B.addEventListener('pointerover', function (e) { var f = rowFlow(e.target); if (f && e.pointerType !== 'touch') point(null, f, 'row'); });
  SIDE_B.addEventListener('pointerout', function (e) { if (rowFlow(e.target) && !rowFlow(e.relatedTarget) && HOT.from === 'row') point(null, null, ''); });
  SIDE_B.addEventListener('focusin', function (e) { var f = rowFlow(e.target); if (f) point(null, f, 'row'); });
  SIDE_B.addEventListener('focusout', function (e) { if (HOT.from === 'row' && !rowFlow(e.relatedTarget)) point(null, null, ''); });
  SIDE_B.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('button') : null, c = SEL, f = rowFlow(e.target);
    if (!b || !c) return;
    if (f) { var o = c.map.byId[f.s === c.id ? f.t : f.s]; if (o) { point(null, null, ''); act(o, false); } }
    else if (b.hasAttribute('data-c')) { var u = c.map.byId[b.getAttribute('data-c')]; if (u) act(u, false); }
    else if (b.hasAttribute('data-uses')) { b.parentNode.querySelectorAll('.row[hidden]').forEach(function (r) { r.hidden = false; }); b.remove(); }
    else if (b.hasAttribute('data-go') && c.child) dive(c);
    else if (b.hasAttribute('data-focus')) fcEnter(c);
    else if (b.hasAttribute('data-all')) setLayer('all');
    else if (b.hasAttribute('data-more')) {
      var d = b.previousElementSibling, shut = d.classList.toggle('clip');
      b.textContent = shut ? 'Read all' : 'Show less';
    }
  });
}

// ---- Reduce motion ------------------------------------------------------------------
var MOTION_BTN = document.getElementById('atlas-motion');
function showMotion() { if (MOTION_BTN) MOTION_BTN.setAttribute('aria-pressed', String(document.documentElement.getAttribute('data-reduce-motion') === 'true')); }
if (MOTION_BTN) MOTION_BTN.addEventListener('click', function () {
  var on = document.documentElement.getAttribute('data-reduce-motion') !== 'true';
  document.documentElement.setAttribute('data-reduce-motion', String(on));
  try { localStorage.setItem(MOTION_KEY, String(on)); } catch (e) { /* no storage */ }
  showMotion(); request();
  say('Reduce motion: ' + (on ? 'on' : 'off') + '.');
});
showMotion();
"""

DETAILS = (
    DETAILS.replace("EVIDENCE_JSON", _EVIDENCE)
    .replace("MOTION_KEY", json.dumps(page.MOTION_KEY))
    .replace("ENTER_PATH", json.dumps(_ENTER))
)
