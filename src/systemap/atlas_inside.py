"""The inside part of the atlas page: the signs that the page shows a nested map.

`atlas_script` joins the script of this part after the image part (`atlas_image`). The
rules are the section "Map view: the rules" of docs/design/atlas.md ("Inside a nested map"):

- The bar (`atlas-inside`). In the Map view of a nested map, a bar at the top of the map
  area gives "Inside" and the name of the map, and a button "Back to" the map above, with
  the key Esc. At depth 2 or more, the bar also gives the path from the top map, and each
  name in the path is a button that goes to that map. The fit of a nested map keeps the
  height of the bar free (`insideH` in the fit of `atlas_input`), and the headline moves
  down by that height (`--ih`).
- The zoom movement (`zoomMove`). A dive goes from the box of the card on the map above to
  the fit of the nested map, in ZOOM_MS. A move out goes back to the box of the card, and
  the card is then selected (`leaveTo`). In the movement, the nested map has a place that
  goes from the box of its card to its own place (`MORPH`, `retree`). With reduced motion,
  the camera goes to the end at once.
- The locator (`atlas-loc`). A small picture of the map above with the card of the nested
  map marked, in a corner of the screen where it covers no card and no label at rest of the
  nested map at its fit (`locSpot`). When no corner is free, the locator does not show. A
  click on it goes out.
- The ground. While the camera is in a nested map, the ground of the canvas has the color
  `--inside`, not `--map` (`groundSync`). The frame of a nested map has its name as a title
  (`drawBoxes` in `atlas_draw`).
- The neighbours. A neighbour card of a nested map has the line "on" and the name of the map
  above below its name (`cardText` in `atlas_draw`).

The script writes the bar with DOM functions (`el` in `atlas_tree`), not with HTML text.
"""

from __future__ import annotations

# The bar comes before the headline, and the locator after the canvas of the map.
BAR_HTML = '<nav class="inside" id="atlas-inside" aria-label="Nested map" hidden></nav>'
LOC_HTML = (
    '<button type="button" class="loc" id="atlas-loc" hidden>'
    '<canvas aria-hidden="true"></canvas></button>'
)

CSS = """
.inside{position:fixed;left:0;right:0;top:48px;z-index:2;display:flex;align-items:center;flex-wrap:wrap;
gap:6px 16px;min-height:48px;box-sizing:border-box;padding:7px max(16px,env(safe-area-inset-right,0px)) 7px
max(16px,env(safe-area-inset-left,0px));background:var(--surface);border-bottom:1px solid var(--line);
font:500 14px/20px var(--fs);color:var(--ink-2)}
.inside[hidden]{display:none}
.inside.off{visibility:hidden}
.inside__back{display:inline-flex;align-items:center;gap:8px;min-height:34px;padding:0 6px 0 9px;
border:1px solid var(--line-2);border-radius:9px;color:var(--ink);font-weight:600;background:var(--map)}
.inside__back:hover{background:var(--tint)}
.inside kbd{font:500 14px/1 var(--fm);padding:3px 6px;border:1px solid var(--line-2);border-radius:6px;
color:var(--ink-2);background:var(--surface)}
.inside__at b{color:var(--ink);font-weight:600}
.inside__path{display:flex;flex-wrap:wrap;gap:4px 7px;align-items:center}
.inside__path button{color:var(--ink-2);text-decoration:underline;text-underline-offset:3px;
text-decoration-color:var(--line-2)}
.inside__path button:hover{color:var(--ink)}
.inside__path [aria-current]{color:var(--ink);font-weight:600;text-decoration:none}
.loc{position:fixed;left:var(--lx,0);top:var(--ly,0);z-index:1;padding:0;border:1px solid var(--line-2);
border-radius:8px;background:var(--surface);box-shadow:var(--shadow);overflow:hidden;cursor:pointer}
.loc[hidden]{display:none}
.loc canvas{display:block;width:var(--lw,1px);height:var(--lh,1px)}
.loc:hover{border-color:var(--ink-3)}
:root[data-inside][data-inside]{--ink-3:var(--ink-3-in)}
:root[data-inside] .ask::before{background:radial-gradient(closest-side,var(--inside) 62%,transparent)}
:root[data-inside] body{background:var(--inside)}
:root[data-inside] :is(.rail,.srail,.frail,.board,.sboard,.fboard){--map:var(--inside)}
@media (max-width:720px){body[data-mode="map"] .inside{top:86px}}
@media (pointer:coarse){.inside__back,.inside__path button{min-height:44px}}
"""

