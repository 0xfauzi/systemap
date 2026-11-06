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
it. Esc goes out one level (`goOut`), and the keyboard focus goes to the card that opens
the map that the camera comes from. A pointer input on the canvas removes the keyboard
focus from the card.

The focused card has a ring 4 px outside its box. The ring is 3 px wide, in the color of
the text (`--ink`). Thus the contrast ratio of the ring with the page color (`--map`) is 3
or more in the two schemes. The selected card has a border of 2.5 px in the selection color
(`--accent`). The page draws the ring only while the canvas has the keyboard focus. The
ring and the border have a constant cost in each frame. A text element with
`aria-live` gives the name of the focused card or the selected card to a screen reader.
"""

from __future__ import annotations

KEYS = r"""
// ---- the keyboard focus -------------------------------------------------------------
// FOCUS is the focused card, and FOCUS_MAP is the map in which Tab moves. SELECTED is the
// card that Enter selected.
var FOCUS = null, FOCUS_MAP = null, SELECTED = null, LIVE = document.getElementById('canvas-focus');
var RING_OFF = 4, RING_W = 3, PICK_W = 2.5;
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
    m._read = m._read.concat(r.list);
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
function cardWords(c) {
  var list = readingOrder(c.map), n = list.indexOf(c) + 1;
  return 'Card ' + c.id + ', ' + n + ' of ' + list.length + '.' + (c.child ? ' This card opens a map.' : '');
}
function setFocus(c) {
  FOCUS = c;
  if (c) { FOCUS_MAP = c.map; say(cardWords(c)); }
  request();
}
// Move the camera when the box of the focused card is not fully in the free box.
function showFocus(c) {
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
  setFocus(list[j]); showFocus(list[j]);
  return true;
}
function enterKey() {
  var c = FOCUS;
  if (!c) return;
  if (c.child) { FOCUS = null; FOCUS_MAP = c.child; say('Map ' + c.child.id + '.'); request(); flyTo(frameOf(c.child), FIT); return; }
  SELECTED = c; say('Selected: card ' + c.id + '.'); request();
}
// Esc: the keyboard focus goes to the card that opens the map that the camera leaves.
function focusOut() { var n = CHAIN.length; if (n) setFocus(CHAIN[n - 1]); }
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
function cornerOfCard(r) { return r[2] > 60 ? clamp(r[3] * 0.1, 2, 8) : 0; }
// The border of the selected card, under the rings and the portals.
function drawSelected() {
  if (!SELECTED) return;
  var r = screenBox(SELECTED);
  if (!boxOnScreen(r)) return;
  ctx.globalAlpha = 1; ctx.setLineDash([]); ctx.strokeStyle = C['--accent']; ctx.lineWidth = PICK_W;
  ctx.beginPath(); rr(ctx, r[0] + PICK_W / 2, r[1] + PICK_W / 2, Math.max(1, r[2] - PICK_W), Math.max(1, r[3] - PICK_W), cornerOfCard(r)); ctx.stroke();
}
// The ring of the focused card, over all other drawing. Only while the canvas has the
// keyboard focus.
function drawFocus() {
  if (!FOCUS || document.activeElement !== cv) return;
  var b = ringBox(FOCUS);
  if (!boxOnScreen(b)) return;
  ctx.globalAlpha = 1; ctx.setLineDash([]); ctx.strokeStyle = C['--ink']; ctx.lineWidth = RING_W;
  ctx.beginPath(); rr(ctx, b[0], b[1], b[2], b[3], cornerOfCard(screenBox(FOCUS)) + RING_OFF); ctx.stroke();
}
// The state of the keyboard focus for the tests.
function keyState() {
  var f = FOCUS, s = SELECTED;
  return {focus: f ? {map: f.map.id, id: f.id} : null, selected: s ? {map: s.map.id, id: s.id} : null,
    tabMap: FOCUS_MAP ? FOCUS_MAP.id : null, ring: f ? {box: ringBox(f), width: RING_W, off: RING_OFF} : null,
    live: LIVE ? LIVE.textContent : ''};
}
"""
