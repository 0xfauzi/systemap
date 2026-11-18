"""The keyboard and selection part of the atlas renderer: the selected card, the taps and
the keyboard focus.

`atlas_script` joins this part after the tree part (`atlas_tree`). It is a fork of the
touch part and the keyboard part of the canvas page (`page_canvas_touch`,
`page_canvas_keys`). A click with a mouse or a tap selects a card, and the selected card
has a halo. A second tap on a card that opens a map goes into that map. Tab and Shift+Tab
move the keyboard focus through the cards of the current map in reading order, and Enter
goes into the focused card or selects it. Esc goes out one level, and the keyboard focus
goes to the card that opens the map that the camera leaves.

The plate of facts of the canvas page is not in this fork. The details of a selected card
come in stage 2 of docs/design/atlas.md.
"""

from __future__ import annotations

KEYS = r"""
// ---- the selected card ----------------------------------------------------------------
// SEL_C is the selected card, or null. SELS has the cards that the frame draws as selected,
// each with its alpha `a`: the selected card, and the cards that fade out.
// `SEL_FADING` is true when an alpha did not get to its target in the frame.
// SEL_HOOKS has the functions that a change of SEL_C calls (`page_canvas_details`).
var SEL_C = null, SELS = [], SEL_MS = 160, SEL_LAST = 0, SEL_FADING = false, SEL_HOOKS = [];
function selTold() { SEL_HOOKS.forEach(function (f) { f(); }); }
function select(c) {
  var was = SEL_C;
  SEL_C = c || null;
  if (was !== SEL_C) selTold();
  if (SEL_C) say('Selected: card ' + SEL_C.id + '.');
  if (SEL_C && !SELS.some(function (e) { return e.c === SEL_C; })) SELS.push({c: SEL_C, a: 0});
  request();
}
// Tell if the map of card c is on the screen as an open map: the top map or a map of the chain.
function mapOpen(c) {
  if (c.map === TOP) return true;
  for (var i = 0; i < CHAIN.length; i++) if (CHAIN[i].child === c.map) return true;
  return false;
}
function selFrame() {
  var now = performance.now(), dt = SEL_LAST ? now - SEL_LAST : Infinity, step = reduced() ? 1 : Math.min(0.2, dt / SEL_MS);
  SEL_LAST = now; SEL_FADING = false;
  if (SEL_C && !mapOpen(SEL_C)) { SEL_C = null; selTold(); }
  SELS = SELS.filter(function (e) {
    var to = e.c === SEL_C ? 1 : 0;
    e.a = approach(e.a, to, step);
    if (e.a !== to) SEL_FADING = true;
    return e.a > 0 || to > 0;
  });
}
// The halo around each selected card, and its stronger border.
function drawSelected() {
  ctx.setLineDash([]);
  SELS.forEach(function (e) {
    var b = screenBox(e.c), r = cardCorner(e.c, b[2], b[3]);
    if (e.a <= 0.01 || !boxOnScreen(b)) return;
    ctx.globalAlpha = e.a; ctx.strokeStyle = C['--halo']; ctx.lineWidth = 5;
    ctx.beginPath(); rr(ctx, b[0] - 3, b[1] - 3, b[2] + 6, b[3] + 6, r + 3); ctx.stroke();
    ctx.strokeStyle = C['--ink']; ctx.lineWidth = 1.5; ctx.beginPath(); rr(ctx, b[0], b[1], b[2], b[3], r); ctx.stroke();
  });
}
// A tap on card c, or on empty space when c is null.
function tapCard(c) {
  if (c && c === SEL_C && c.child && deepOf(c) < 0.5) { select(null); flyGoal(goalOf(c.map, c, null)); return; }
  select(c);
}
// A tap at a screen point. An open card is empty space (`pickClosed`).
function tapAt(px, py) { tapCard(pickClosed(px, py)); }

// ---- the keyboard focus -------------------------------------------------------------
// FOCUS is the focused card, and FOCUS_MAP is the map in which Tab moves.
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
// The map in which Tab moves. It stays while a flight goes, while the camera is in the
// map, and while the focused card is open around the middle of the screen. Else it is the
// current map, with no focused card.
function tabMap() {
  var m = currentMap();
  if (FOCUS_MAP && (flight || FOCUS_MAP === m || (FOCUS && CHAIN.indexOf(FOCUS) >= 0))) return FOCUS_MAP;
  FOCUS = null; FOCUS_MAP = m;
  return m;
}
function say(s) { if (LIVE) LIVE.textContent = s; }
// True when the card keeps the keyboard focus: it is in the current map, or it is open
// around the middle of the screen.
function focusHeld(c) { return c.map === currentMap() || CHAIN.indexOf(c) >= 0; }
// True when the live region tells the map of card c later, with the card (`tell`).
function toldLater(c) { return !!SAID_MAP && c.map !== SAID_MAP; }
function cardWords(c) {
  var list = readingOrder(c.map), n = list.indexOf(c) + 1;
  return 'Card ' + c.id + ', ' + n + ' of ' + list.length + '.' + (c.child ? ' This card opens a map.' : '');
}
// `quiet` is true when the live region gives the card later, with its map.
function setFocus(c, quiet) {
  FOCUS = c;
  if (c) { FOCUS_MAP = c.map; if (!quiet) say(cardWords(c)); }
  request();
}
// The focused card, while it keeps the keyboard focus (`focusHeld`) or a flight goes. Else
// no card has the keyboard focus.
function liveFocus() {
  if (FOCUS && !flight && !focusHeld(FOCUS)) { FOCUS = null; FOCUS_MAP = null; }
  return FOCUS;
}
// Move the camera when the box of the focused card is not fully in the free box. A
// flight into the map of the card (`enterKey`) continues: it shows the map of the card.
function showFocus(c) {
  if (flight && flight.into === c.map) return;
  var r = screenBox(c), x0 = 16, y0 = HEAD_H + 16, x1 = W - 16, y1 = H - 16;
  if (r[0] >= x0 && r[1] >= y0 && r[0] + r[2] <= x1 && r[1] + r[3] <= y1) return;
  if (r[2] > x1 - x0 || r[3] > y1 - y0) { flyTo(worldBox(c), 0.2); return; }
  var w = worldBox(c), k = cam.k;
  fly({x: w[0] + w[2] / 2 - (x0 + x1) / 2 / k, y: w[1] + w[3] / 2 - (y0 + y1) / 2 / k, k: k}, 260);
}
// One Tab step. It gives false when the keyboard focus goes out of the canvas.
function tabStep(back) {
  var list = readingOrder(tabMap()), i = FOCUS ? list.indexOf(FOCUS) : back ? list.length : -1, j = i + (back ? -1 : 1);
  if (j < 0 || j >= list.length) { setFocus(null); return false; }
  setFocus(list[j], !!flight && toldLater(list[j])); showFocus(list[j]);
  return true;
}
function enterKey() {
  var c = liveFocus();
  if (!c) return;
  if (c.child) {
    FOCUS = null; FOCUS_MAP = c.child; request(); flyGoal(goalOf(c.map, c, null));
    if (flight) flight.into = c.child;
    return;
  }
  select(c);
}
// Esc on the canvas: the keyboard focus goes to the card that opens the map that the camera
// leaves. The live region gives that card with the new map, when the camera stops.
function focusOut() {
  var n = CHAIN.length, c = n ? CHAIN[n - 1] : null;
  if (c && document.activeElement === cv) setFocus(c, toldLater(c));
}
cv.addEventListener('keydown', function (e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'Tab' && tabStep(e.shiftKey)) e.preventDefault();
  else if (e.key === 'Enter' && FOCUS) { e.preventDefault(); enterKey(); }
});
cv.addEventListener('pointerdown', function () { if (FOCUS) setFocus(null); });
cv.addEventListener('focus', request);
cv.addEventListener('blur', request);
function ringBox(c) {
  var r = screenBox(c), w = Math.max(r[2], 4), h = Math.max(r[3], 4), x = r[0] + r[2] / 2 - w / 2, y = r[1] + r[3] / 2 - h / 2;
  return [x - RING_OFF, y - RING_OFF, w + 2 * RING_OFF, h + 2 * RING_OFF];
}
// The ring of the focused card, over all other drawing. Only while the canvas has the
// keyboard focus.
function drawFocus() {
  if (!liveFocus() || document.activeElement !== cv) return;
  var r = screenBox(FOCUS), b = ringBox(FOCUS);
  if (!boxOnScreen(b)) return;
  ctx.globalAlpha = 1; ctx.setLineDash([]); ctx.strokeStyle = C['--ink']; ctx.lineWidth = RING_W;
  ctx.beginPath(); rr(ctx, b[0], b[1], b[2], b[3], cardCorner(FOCUS, r[2], r[3]) + RING_OFF); ctx.stroke();
}
// The state of the keyboard focus for the tests.
function keyState() {
  var f = liveFocus();
  return {focus: f ? {map: f.map.id, id: f.id} : null, ring: f ? {box: ringBox(f), width: RING_W} : null};
}
"""
