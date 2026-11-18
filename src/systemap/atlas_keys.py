"""The keyboard and touch part of the atlas renderer: the taps, the clicks and the keyboard focus.

`atlas_script` joins this part after the image part (`atlas_image`). It is a fork of the
touch part and the keyboard part of the canvas page (`page_canvas_touch`,
`page_canvas_keys`), with the rules of docs/design/atlas.md:

- A click with a mouse or a tap on a card selects it, or removes the selection when the
  card is the selected card (`act` in `atlas_details`). A second tap on the selected card
  goes into the map that it opens. A double-click with a mouse goes into that map
  (`enter` in `atlas_input`). A click or a tap on a line pins that line: it stays lit, and
  the reading line gives it. A click on empty space removes the pin, else the selection.
- Tab and Shift+Tab move the keyboard focus through the items of the current map: each
  card in reading order, and after each card the lines that start at it in the layer of
  the map (`tabOrder`). The item with the keyboard focus is lit, and the reading line
  gives it, with its place in the order for a screen reader.
- Enter selects the focused card, or pins the focused line. The keyboard focus then goes
  to the heading of the details. Enter on the selected card that opens a map goes into
  that map. Shift+Enter goes into it at once.
- Esc closes the details, else removes the pin, else goes out one level (`escapeKey`).
  The keyboard focus goes to the card that the details gave, or to the card that opens the
  map that the camera leaves.
"""

from __future__ import annotations

