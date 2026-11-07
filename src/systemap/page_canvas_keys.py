"""The keyboard part of the canvas renderer: the keyboard focus on the cards of a map.

`page_canvas` joins this part before the input part. The design is the section "Access" of
docs/design/nested-canvas.md.

Tab and Shift+Tab move the keyboard focus through the cards of the current map in reading
order: the rows from top to bottom, and in each row the cards from left to right. A card
is in the row of the first card of that row when the vertical middle of the card is in
the box of that first card. After the last card, Tab moves the keyboard focus out of the
canvas, and before the first card Shift+Tab does the same. Thus the canvas does not keep
the keyboard focus.

When the box of the focused card is not fully in the free box of the screen, the camera
moves the card to the middle of the free box, at the same zoom. When the card is larger
than the free box, the camera zooms out to the card, with a margin of 20 % of the screen.

Enter on a card that opens a map goes into that map. Enter on a different card selects
it, with the selection of the touch part (`select` in `page_canvas_touch`). Esc goes out
one level (`goOut`). When the canvas has the keyboard focus, the keyboard focus then goes
to the card that opens the map that the camera comes from. A pointer input on the canvas
removes the keyboard focus from the card. When the map of the focused card closes (for
example after a zoom out, or after a zoom into the map of a different card), the card
loses the keyboard focus (`liveFocus`). The card keeps the keyboard focus only while it is
in the current map or it is open around the middle of the screen (`focusHeld`). Tab, the
ring and the live region use this one rule. Then the page draws no ring, and Enter does
nothing.

When the open map changes, the live region gives the new map and the focused card in one
text (`tell` in `page_canvas_tree`). Thus Esc, and Tab during a flight to a different map,
do not write the card words before the camera stops. A Tab during the flight that Enter
starts into a map does not stop that flight.

The focused card has a ring 7 px outside its box. The ring is 3 px wide, in the color of
the text (`--ink`). Thus the contrast ratio of the ring with the page color (`--map`) is 3
or more in the two schemes, and the ring is outside the line of the selected card. The page
draws the ring only while the canvas has the keyboard focus. The ring has a constant cost
in each frame. The live region of the page (`canvas-said`) gives the name of the focused
card or the selected card to a screen reader.
"""

from __future__ import annotations

KEYS = r"""
// ---- the keyboard focus -------------------------------------------------------------
// FOCUS is the focused card, and FOCUS_MAP is the map in which Tab moves.
var FOCUS = null, FOCUS_MAP = null, LIVE = document.getElementById('canvas-said');
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
  var r = screenBox(c), g = gutters(), x0 = g.x, y0 = g.top, x1 = W - g.x, y1 = H - g.bottom;
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
  ctx.beginPath(); rr(ctx, b[0], b[1], b[2], b[3], cardCorner(r[2], r[3]) + RING_OFF); ctx.stroke();
}
// The state of the keyboard focus for the tests.
function keyState() {
  var f = liveFocus();
  return {focus: f ? {map: f.map.id, id: f.id} : null, ring: f ? {box: ringBox(f), width: RING_W} : null};
}
"""