INSIDE = r"""
// ---- the bar of a nested map ----------------------------------------------------------
var BAR_IN = document.getElementById('atlas-inside'), BAR_FOR = '', BAR_HS = Object.create(null);
// The name of map m in a path: the ID of its card, or the name of the system.
function mapTitle(m) { return m.owner ? m.owner.id : (DATA.name || 'map'); }
// The nested map that the view shows (`viewMap` in `atlas_view`), or null. The History view
// shows the top map.
function insideMap() { var m = viewMap(); return m.owner ? m : null; }
// True when the camera of the view shows map m with the bar: the Map view and the map form of
// the Sequences view. The fit of a nested map keeps the height of the bar free.
function insideOn(m) { return !!m.owner && (VIEW.mode === 'map' || (VIEW.mode === 'seq' && SEQ.form !== 'diagram')); }
function inBarWrite(m) {
  var key = m.oi + '|' + W;
  if (BAR_FOR === key) return;
  BAR_FOR = key;
  var up = m.owner.map, chain = [], out = [];
  for (var x = m; x; x = x.owner ? x.owner.map : null) chain.unshift(x);
  var back = el('button', {type: 'button', 'class': 'inside__back', title: 'Go out to the map ' + mapTitle(up) + ' (Esc)'},
    svgBack(), 'Back to ' + mapTitle(up), el('kbd', null, 'Esc'));
  back.addEventListener('click', function () { cv.focus({preventScroll: true}); goOut(); });
  out.push(back, el('span', {'class': 'inside__at'}, 'Inside ', el('b', null, mapTitle(m))));
  if (chain.length > 2) {
    var path = el('span', {'class': 'inside__path', role: 'group', 'aria-label': 'Path'});
    chain.forEach(function (x, i) {
      var last = i === chain.length - 1, b = el('button', {type: 'button', 'aria-current': last ? 'page' : null, title: 'Go to the map ' + mapTitle(x)}, mapTitle(x));
      b.addEventListener('click', function () { cv.focus({preventScroll: true}); if (last && VIEW.mode === 'map') fitCurrent(); else outTo(last ? null : x); });
      if (i) path.append(el('span', {'aria-hidden': 'true'}, '/'));
      path.append(b);
    });
    out.push(path);
  }
  BAR_IN.replaceChildren.apply(BAR_IN, out);
}
function svgBack() {
  var ns = 'http://www.w3.org/2000/svg', s = document.createElementNS(ns, 'svg'), p = document.createElementNS(ns, 'path');
  s.setAttribute('width', '14'); s.setAttribute('height', '14'); s.setAttribute('viewBox', '0 0 14 14'); s.setAttribute('aria-hidden', 'true');
  p.setAttribute('d', 'M8.5 2.5L4 7l4.5 4.5'); p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'currentColor'); p.setAttribute('stroke-width', '1.6');
  s.append(p);
  return s;
}
// The height of the bar of map m on this screen, or 0 when map m has no bar. The fit of a
// nested map keeps it free, also before the bar shows.
function insideH(m) {
  if (!BAR_IN || !m.owner) return 0;
  var key = m.oi + '|' + W, h = BAR_HS[key];
  if (h !== undefined) return h;
  var was = BAR_IN.hidden;
  inBarWrite(m); BAR_IN.hidden = false; BAR_IN.classList.add('off');
  h = BAR_HS[key] = BAR_IN.offsetHeight;
  BAR_IN.hidden = was; BAR_IN.classList.remove('off');
  if (SHOWN_IN && SHOWN_IN !== m) { BAR_FOR = ''; inBarWrite(SHOWN_IN); }
  return h;
}
var SHOWN_IN = null, IN_KEY = '';
// Show the bar of the nested map that the view shows (`insideMap`), and the locator of the
// current map m in the Map view. The bar changes only when its map or the screen width
// changes. Give the bottom of the bar on the screen, or the bottom of the header.
function insideSync(m) {
  var n = insideMap(), on = !!n, was = SHOWN_IN, key = on ? n.oi + '|' + W : '';
  SHOWN_IN = n;
  if (BAR_IN && key !== IN_KEY) {
    IN_KEY = key;
    if (on) inBarWrite(n);
    BAR_IN.hidden = !on; BAR_IN.classList.remove('off');
    document.documentElement.style.setProperty('--ih', (on ? insideH(n) : 0) + 'px');
    if (was && !on && BAR_IN.contains(document.activeElement)) cv.focus({preventScroll: true});
  }
  locSync(m || currentMap());
  return on ? BAR_IN.getBoundingClientRect().bottom : HEAD_H;
}

// ---- the ground --------------------------------------------------------------------
// The ground of the canvas is `--inside` while the view shows a nested map (`insideMap`),
// in each view. The images of a large map have the ground, thus a change of the ground
// makes them again (EPOCH).
function groundSync() {
  var on = !!insideMap(), want = on ? C['--inside'] : C.mapTop;
  if (C['--map'] === want) return;
  // The ground --inside is darker in the light scheme. Thus the text in --ink-3 has the
  // darker tone --ink-3-in, so that its contrast stays 4.5 or more.
  C['--map'] = want; C['--ink-3'] = on ? C['--ink-3-in'] : C.ink3Top; EPOCH++;
  if (on) document.documentElement.setAttribute('data-inside', ''); else document.documentElement.removeAttribute('data-inside');
}

// ---- the zoom movement -------------------------------------------------------------
// The place of the map of card c in the coordinates of the map of c: its own place (`L`),
// or in a movement (MORPH) a place between the box of the card and its own place.
var ZOOM_MS = 360, MORPH = null, MOVES = [];
function cardPlace(c) {
  var z = c.child.size, s = Math.min(c.b[2] / z[0], c.b[3] / z[1]);
  return {x: c.b[0] + (c.b[2] - z[0] * s) / 2, y: c.b[1] + (c.b[3] - z[1] * s) / 2, s: s};
}
function localPlace(c) { return MORPH && MORPH.c === c ? placeAt(c, MORPH.p) : c.child.L; }
// The place of the map of card c at the part p of a movement: the box of the card at 0 and
// its own place at 1. The scale moves in log space.
function placeAt(c, p) {
  var L = c.child.L, B = cardPlace(c);
  return {x: B.x + (L.x - B.x) * p, y: B.y + (L.y - B.y) * p, s: B.s * Math.pow(L.s / B.s, p)};
}
// The world frame of the map of card c at the part p, and its box on the screen for the
// camera k.
function frameAt(c, p) { var L = placeAt(c, p), T = c.map.T, z = c.child.size; return [T.x + T.s * L.x, T.y + T.s * L.y, T.s * L.s * z[0], T.s * L.s * z[1]]; }
function onScreen(b, k) { return [(b[0] - k.x) * k.k, (b[1] - k.y) * k.k, b[2] * k.k, b[3] * k.k]; }
// The screen box of the frame at the part e of a movement from box b0 to box b1: a zoom
// about the one screen point that the two boxes keep.
function zoomBox(b0, b1, e) {
  var r = b1[2] / b0[2], s = Math.pow(r, e);
  function at(i) { if (Math.abs(1 - r) < 1e-3) return b0[i] + (b1[i] - b0[i]) * e; var P = (b1[i] - b0[i] * r) / (1 - r); return P - (P - b0[i]) * s; }
  return [at(0), at(1), b0[2] * s, b0[3] * s];
}
// Place the nested maps of map m again from the place of m.
function retree(m) {
  m.cards.forEach(function (c) {
    if (!c.child) return;
    var L = localPlace(c), T = m.T;
    c.child.T = {x: T.x + T.s * L.x, y: T.y + T.s * L.y, s: T.s * L.s};
    c._fit = null;
    retree(c.child);
  });
}
function morphEnd() {
  if (!MORPH) return;
  var c = MORPH.c;
  MORPH = null; retree(c.map);
}
// Move the camera to the fit of `box` (the frame of a map) with the movement of card c:
// into the map of c (`into`), or out to the map of c.
function zoomMove(c, into, box) {
  stopFlight();
  var move = {kind: into ? 'enter' : 'leave', map: c.child.id, t0: performance.now(), t1: null, first: null};
  MOVES.push(move);
  if (MOVES.length > 20) MOVES.shift();
  if (reduced()) { flyTo(box, FIT); move.t1 = move.t0; return; }
  // The target of the camera is the fit of the map at its own place. Thus the place of the
  // movement starts after `flyTo` (its `stopFlight` ends a movement).
  flyTo(box, FIT, false, ZOOM_MS);
  if (!flight) { move.t1 = performance.now(); return; }
  MORPH = {c: c, p: into ? 0 : 1, into: into, move: move};
  retree(c.map);
  // The frame of the nested map moves on the screen as a zoom from its first box to its
  // last box, and the camera follows the frame (`zoomBox`).
  var p0 = into ? 0 : 1, b0 = onScreen(frameAt(c, p0), cam), b1 = onScreen(frameAt(c, 1 - p0), {x: flight.to.x, y: flight.to.y, k: flight.to.k});
  flight.into = into ? c.child : null;
  // The last frame of the movement draws the nested map at the end of its place: at the box
  // of its card for a move out. The movement ends after that frame (`morphDone`).
  flight.each = function (e, done) {
    if (!MORPH) return;
    MORPH.p = into ? e : 1 - e; MORPH.done = done; retree(c.map);
    var f = frameOf(c.child), b = zoomBox(b0, b1, e), k = b[2] / f[2];
    cam = {x: f[0] - b[0] / k, y: f[1] - b[1] / k, k: k};
  };
}
// The first frame and the last frame of a movement: the screen frame of the nested map and
// the screen box of its card (the tests read them).
function morphFrame() {
  if (!MORPH) return;
  var c = MORPH.c, f = frameOf(c.child), at = {frame: [(f[0] - cam.x) * cam.k, (f[1] - cam.y) * cam.k, f[2] * cam.k, f[3] * cam.k], card: screenBox(c)};
  if (!MORPH.move.first) MORPH.move.first = at;
  MORPH.move.last = at;
}
// After the last frame of a movement: the nested map goes back to its own place. After a
// move out, the next move out of the queue starts (`goOut`), or the keyboard focus goes to
// the card.
function morphDone() {
  if (!MORPH || !MORPH.done) return;
  var c = MORPH.c, into = MORPH.into, up = c.map.owner;
  MORPH.move.t1 = performance.now();
  morphEnd(); request();
  if (into) return;
  if (OUT_TO && OUT_TO !== c.map && up) { var to = OUT_TO; leaveTo(up.map); OUT_TO = to; return; }
  OUT_TO = null;
  if (document.activeElement === cv) setFocus(c, toldLater(c));
}
// The ground of the nested map in a movement: the card becomes the frame of the map.
function morphGround() {
  if (!MORPH) return;
  var c = MORPH.c, f = frameOf(c.child), a = 1 - deepOf(c), r = screenBox(c);
  if (a <= 0.02) return;
  var x = (f[0] - cam.x) * cam.k, y = (f[1] - cam.y) * cam.k, w = f[2] * cam.k, h = f[3] * cam.k, k = Math.min(1, Math.max(w / r[2], h / r[3]));
  ctx.globalAlpha = a; ctx.fillStyle = C['--card']; ctx.strokeStyle = C['--line-2']; ctx.lineWidth = 1;
  ctx.beginPath(); rr(ctx, x, y, w, h, cardCorner(c, r[2], r[3]) * k); ctx.fill(); ctx.stroke();
}
// Go out to map x, an ancestor of the current map. The card of x on the way to the current
// map is selected when the camera stops, or the card `sel` (a neighbour goes out to its
// card).
// OUT_TO is the map where the move out ends, also after the moves in the queue.
var OUT_TO = null;
function leaveTo(x, sel, keyed) {
  var c = null;
  CHAIN.forEach(function (o) { if (o.map === x) c = o; });
  select(null, {keep: true});
  AFTER = sel || c; AFTER_KEY = !!keyed; OUT_TO = c ? x : null;
  if (!c) { flyTo(frameOf(x), FIT); return; }
  zoomMove(c, false, frameOf(x));
}
// True while a move out of a nested map is on the screen.
function leaving() { return !!(MORPH && !MORPH.into && flight); }
// Go out to map x in the Map view, from the nested map that the view shows, or with x null
// to that nested map. The card of x on the way to the nested map is selected. When the
// camera is in the nested map, the zoom movement goes out (`leaveTo`).
function outTo(x) {
  var m = insideMap();
  if (!m) return;
  if (VIEW.mode !== 'map') setMode('map');
  if (!x) { if (currentMap() !== m) flyTo(frameOf(m), FIT); return; }
  if (currentMap() === m) { leaveTo(x); return; }
  var c = null;
  for (var y = m; y.owner; y = y.owner.map) if (y.owner.map === x) c = y.owner;
  select(null, {keep: true});
  AFTER = c; AFTER_KEY = false; OUT_TO = null;
  flyTo(frameOf(x), FIT);
}

// ---- the locator ----------------------------------------------------------------------
var LOC = document.getElementById('atlas-loc'), LOC_CV = LOC ? LOC.querySelector('canvas') : null, LOC_KEY = '', LOC_AT = null;
if (LOC) LOC.addEventListener('click', function () { cv.focus({preventScroll: true}); goOut(); });
function rectOf(e) { if (!e || e.hidden) return null; var r = e.getBoundingClientRect(); return r.width ? [r.left, r.top, r.right, r.bottom] : null; }
// The boxes that the locator must not cover at the fit of map m: the cards, the labels at
// rest, the headline, the zoom control and the key.
function locBusy(m) {
  var f = fitBox(frameOf(m), FIT), a = m.T.s * f.k, ox = (m.T.x - f.x) * f.k, oy = (m.T.y - f.y) * f.k, out = [];
  m.cards.forEach(function (c) { var b = c.b; out.push([ox + a * b[0], oy + a * b[1], ox + a * (b[0] + b[2]), oy + a * (b[1] + b[3])]); });
  var id = layerOf(m), L = linesOf(m, id), s = L.dense ? null : seatsOf(m, id, a);
  if (s) s.list.forEach(function (x) { out.push(labelBox(x.box, a, ox, oy)); });
  [ASK_EL, document.querySelector('.zoom'), KEY].forEach(function (e) { var r = rectOf(e); if (r) out.push(r); });
  return out;
}
// The place of the locator for map m: a corner where it covers no busy box, or null.
function locSpot(m) {
  var up = m.owner.map, most = W > WIDE ? 150 : 104, busy = locBusy(m), bar = insideH(m), side = sideRight(m);
  var top = HEAD_H + tabStrip() + bar + 12, low = H - (W > WIDE ? 58 : TOUCH ? 76 : 60);
  for (var f = 1; f >= 0.6; f -= 0.2) {
    var r = Math.min(most * f / up.size[0], most * 0.7 * f / up.size[1]), w = Math.round(up.size[0] * r) + 8, h = Math.round(up.size[1] * r) + 8;
    var spots = [[W - 16 - side - w, top], [W - 16 - side - w, low - h], [16, low - h]];
    for (var i = 0; i < spots.length; i++) {
      var b = [spots[i][0], spots[i][1], spots[i][0] + w, spots[i][1] + h], pad = [b[0] - 6, b[1] - 6, b[2] + 6, b[3] + 6];
      if (b[0] >= 16 && b[1] >= top && !busy.some(function (o) { return over(pad, o); })) return {x: b[0], y: b[1], w: w, h: h, r: r};
    }
  }
  return null;
}
function locSync(m) {
  if (!LOC) return;
  var on = VIEW.mode === 'map' && insideOn(m) && !flight, key = on ? [m.oi, W, H, EPOCH, layerOf(m), sideRight(m)].join('|') : '';
  if (key === LOC_KEY) return;
  LOC_KEY = key;
  var spot = on ? locSpot(m) : null;
  LOC_AT = spot;
  if (!spot) { LOC.hidden = true; return; }
  var up = m.owner.map, st = LOC.style;
  st.setProperty('--lx', spot.x + 'px'); st.setProperty('--ly', spot.y + 'px');
  st.setProperty('--lw', (spot.w - 2) + 'px'); st.setProperty('--lh', (spot.h - 2) + 'px');
  LOC.setAttribute('aria-label', 'Back to ' + mapTitle(up) + '. The picture shows the card ' + m.owner.id + ' on the map ' + mapTitle(up) + '.');
  LOC.title = 'Back to ' + mapTitle(up) + ' (Esc)';
  locDraw(m, spot);
  LOC.hidden = false;
}
function locDraw(m, spot) {
  var up = m.owner.map, d = dpr(), w = spot.w - 2, h = spot.h - 2, g;
  LOC_CV.width = Math.round(w * d); LOC_CV.height = Math.round(h * d);
  g = LOC_CV.getContext('2d');
  g.setTransform(d, 0, 0, d, 0, 0); g.fillStyle = C.mapTop; g.fillRect(0, 0, w, h);
  var r = spot.r, o = 3;
  up.cards.forEach(function (c) {
    if (c === m.owner) return;
    g.fillStyle = C['--line-2']; g.fillRect(o + r * c.b[0], o + r * c.b[1], Math.max(1, r * c.b[2]), Math.max(1, r * c.b[3]));
  });
  var b = m.owner.b, x = o + r * b[0], y = o + r * b[1], bw = Math.max(3, r * b[2]), bh = Math.max(3, r * b[3]);
  g.fillStyle = C['--focus']; g.fillRect(x, y, bw, bh);
  g.strokeStyle = C['--focus']; g.lineWidth = 1.5; g.strokeRect(x - 2.5, y - 2.5, bw + 5, bh + 5);
}
// The state of the signs of a nested map for the tests.
function insideState() {
  var m = currentMap(), r = BAR_IN ? BAR_IN.getBoundingClientRect() : null;
  return {map: m.id, view: viewMap().id, bar: BAR_IN && !BAR_IN.hidden ? {box: [r.left, r.top, r.width, r.height], text: BAR_IN.textContent} : null,
    loc: LOC && !LOC.hidden ? LOC_AT : null, ground: C['--map'], top: C.mapTop, inside: C['--inside'], moves: MOVES.slice(), morph: !!MORPH};
}
"""