KEYS = r"""
// ---- the taps and the clicks -------------------------------------------------------------
// The card of the current map under a screen point, or null. An open card is empty space.
function pickHere(px, py) { var c = pickClosed(px, py); return c && c.map === currentMap() ? c : null; }
function tapAt(px, py) {
  var c = pickHere(px, py);
  if (c && c === SEL && c.child) { dive(c); return; }
  clickAt(px, py, false);
}
function clickAt(px, py, mouse) {
  var c = pickHere(px, py), f = c ? null : pickLine(px, py);
  if (c) act(c, mouse);
  else if (f) pin(PIN === f ? null : f);
  else if (PIN) pin(null);
  else if (SEL) select(null);
}

// ---- the keyboard focus -------------------------------------------------------------
// FOCUS is the focused card or line, and FOCUS_MAP is the map in which Tab moves.
var FOCUS = null, FOCUS_MAP = null, LIVE = document.getElementById('atlas-said');
var RING_OFF = 7, RING_W = 3;
// The cards of a map in reading order. Each map keeps its order.
function readingOrder(m) {
  if (m._read) return m._read;
  var cards = m.cards.slice().sort(function (a, b) { return a.b[1] - b.b[1] || a.b[0] - b.b[0]; });
  var rows = [], row = null;
  cards.forEach(function (c) {
    var mid = c.b[1] + c.b[3] / 2;
    if (!row || mid > row.y1) { row = {y1: c.b[1] + c.b[3], list: []}; rows.push(row); }
    row.list.push(c);
  });
  m._read = [];
  rows.forEach(function (r) {
    r.list.sort(function (a, b) { return a.b[0] - b.b[0]; });
    Array.prototype.push.apply(m._read, r.list);
  });
  return m._read;
}
// The order of Tab in map m: each card in reading order, and after it the flows that start
// at it in the layer of the map. Each map keeps the order of each layer.
function tabOrder(m) {
  var id = shownLayer(m), memo = m._tab || (m._tab = Object.create(null));
  if (memo[id]) return memo[id];
  var fl = layerFlags(m, id).flow, out = [];
  readingOrder(m).forEach(function (c) {
    out.push(c);
    c.outs.forEach(function (f) { if (fl[f.i] && lineOf(m, f.i)) out.push(f); });
  });
  memo[id] = out;
  return out;
}
// The map in which Tab moves. It stays while a flight goes, while the camera is in the
// map, and while the focused card is open around the middle of the screen. Else it is the
// current map, with no focused item.
function tabMap() {
  var m = currentMap();
  if (FOCUS_MAP && (flight || FOCUS_MAP === m || (FOCUS && CHAIN.indexOf(FOCUS) >= 0))) return FOCUS_MAP;
  FOCUS = null; FOCUS_MAP = m;
  return m;
}
function say(s) { if (LIVE) LIVE.textContent = s; }
// True when the item keeps the keyboard focus: it is in the current map, or it is a card
// that is open around the middle of the screen.
function focusHeld(x) { return x.map === currentMap() || CHAIN.indexOf(x) >= 0; }
// True when the live region tells the map of item x later, with the item (`tell`).
function toldLater(x) { return !!SAID_MAP && x.map !== SAID_MAP; }
function itemWords(x) {
  var list = tabOrder(x.map), n = list.indexOf(x) + 1;
  if (isFlow(x)) return 'Line ' + n + ' of ' + list.length + ': from ' + x.s + ' to ' + x.t + ', ' + x.a + '.';
  return 'Card ' + x.id + ', ' + n + ' of ' + list.length + '.' + (x.child ? ' This card opens a map.' : '');
}
// Give the keyboard focus to card or line x, or to no item. The item is lit, and the
// reading line gives it. `quiet` is true when the live region gives the item later, with
// its map.
function setFocus(x, quiet) {
  FOCUS = x;
  if (x) {
    FOCUS_MAP = x.map;
    if (quiet) say(''); else if (document.activeElement === cv) point(isFlow(x) ? null : x, isFlow(x) ? x : null, 'key');
  } else if (HOT.from === 'key') point(null, null, '');
  request();
}
// The focused item, while it keeps the keyboard focus (`focusHeld`) or a flight goes. Else
// no item has the keyboard focus.
function liveFocus() {
  if (FOCUS && !flight && !focusHeld(FOCUS)) { FOCUS = null; FOCUS_MAP = null; }
  return FOCUS;
}
// The world box of an item: a card, or the box of the points of a line.
function itemBox(x) {
  if (!isFlow(x)) return worldBox(x);
  var e = lineOf(x.map, x.i), T = x.map.T, b = pointsBox(e ? e.q : x.p);
  return [T.x + T.s * (b[0] + 12), T.y + T.s * (b[1] + 12), T.s * (b[2] - 24), T.s * (b[3] - 24)];
}
function itemScreen(x) { var b = itemBox(x); return [(b[0] - cam.x) * cam.k, (b[1] - cam.y) * cam.k, b[2] * cam.k, b[3] * cam.k]; }
// Move the camera when the box of the focused item is not fully in the free box: the
// screen less the details at the side. A flight into the map of the card (`dive`)
// continues: it shows the map of the card.
function showFocus(x) {
  if (flight && flight.into === x.map) return;
  var r = itemScreen(x), x0 = 16, y0 = HEAD_H + 16, x1 = W - 16 - sideRight(x.map), y1 = H - 16;
  if (r[0] >= x0 && r[1] >= y0 && r[0] + r[2] <= x1 && r[1] + r[3] <= y1) return;
  var w = itemBox(x), k = cam.k;
  if (r[2] > x1 - x0 || r[3] > y1 - y0) k = clamp(Math.min((x1 - x0) * 0.8 / w[2], (y1 - y0) * 0.8 / w[3]), KMIN, KMAX);
  fly({x: w[0] + w[2] / 2 - (x0 + x1) / 2 / k, y: w[1] + w[3] / 2 - (y0 + y1) / 2 / k, k: k}, 260);
}
// One Tab step. It gives false when the keyboard focus goes out of the canvas.
function tabStep(back) {
  var list = tabOrder(tabMap()), i = FOCUS ? list.indexOf(FOCUS) : back ? list.length : -1, j = i + (back ? -1 : 1);
  if (j < 0 || j >= list.length) { setFocus(null); return false; }
  setFocus(list[j], !!flight && toldLater(list[j])); showFocus(list[j]);
  return true;
}
function enterKey(shift) {
  var x = liveFocus();
  if (!x) return;
  if (isFlow(x)) { pin(PIN === x ? null : x); return; }
  if (x.child && (shift || SEL === x)) { dive(x); return; }
  act(x, false, true);
}
// Esc on the canvas: the keyboard focus goes to the card that opens the map that the camera
// leaves. The live region gives that card with the new map, when the camera stops.
function focusOut() {
  var n = CHAIN.length, c = n ? CHAIN[n - 1] : null;
  if (c && document.activeElement === cv) setFocus(c, toldLater(c));
}
function escapeKey() {
  if (SEL || SIDE_ON) closeSide();
  else if (PIN) pin(null);
  else goOut();
}
cv.addEventListener('keydown', function (e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'Tab' && tabStep(e.shiftKey)) e.preventDefault();
  else if (e.key === 'Enter' && FOCUS) { e.preventDefault(); enterKey(e.shiftKey); }
});
cv.addEventListener('pointerdown', function () { if (FOCUS) setFocus(null); });
cv.addEventListener('focus', function () { if (FOCUS && liveFocus()) setFocus(FOCUS); request(); });
cv.addEventListener('blur', function () { if (HOT.from === 'key') point(null, null, ''); request(); });
function ringBox(x) {
  var r = itemScreen(x), w = Math.max(r[2], 4), h = Math.max(r[3], 4), cx = r[0] + r[2] / 2 - w / 2, cy = r[1] + r[3] / 2 - h / 2;
  return [cx - RING_OFF, cy - RING_OFF, w + 2 * RING_OFF, h + 2 * RING_OFF];
}
// The ring of the focused item, over all other drawing, only while the canvas has the
// keyboard focus. A focused line has a ring along its line.
function drawFocus() {
  if (!liveFocus() || document.activeElement !== cv) return;
  var x = FOCUS;
  ctx.globalAlpha = 1; ctx.setLineDash([]); ctx.strokeStyle = C['--ink']; ctx.lineWidth = RING_W;
  if (isFlow(x)) {
    var e = lineOf(x.map, x.i), v = view(x.map);
    if (!e) return;
    ctx.strokeStyle = C['--brand']; ctx.globalAlpha = 0.7; ctx.lineWidth = 2; ctx.lineJoin = 'round';
    [-1, 1].forEach(function (side) {
      ctx.beginPath(); cutLine(ctx, e.d.map(function (p, i) { return offsetPoint(e.d, i, side * 5 / v.a); }), v.ox, v.oy, v.a); ctx.stroke();
    });
    return;
  }
  var r = screenBox(x), b = ringBox(x);
  if (!boxOnScreen(b)) return;
  ctx.beginPath(); rr(ctx, b[0], b[1], b[2], b[3], cardCorner(x, r[2], r[3]) + RING_OFF); ctx.stroke();
}
// Point i of a line of right angles, moved by d to the left of the line.
function offsetPoint(p, i, d) {
  var n = [0, 0];
  function side(u, v) { var l = Math.hypot(v[0] - u[0], v[1] - u[1]) || 1; return [-(v[1] - u[1]) / l, (v[0] - u[0]) / l]; }
  if (i > 0) { var s0 = side(p[i - 1], p[i]); n[0] += s0[0]; n[1] += s0[1]; }
  if (i < p.length - 1) { var s1 = side(p[i], p[i + 1]); n[0] += s1[0]; n[1] += s1[1]; }
  return [p[i][0] + n[0] * d, p[i][1] + n[1] * d];
}
// The state of the keyboard focus for the tests.
function keyState() {
  var f = liveFocus();
  return {focus: f ? (isFlow(f) ? {map: f.map.id, f: f.i} : {map: f.map.id, id: f.id}) : null, ring: f && !isFlow(f) ? {box: ringBox(f), width: RING_W} : null};
}
"""
